"""Spotify export parser (CSV and JSON) and similarity-based metadata matcher."""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from flac_injector.fingerprint import parse_filename_metadata
from flac_injector.models import (
    PLACEHOLDER_TAG_VALUES,
    ScanResult,
    TrackMetadata,
    resolve_album_name,
    split_artists,
)
from flac_injector.scanner import inspect_audio

logger = logging.getLogger(__name__)


@dataclass
class SpotifyTrackRecord:
    """Canonical representation of a track parsed from a Spotify CSV or JSON export."""

    title: str
    artist: str
    album: str
    artists: list[str] = field(default_factory=list)
    album_artist: str | None = None
    uri: str | None = None
    spotify_id: str | None = None
    release_date: str | None = None
    year: str | None = None
    duration_ms: int | None = None
    duration_seconds: float | None = None
    popularity: int | None = None
    explicit: bool | None = None
    genres: list[str] = field(default_factory=list)
    record_label: str | None = None
    bpm: float | None = None
    isrc: str | None = None
    track_number: str | None = None
    track_total: str | None = None
    disc_number: str | None = None
    cover_art_url: str | None = None
    audio_features: dict[str, Any] = field(default_factory=dict)
    raw_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpotifyTrackRecord | None:
        """Parse a track from a normalized dictionary (from CSV or JSON)."""
        # Normalize keys by removing spaces, underscores, hyphens, and lowercase
        norm_map: dict[str, Any] = {}
        for k, v in data.items():
            if k is None:
                continue
            cleaned_key = "".join(ch for ch in str(k).lower() if ch.isalnum())
            norm_map[cleaned_key] = v

        # 1. Title / Track Name
        title = (
            norm_map.get("trackname")
            or norm_map.get("track")
            or norm_map.get("title")
            or norm_map.get("name")
            or norm_map.get("songname")
            or norm_map.get("song")
        )
        if not title or not str(title).strip():
            return None
        title = str(title).strip()

        # 2. Artist(s)
        artist_raw = (
            norm_map.get("artistnames")
            or norm_map.get("artistname")
            or norm_map.get("artists")
            or norm_map.get("artist")
        )
        artists: list[str] = []
        if isinstance(artist_raw, list):
            raw_items = []
            for item in artist_raw:
                if isinstance(item, dict) and "name" in item:
                    raw_items.append(str(item["name"]).strip())
                elif isinstance(item, str) and item.strip():
                    raw_items.append(item.strip())
            artists = split_artists(raw_items)
        elif isinstance(artist_raw, str) and artist_raw.strip():
            artists = split_artists(artist_raw)

        artist_display = ", ".join(artists) if artists else "Unknown Artist"

        # 3. Album & nested album properties
        album_obj = (
            norm_map.get("albumname") or norm_map.get("album") or norm_map.get("collectionname")
        )
        album_raw: str | None = None
        album_dict: dict[str, Any] = {}
        if isinstance(album_obj, dict):
            album_dict = album_obj
            album_raw = album_dict.get("name")
        elif album_obj is not None:
            album_raw = str(album_obj).strip()

        album_type = (
            norm_map.get("albumtype")
            or (album_dict.get("album_type") if isinstance(album_dict, dict) else None)
            or norm_map.get("type")
        )
        is_single = bool(album_type and str(album_type).lower() == "single")
        track_total_val = (
            norm_map.get("tracktotal")
            or norm_map.get("totaltracks")
            or (album_dict.get("total_tracks") if isinstance(album_dict, dict) else None)
        )

        album = resolve_album_name(
            album=album_raw,
            title=title,
            is_single=is_single,
            total_tracks=track_total_val,
        )

        # 4. URI & Spotify ID
        uri = norm_map.get("trackuri") or norm_map.get("uri") or norm_map.get("spotifyuri")
        if uri:
            uri = str(uri).strip()
        spotify_id = norm_map.get("spotifyid") or norm_map.get("id") or norm_map.get("trackid")
        if not spotify_id and uri and "spotify:track:" in str(uri):
            spotify_id = str(uri).split("spotify:track:")[-1].split("?")[0].strip()
        elif not spotify_id and uri and "open.spotify.com/track/" in str(uri):
            spotify_id = str(uri).split("open.spotify.com/track/")[-1].split("?")[0].strip()
        if spotify_id:
            spotify_id = str(spotify_id).strip()
        if not uri and spotify_id:
            uri = f"spotify:track:{spotify_id}"

        # 5. Release Date & Year
        release_date = (
            norm_map.get("releasedate")
            or norm_map.get("date")
            or norm_map.get("year")
            or norm_map.get("albumreleasedate")
            or album_dict.get("release_date")
        )
        year: str | None = None
        if release_date:
            release_date = str(release_date).strip()
            if len(release_date) >= 4 and release_date[:4].isdigit():
                year = release_date[:4]
            elif release_date.isdigit():
                year = release_date

        # 6. Duration
        duration_ms = None
        duration_raw = (
            norm_map.get("durationms")
            or norm_map.get("duration")
            or norm_map.get("trackdurationms")
            or norm_map.get("lengthms")
        )
        if duration_raw is not None:
            try:
                # Handle formatted time "mm:ss" or float / integer milliseconds
                if isinstance(duration_raw, str) and ":" in duration_raw:
                    parts = duration_raw.split(":")
                    if len(parts) == 2:
                        duration_ms = int((int(parts[0]) * 60 + float(parts[1])) * 1000)
                else:
                    val = float(duration_raw)
                    # If value is smaller than 1000, it's likely seconds, not ms
                    if val < 1000 and val > 0:
                        duration_ms = int(val * 1000)
                    else:
                        duration_ms = int(val)
            except (ValueError, TypeError):
                duration_ms = None

        duration_seconds = round(duration_ms / 1000.0, 2) if duration_ms else None

        # 7. Popularity
        popularity = None
        pop_raw = norm_map.get("popularity")
        if pop_raw is not None:
            try:
                popularity = int(float(pop_raw))
            except (ValueError, TypeError):
                pass

        # 8. Explicit
        explicit = None
        exp_raw = norm_map.get("explicit")
        if exp_raw is not None:
            if isinstance(exp_raw, bool):
                explicit = exp_raw
            elif str(exp_raw).lower() in ("true", "1", "yes", "t"):
                explicit = True
            elif str(exp_raw).lower() in ("false", "0", "no", "f"):
                explicit = False

        # 9. Genres
        genres_raw = norm_map.get("genres") or norm_map.get("genre")
        genres: list[str] = []
        if isinstance(genres_raw, list):
            genres = [str(g).strip() for g in genres_raw if str(g).strip()]
        elif isinstance(genres_raw, str) and genres_raw.strip():
            # Split comma or semicolon
            delim = ";" if ";" in genres_raw else ","
            genres = [g.strip() for g in genres_raw.split(delim) if g.strip()]

        # 10. Record Label / Publisher
        record_label = (
            norm_map.get("recordlabel")
            or norm_map.get("label")
            or norm_map.get("publisher")
            or norm_map.get("organization")
        )
        if record_label:
            record_label = str(record_label).strip()

        # 11. Tempo / BPM
        bpm = None
        tempo_raw = norm_map.get("tempo") or norm_map.get("bpm")
        if tempo_raw is not None:
            try:
                val = float(tempo_raw)
                if val > 0:
                    bpm = round(val, 1)
            except (ValueError, TypeError):
                pass

        # 12. ISRC
        ext_ids = norm_map.get("externalids")
        if isinstance(ext_ids, dict) and "isrc" in ext_ids:
            isrc = ext_ids["isrc"]
        else:
            isrc = norm_map.get("isrc")
        if isrc:
            isrc = str(isrc).strip().upper()

        # 13. Track Number, Total, Disc Number
        track_num = norm_map.get("tracknumber") or norm_map.get("trackno")
        if track_num is not None:
            track_num = str(track_num).strip()
        track_total = (
            norm_map.get("tracktotal")
            or norm_map.get("totaltracks")
            or album_dict.get("total_tracks")
        )
        if track_total is not None:
            track_total = str(track_total).strip()
        disc_num = norm_map.get("discnumber") or norm_map.get("discno")
        if disc_num is not None:
            disc_num = str(disc_num).strip()

        # 14. Cover Art URL
        cover_art_url = (
            norm_map.get("coverarturl")
            or norm_map.get("imageurl")
            or norm_map.get("albumimageurl")
            or norm_map.get("artworkurl")
        )
        if not cover_art_url and "images" in album_dict and isinstance(album_dict["images"], list):
            imgs = album_dict["images"]
            if imgs and isinstance(imgs[0], dict) and "url" in imgs[0]:
                cover_art_url = imgs[0]["url"]
        if cover_art_url:
            cover_art_url = str(cover_art_url).strip()

        # 15. Audio Features
        feature_keys = [
            "danceability",
            "energy",
            "key",
            "loudness",
            "mode",
            "speechiness",
            "acousticness",
            "instrumentalness",
            "liveness",
            "valence",
            "timesignature",
        ]
        audio_features: dict[str, Any] = {}
        for fk in feature_keys:
            val = norm_map.get(fk)
            if val is not None and str(val).strip() != "":
                audio_features[fk] = val

        return cls(
            title=title,
            artist=artist_display,
            album=album,
            artists=artists,
            album_artist=artists[0] if artists else None,
            uri=uri,
            spotify_id=spotify_id,
            release_date=release_date,
            year=year,
            duration_ms=duration_ms,
            duration_seconds=duration_seconds,
            popularity=popularity,
            explicit=explicit,
            genres=genres,
            record_label=record_label,
            bpm=bpm,
            isrc=isrc,
            track_number=track_num,
            track_total=track_total,
            disc_number=disc_num,
            cover_art_url=cover_art_url,
            audio_features=audio_features,
            raw_data=data,
        )


def load_spotify_data(
    source: Path | str | bytes | list[dict[str, Any]],
) -> list[SpotifyTrackRecord]:
    """Parse Spotify export data from a file path, string content, or list of dicts.

    Supports:
    - CSV format (Exportify, Spotlistr, TuneMyMusic, Soundiiz, etc.)
    - JSON format (Array of tracks, Spotify API playlist / items response, etc.)
    """
    if isinstance(source, list):
        records: list[SpotifyTrackRecord] = []
        for item in source:
            if isinstance(item, dict):
                rec = SpotifyTrackRecord.from_dict(item)
                if rec:
                    records.append(rec)
        return records

    content: str
    is_json_ext = False

    if isinstance(source, Path):
        if not source.exists():
            raise FileNotFoundError(f"Spotify data file does not exist: {source}")
        is_json_ext = source.suffix.lower() == ".json"
        # Read with utf-8-sig to automatically handle BOM
        try:
            content = source.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            content = source.read_text(encoding="latin-1")
    elif isinstance(source, bytes):
        try:
            content = source.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = source.decode("latin-1")
    else:
        # Source is a string: could be a file path or raw string content
        possible_path = Path(source)
        if "\n" not in source and len(source) < 500 and possible_path.exists():
            return load_spotify_data(possible_path)
        content = source

    content_strip = content.strip()
    if not content_strip:
        return []

    # Attempt JSON parsing first if requested or looks like JSON
    if is_json_ext or content_strip.startswith(("{", "[")):
        try:
            data = json.loads(content_strip)
            return _parse_json_data(data)
        except json.JSONDecodeError as err:
            if is_json_ext:
                raise ValueError("Failed to parse file as JSON.") from err

    # Otherwise, parse as CSV
    return _parse_csv_data(content_strip)


def _parse_json_data(data: Any) -> list[SpotifyTrackRecord]:
    """Parse parsed JSON structure into SpotifyTrackRecord list."""
    items: list[dict[str, Any]] = []

    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                # Spotify API item format {"track": {...}} or flat {...}
                if "track" in entry and isinstance(entry["track"], dict):
                    items.append(entry["track"])
                else:
                    items.append(entry)
    elif isinstance(data, dict):
        if "tracks" in data and isinstance(data["tracks"], list):
            items.extend(_extract_dict_items(data["tracks"]))
        elif "items" in data and isinstance(data["items"], list):
            items.extend(_extract_dict_items(data["items"]))
        elif "data" in data and isinstance(data["data"], list):
            items.extend(_extract_dict_items(data["data"]))
        else:
            items.append(data)

    records: list[SpotifyTrackRecord] = []
    for item in items:
        rec = SpotifyTrackRecord.from_dict(item)
        if rec:
            records.append(rec)
    return records


def _extract_dict_items(item_list: list[Any]) -> list[dict[str, Any]]:
    """Unnest items from a list of playlist items or track wrappers."""
    res: list[dict[str, Any]] = []
    for it in item_list:
        if isinstance(it, dict):
            if "track" in it and isinstance(it["track"], dict):
                res.append(it["track"])
            else:
                res.append(it)
    return res


def _parse_csv_data(csv_text: str) -> list[SpotifyTrackRecord]:
    """Parse CSV text into SpotifyTrackRecord list."""
    f = io.StringIO(csv_text)
    # Detect delimiter
    sample = csv_text[:4096]
    delimiter = ","
    if "\t" in sample and sample.count("\t") > sample.count(","):
        delimiter = "\t"

    reader = csv.DictReader(f, delimiter=delimiter)
    records: list[SpotifyTrackRecord] = []
    for row in reader:
        rec = SpotifyTrackRecord.from_dict(row)
        if rec:
            records.append(rec)
    return records


def calculate_similarity(
    scan: ScanResult,
    hints: dict[str, Any],
    record: SpotifyTrackRecord,
) -> float:
    """Calculate normalized similarity ratio (0.0 to 1.0) between an audio file and a Spotify track.

    Evaluates similarity across both embedded metadata tags and filename-parsed hints,
    ensuring tracks with missing or corrupt internal tags match by filename.
    """
    cand_title = record.title.strip().lower()
    cand_artist = record.artist.strip().lower()
    cand_album = record.album.strip().lower()

    # Filename-derived hints
    fn_parsed = parse_filename_metadata(scan.path)
    fn_title = str(hints.get("title") or fn_parsed.get("title") or scan.path.stem).strip().lower()
    fn_artist = str(hints.get("artist") or fn_parsed.get("artist") or "").strip().lower()
    fn_album = str(hints.get("album") or fn_parsed.get("album") or "").strip().lower()

    # Tag-derived values
    tag_title = str(scan.existing_tags.get("TITLE", [""])[0] or "").strip().lower()
    tag_artist = str(scan.existing_tags.get("ARTIST", [""])[0] or "").strip().lower()
    tag_album = str(scan.existing_tags.get("ALBUM", [""])[0] or "").strip().lower()

    def _eval_candidate(f_title: str, f_artist: str, f_album: str) -> float:
        clean_title = f_title.strip("\"'")
        if not clean_title or clean_title in PLACEHOLDER_TAG_VALUES:
            return 0.0

        # 1. Title Similarity
        t_sort = fuzz.token_sort_ratio(clean_title, cand_title) / 100.0
        t_set = fuzz.token_set_ratio(clean_title, cand_title) / 100.0
        title_sim = max(t_sort, t_set * 0.95)

        if title_sim < 0.25:
            return 0.0

        # 2. Artist Similarity
        clean_artist = f_artist.strip("\"'")
        artist_sim = 0.5
        if clean_artist and clean_artist not in PLACEHOLDER_TAG_VALUES:
            a_sort = fuzz.token_sort_ratio(clean_artist, cand_artist) / 100.0
            a_set = fuzz.token_set_ratio(clean_artist, cand_artist) / 100.0
            artist_sim = max(a_sort, a_set * 0.95)
            for a in record.artists:
                sub_sim = fuzz.token_sort_ratio(clean_artist, a.lower()) / 100.0
                if sub_sim > artist_sim:
                    artist_sim = sub_sim
        else:
            stem_lower = scan.path.stem.lower()
            if cand_artist and cand_artist in stem_lower:
                artist_sim = 0.90
            elif any(a.lower() in stem_lower for a in record.artists if len(a) > 2):
                artist_sim = 0.85

        # 3. Album Similarity
        album_sim = 0.8
        clean_album = f_album.strip("\"'")
        is_file_album_valid = clean_album and clean_album not in PLACEHOLDER_TAG_VALUES
        is_cand_album_valid = cand_album and cand_album not in PLACEHOLDER_TAG_VALUES
        if is_file_album_valid and is_cand_album_valid:
            album_sim = fuzz.token_sort_ratio(clean_album, cand_album) / 100.0

        # Base weighted textual score
        if clean_artist and clean_artist not in PLACEHOLDER_TAG_VALUES:
            base_score = (0.50 * title_sim) + (0.35 * artist_sim) + (0.15 * album_sim)
        else:
            base_score = (0.65 * title_sim) + (0.25 * artist_sim) + (0.10 * album_sim)

        # 4. Duration Comparison
        if scan.duration_seconds > 0 and record.duration_seconds:
            delta = abs(scan.duration_seconds - record.duration_seconds)
            if delta <= 1.5:
                base_score = min(1.0, base_score + 0.08)
            elif delta <= 4.0:
                base_score = min(1.0, base_score + 0.04)
            elif delta > 20.0:
                max_penalty = 0.15 if (title_sim >= 0.85 and artist_sim >= 0.85) else 0.35
                penalty = min(max_penalty, (delta - 20.0) / 40.0)
                base_score = max(0.0, base_score - penalty)

        return round(min(1.0, max(0.0, base_score)), 3)

    score_tags = _eval_candidate(tag_title, tag_artist, tag_album) if tag_title else 0.0
    score_filename = _eval_candidate(fn_title, fn_artist, fn_album)
    score_stem = _eval_candidate(scan.path.stem.lower(), "", "")

    return max(score_tags, score_filename, score_stem)


@dataclass
class MatchResult:
    """Result of matching an audio file against the Spotify dataset."""

    file_path: Path
    scan_result: ScanResult
    spotify_record: SpotifyTrackRecord | None
    similarity_score: float
    is_match: bool
    missing_gaps_filled: list[str] = field(default_factory=list)
    overwritten_tags: list[str] = field(default_factory=list)
    metadata_to_inject: TrackMetadata | None = None


def match_file_to_spotify(
    file_path: Path,
    spotify_records: list[SpotifyTrackRecord],
    threshold: float = 0.70,
    overwrite: bool = False,
    scan_result: ScanResult | None = None,
    overwrite_mismatched: bool = True,
    mismatch_threshold: float = 0.70,
) -> MatchResult:
    """Compare a single audio file against Spotify records and generate the enriched metadata."""
    if not scan_result:
        scan_result = inspect_audio(file_path)

    hints = parse_filename_metadata(file_path)
    best_record: SpotifyTrackRecord | None = None
    best_score = 0.0

    for rec in spotify_records:
        score = calculate_similarity(scan_result, hints, rec)
        if score > best_score:
            best_score = score
            best_record = rec

    if not best_record or best_score < threshold:
        return MatchResult(
            file_path=file_path,
            scan_result=scan_result,
            spotify_record=best_record,
            similarity_score=best_score,
            is_match=False,
        )

    # Construct enriched TrackMetadata from the matched Spotify record
    existing = scan_result.existing_tags
    gaps_filled: list[str] = []
    overwritten: list[str] = []

    # Check whether the file's existing tags meet similarity to the matched Spotify track
    curr_raw_title = existing.get("TITLE", [""])[0] if existing.get("TITLE") else ""
    curr_raw_artist = existing.get("ARTIST", [""])[0] if existing.get("ARTIST") else ""

    title_matches = False
    if curr_raw_title and curr_raw_title.lower().strip("\"'") not in PLACEHOLDER_TAG_VALUES:
        title_matches = (
            fuzz.token_set_ratio(curr_raw_title.lower(), best_record.title.lower())
            >= mismatch_threshold * 100
        )

    artist_matches = False
    if curr_raw_artist and curr_raw_artist.lower().strip("\"'") not in PLACEHOLDER_TAG_VALUES:
        a_sims = [fuzz.token_set_ratio(curr_raw_artist.lower(), best_record.artist.lower())]
        for a in best_record.artists:
            a_sims.append(fuzz.token_set_ratio(curr_raw_artist.lower(), a.lower()))
        artist_matches = max(a_sims) >= mismatch_threshold * 100

    # If the file's existing artist or song name does not meet similarity to the matched track
    is_file_mismatched = bool(overwrite_mismatched and (not title_matches or not artist_matches))

    # Helper to resolve field: fill gap or overwrite
    def pick_str(
        tag_name: str,
        spotify_val: str | None,
        current_val: str | None,
        is_identity_field: bool = False,
    ) -> str | None:
        curr = (current_val or "").strip()
        is_unknown = not curr or curr.lower().strip("\"'") in PLACEHOLDER_TAG_VALUES
        if spotify_val and str(spotify_val).strip():
            clean_spotify = str(spotify_val).strip()
            if is_unknown:
                gaps_filled.append(tag_name)
                return clean_spotify
            elif overwrite and clean_spotify.lower() != curr.lower():
                overwritten.append(tag_name)
                return clean_spotify
            elif (
                is_file_mismatched
                and (is_identity_field or tag_name == "ALBUM")
                and clean_spotify.lower() != curr.lower()
            ):
                overwritten.append(tag_name)
                return clean_spotify
        return curr if (curr and not is_unknown) else None

    target_title = (
        pick_str("TITLE", best_record.title, existing.get("TITLE", [""])[0], is_identity_field=True)
        or best_record.title
    )
    target_artist = (
        pick_str(
            "ARTIST", best_record.artist, existing.get("ARTIST", [""])[0], is_identity_field=True
        )
        or best_record.artist
    )
    target_album = (
        pick_str("ALBUM", best_record.album, existing.get("ALBUM", [""])[0]) or best_record.album
    )
    target_album = resolve_album_name(
        album=target_album,
        title=target_title,
        is_single=bool(
            (best_record.raw_data.get("album_type") == "single")
            or (best_record.album and best_record.album.lower() in ("single", "the single"))
        ),
        total_tracks=best_record.track_total,
    )

    # Album artist
    existing_aa = existing.get("ALBUMARTIST", [""])[0]
    target_album_artist = pick_str(
        "ALBUMARTIST",
        best_record.album_artist or best_record.artist,
        existing_aa,
    )

    # Date / Year
    existing_date = existing.get("DATE", [""])[0]
    target_date = pick_str("DATE", best_record.release_date or best_record.year, existing_date)

    # Genres
    existing_genres = existing.get("GENRE", [])
    target_genres: list[str] = []
    if best_record.genres:
        if not existing_genres:
            target_genres = best_record.genres
            gaps_filled.append("GENRE")
        elif overwrite:
            target_genres = best_record.genres
            overwritten.append("GENRE")
        else:
            # Preserve existing genres and merge new ones
            seen = {g.lower() for g in existing_genres}
            target_genres = list(existing_genres)
            for g in best_record.genres:
                if g.lower() not in seen:
                    seen.add(g.lower())
                    target_genres.append(g)
    else:
        target_genres = existing_genres

    # Label
    existing_label = existing.get("LABEL", existing.get("ORGANIZATION", [""]))[0]
    target_label = pick_str("LABEL", best_record.record_label, existing_label)

    # BPM
    existing_bpm_str = existing.get("BPM", [None])[0]
    target_bpm: float | None = None
    if existing_bpm_str:
        try:
            target_bpm = float(existing_bpm_str)
        except (ValueError, TypeError):
            pass

    if best_record.bpm is not None:
        if target_bpm is None:
            target_bpm = best_record.bpm
            gaps_filled.append("BPM")
        elif overwrite and target_bpm != best_record.bpm:
            target_bpm = best_record.bpm
            overwritten.append("BPM")

    # Explicit
    existing_explicit: bool | None = None
    if "ITUNESADVISORY" in existing:
        existing_explicit = existing["ITUNESADVISORY"][0] == "1"

    target_explicit: bool | None = existing_explicit
    if best_record.explicit is not None:
        if target_explicit is None:
            target_explicit = best_record.explicit
            gaps_filled.append("EXPLICIT")
        elif overwrite and target_explicit != best_record.explicit:
            target_explicit = best_record.explicit
            overwritten.append("EXPLICIT")

    # ISRC
    existing_isrc = existing.get("ISRC", [None])[0]
    target_isrc = pick_str("ISRC", best_record.isrc, existing_isrc)

    # Extra tags: add Spotify identifiers and audio features
    extra_tags: dict[str, str] = {}
    if best_record.spotify_id:
        extra_tags["SPOTIFY_TRACK_ID"] = best_record.spotify_id
        gaps_filled.append("SPOTIFY_TRACK_ID")
    if best_record.uri:
        extra_tags["SPOTIFY_TRACK_URI"] = best_record.uri
    if best_record.popularity is not None:
        extra_tags["SPOTIFY_POPULARITY"] = str(best_record.popularity)

    # Add audio features to extra tags
    for feat_name, feat_val in best_record.audio_features.items():
        tag_key = f"SPOTIFY_{feat_name.upper()}"
        extra_tags[tag_key] = str(feat_val)

    metadata = TrackMetadata(
        title=target_title,
        artist=target_artist,
        artists=best_record.artists or split_artists(target_artist),
        album=target_album,
        album_artist=target_album_artist,
        date=target_date,
        year=best_record.year,
        genre=target_genres,
        label=target_label,
        bpm=target_bpm,
        explicit=target_explicit,
        isrc=target_isrc,
        track_number=best_record.track_number,
        track_total=best_record.track_total,
        disc_number=best_record.disc_number,
        cover_art_url=best_record.cover_art_url,
        confidence_score=best_score,
        source_provider="spotify_export",
        extra_tags=extra_tags,
    )

    return MatchResult(
        file_path=file_path,
        scan_result=scan_result,
        spotify_record=best_record,
        similarity_score=best_score,
        is_match=True,
        missing_gaps_filled=sorted(list(set(gaps_filled))),
        overwritten_tags=sorted(list(set(overwritten))),
        metadata_to_inject=metadata,
    )
