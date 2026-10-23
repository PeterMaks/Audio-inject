export interface CoverArtInfo {
  type: number;
  mime: string;
  width: number;
  height: number;
  depth: number;
  size_bytes: number;
}

export interface ScanItem {
  path: string;
  filename: string;
  duration_seconds: number;
  sample_rate: number;
  channels: number;
  bits_per_sample: number;
  existing_tags: Record<string, string[]>;
  missing_fields: string[];
  has_cover_art: boolean;
  cover_art_info: CoverArtInfo | null;
  cover_art_data_url?: string;
  is_incomplete: boolean;
  audio_format: "flac" | "mp3" | "wav" | string;
}

export interface ScanResponse {
  items: ScanItem[];
  total: number;
  incomplete: number;
  complete: number;
  format_counts: Record<string, number>;
}

export interface TrackMetadata {
  title: string;
  artist: string;
  album: string;
  album_artist?: string | null;
  track_number?: string | null;
  track_total?: string | null;
  disc_number?: string | null;
  disc_total?: string | null;
  date?: string | null;
  year?: string | null;
  genre: string[];
  isrc?: string | null;
  barcode?: string | null;
  label?: string | null;
  copyright?: string | null;
  composer?: string | null;
  bpm?: number | null;
  explicit?: boolean | null;
  acoustid_id?: string | null;
  musicbrainz_trackid?: string | null;
  musicbrainz_albumid?: string | null;
  musicbrainz_artistid?: string | null;
  cover_art_url?: string | null;
  confidence_score: number;
  source_provider: string;
  vorbis_comments?: Record<string, string[]>;
  id3_frames?: Record<string, any>;
}

export interface ProgressEvent {
  type: "progress";
  stage: "start" | "convert" | "fingerprint" | "acoustid" | "itunes" | "deezer" | "spotify" | "songlink" | "merge" | "art" | "write" | "done" | "skip" | "unmatched" | "dry_run" | "finished";
  file: string;
  percent: number;
  message: string;
  cover_art_url?: string;
}

export interface HealthStatus {
  python_version: string;
  in_venv: boolean;
  ffmpeg: {
    available: boolean;
    path: string | null;
  };
  fpcalc: {
    available: boolean;
    path: string | null;
  };
  env_status: {
    acoustid_configured: boolean;
    spotify_configured: boolean;
    discogs_configured?: boolean;
    songlink_configured?: boolean;
    confidence_threshold: number;
    cover_art_min_resolution: number;
    rate_limit_delay: number;
    request_timeout: number;
  };
}

export interface EnvSettings {
  ACOUSTID_API_KEY: string;
  SPOTIFY_CLIENT_ID: string;
  SPOTIFY_CLIENT_SECRET: string;
  DISCOGS_TOKEN?: string;
  SONGLINK_API_KEY?: string;
  MUSICBRAINZ_USER_AGENT: string;
  RATE_LIMIT_DELAY: number;
  COVER_ART_MIN_RESOLUTION: number;
  CONFIDENCE_THRESHOLD: number;
  REQUEST_TIMEOUT: number;
  FPCALC_PATH: string;
}

export interface FingerprintResponse {
  path: string;
  filename: string;
  fingerprint: string;
  duration: number;
  hints: Record<string, any>;
}

export interface InjectItemResult {
  file: string;
  status: "injected" | "dry_run" | "skipped" | "unmatched" | "error";
  reason?: string;
  error?: string;
  metadata?: TrackMetadata;
  cover_art_url?: string;
  confidence_score?: number;
}

export interface InjectResponse {
  processed: number;
  success: number;
  skipped: number;
  failed: number;
  items: InjectItemResult[];
}

export interface ConvertItemResult {
  source: string;
  destination?: string;
  status: "converted" | "dry_run" | "error";
  error?: string;
  injection?: InjectResponse;
}

export interface ConvertResponse {
  converted: number;
  failed: number;
  items: ConvertItemResult[];
}
