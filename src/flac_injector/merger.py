"""Waterfall metadata aggregation and fuzzy-match confidence scoring."""

from typing import Any

from rapidfuzz import fuzz

from flac_injector.models import TrackMetadata


def calculate_confidence(
    candidate: TrackMetadata,
    file_duration: float,
    hints: dict[str, Any],
) -> float:
    """Calculate normalized confidence score (0.0 to 1.0) for a candidate track."""
    # 1. Authoritative confidence if resolved via fingerprint or ISRC
    if candidate.acoustid_id or candidate.musicbrainz_trackid:
        base_score = max(0.92, candidate.confidence_score)
    elif candidate.isrc:
        base_score = max(0.90, candidate.confidence_score)
    else:
        # Calculate textual similarity against hints
        hint_title = str(hints.get("title") or "").strip().lower()
        hint_artist = str(hints.get("artist") or "").strip().lower()
        hint_album = str(hints.get("album") or "").strip().lower()

        if hint_title and hint_artist:
            title_sim = fuzz.token_sort_ratio(candidate.title.lower(), hint_title) / 100.0
            artist_sim = fuzz.token_sort_ratio(candidate.artist.lower(), hint_artist) / 100.0
            album_sim = (
                fuzz.token_sort_ratio(candidate.album.lower(), hint_album) / 100.0
                if hint_album
                else 0.8
            )
            base_score = 0.50 * title_sim + 0.35 * artist_sim + 0.15 * album_sim
        elif hint_title:
            cand_combined = f"{candidate.artist} {candidate.title}".lower()
            stem_sim = fuzz.token_set_ratio(cand_combined, hint_title) / 100.0
            title_sim = fuzz.token_sort_ratio(candidate.title.lower(), hint_title) / 100.0
            base_score = max(stem_sim, title_sim * 0.9)
        elif hint_artist:
            artist_sim = fuzz.token_sort_ratio(candidate.artist.lower(), hint_artist) / 100.0
            base_score = artist_sim * 0.8
        else:
            base_score = (
                max(0.75, candidate.confidence_score)
                if candidate.confidence_score > 0
                else 0.50
            )

    # Check for duration delta penalty or match bonus if candidate has duration info
    candidate_dur = hints.get("candidate_duration") or hints.get("duration")
    if candidate_dur and file_duration > 0:
        try:
            delta = abs(float(file_duration) - float(candidate_dur))
            if delta <= 3.0:
                base_score = min(1.0, base_score + 0.05)
            else:
                # Deduct up to 0.40 based on duration delta
                penalty = min(0.40, (delta - 3.0) / 20.0)
                base_score -= penalty
        except (ValueError, TypeError):
            pass

    return round(min(1.0, max(0.0, base_score)), 3)


def aggregate_candidates(
    candidates: list[TrackMetadata],
    file_duration: float,
    hints: dict[str, Any],
    confidence_threshold: float = 0.70,
) -> TrackMetadata | None:
    """Perform waterfall aggregation across multiple candidate tracks."""
    if not candidates:
        return None

    # Recalculate confidence for each candidate
    scored_candidates: list[tuple[float, TrackMetadata]] = []
    for cand in candidates:
        score = calculate_confidence(cand, file_duration, hints)
        cand.confidence_score = score
        scored_candidates.append((score, cand))

    # Sort candidates by descending confidence score
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_candidate = scored_candidates[0]

    if best_score < confidence_threshold:
        return None

    # Clone the best candidate to start composite aggregation
    merged = best_candidate.model_copy(deep=True)

    # Waterfall field enrichment from remaining candidates
    for _, cand in scored_candidates[1:]:
        # 1. Fill missing ISRC
        if not merged.isrc and cand.isrc:
            merged.isrc = cand.isrc

        # 2. Fill musical attributes: BPM & Explicit
        if merged.bpm is None and cand.bpm is not None:
            merged.bpm = cand.bpm
        if merged.explicit is None and cand.explicit is not None:
            merged.explicit = cand.explicit

        # 3. Fill missing genres
        if not merged.genre and cand.genre:
            merged.genre = cand.genre

        # 4. Fill missing track/disc numbers
        if not merged.track_number and cand.track_number:
            merged.track_number = cand.track_number
        if not merged.track_total and cand.track_total:
            merged.track_total = cand.track_total
        if not merged.disc_number and cand.disc_number:
            merged.disc_number = cand.disc_number
        if not merged.disc_total and cand.disc_total:
            merged.disc_total = cand.disc_total

        # 5. Fill missing MusicBrainz identifiers
        if not merged.musicbrainz_trackid and cand.musicbrainz_trackid:
            merged.musicbrainz_trackid = cand.musicbrainz_trackid
        if not merged.musicbrainz_albumid and cand.musicbrainz_albumid:
            merged.musicbrainz_albumid = cand.musicbrainz_albumid
        if not merged.musicbrainz_artistid and cand.musicbrainz_artistid:
            merged.musicbrainz_artistid = cand.musicbrainz_artistid
        if not merged.acoustid_id and cand.acoustid_id:
            merged.acoustid_id = cand.acoustid_id

        # 6. Fill missing date
        if not merged.date and cand.date:
            merged.date = cand.date

    # Cover Art Waterfall: Select the candidate with the highest resolution cover art
    best_art_url = merged.cover_art_url
    best_res = (merged.cover_art_width or 0) * (merged.cover_art_height or 0)

    for _, cand in scored_candidates:
        if cand.cover_art_url:
            cand_res = (cand.cover_art_width or 0) * (cand.cover_art_height or 0)
            if cand_res > best_res or not best_art_url:
                best_art_url = cand.cover_art_url
                best_res = cand_res
                merged.cover_art_url = cand.cover_art_url
                merged.cover_art_width = cand.cover_art_width
                merged.cover_art_height = cand.cover_art_height

    merged.confidence_score = best_score
    return merged
