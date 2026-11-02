import React, { useEffect, useState } from "react";
import { Save, Key, Sliders, Eye, EyeOff } from "lucide-react";
import { getSettings, saveSettings } from "../lib/tauriClient";
import { EnvSettings } from "../types/injector";

interface SettingsModalProps {
  onSaved?: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ onSaved }) => {
  const [settings, setSettings] = useState<EnvSettings>({
    ACOUSTID_API_KEY: "",
    SPOTIFY_CLIENT_ID: "",
    SPOTIFY_CLIENT_SECRET: "",
    DISCOGS_TOKEN: "",
    SONGLINK_API_KEY: "",
    MUSICBRAINZ_USER_AGENT: "flac-meta-injector/0.1.0",
    RATE_LIMIT_DELAY: 1.0,
    COVER_ART_MIN_RESOLUTION: 600,
    CONFIDENCE_THRESHOLD: 0.7,
    REQUEST_TIMEOUT: 15.0,
    FPCALC_PATH: "fpcalc",
  });

  const [showSecrets, setShowSecrets] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    getSettings()
      .then((data) => {
        setSettings((prev) => ({ ...prev, ...data }));
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load settings:", err);
        setLoading(false);
      });
  }, []);

  const handleSave = async () => {
    try {
      const updated = await saveSettings(settings);
      setSettings((prev) => ({ ...prev, ...updated }));
      onSaved?.();
    } catch (e) {
      console.error("Failed to save settings:", e);
    }
  };

  return (
    <div className="flex flex-col h-full space-y-4 overflow-y-auto pr-1 max-w-2xl">
      {/* Credentials Group */}
      <div className="p-4 rounded-2xl glass-panel space-y-3">
        <div className="flex items-center justify-between border-b border-white/[0.08] pb-2.5">
          <div className="flex items-center space-x-2">
            <Key className="w-4 h-4 text-[#0A84FF]" />
            <h4 className="text-xs font-semibold text-[#F5F5F7]">
              Streaming and acoustic API credentials
            </h4>
          </div>
          <button
            type="button"
            onClick={() => setShowSecrets(!showSecrets)}
            className="flex items-center space-x-1 text-xs text-[#A1A1A6] hover:text-[#F5F5F7]"
          >
            {showSecrets ? (
              <>
                <EyeOff className="w-3.5 h-3.5" />
                <span>Hide keys</span>
              </>
            ) : (
              <>
                <Eye className="w-3.5 h-3.5" />
                <span>Show keys</span>
              </>
            )}
          </button>
        </div>

        <div className="space-y-2.5 text-xs">
          <div className="grid grid-cols-3 items-center gap-3">
            <label className="text-[#A1A1A6] font-medium text-xs">
              AcoustID API key
            </label>
            <input
              type={showSecrets ? "text" : "password"}
              placeholder="Required for Chromaprint waveform lookup"
              value={settings.ACOUSTID_API_KEY}
              onChange={(e) =>
                setSettings({ ...settings, ACOUSTID_API_KEY: e.target.value })
              }
              className="col-span-2 px-3 py-1.5 rounded-lg bg-black/40 border border-white/[0.08] text-[#F5F5F7] font-mono text-xs focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF]"
            />
          </div>

          <div className="grid grid-cols-3 items-center gap-3">
            <label className="text-[#A1A1A6] font-medium text-xs">
              Spotify client ID
            </label>
            <input
              type="text"
              placeholder="Optional — falls back to Apple Music and Deezer"
              value={settings.SPOTIFY_CLIENT_ID}
              onChange={(e) =>
                setSettings({ ...settings, SPOTIFY_CLIENT_ID: e.target.value })
              }
              className="col-span-2 px-3 py-1.5 rounded-lg bg-black/40 border border-white/[0.08] text-[#F5F5F7] font-mono text-xs focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF]"
            />
          </div>

          <div className="grid grid-cols-3 items-center gap-3">
            <label className="text-[#A1A1A6] font-medium text-xs">
              Spotify client secret
            </label>
            <input
              type={showSecrets ? "text" : "password"}
              placeholder="Optional Spotify secret"
              value={settings.SPOTIFY_CLIENT_SECRET}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  SPOTIFY_CLIENT_SECRET: e.target.value,
                })
              }
              className="col-span-2 px-3 py-1.5 rounded-lg bg-black/40 border border-white/[0.08] text-[#F5F5F7] font-mono text-xs focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF]"
            />
          </div>

          <div className="grid grid-cols-3 items-center gap-3">
            <label className="text-[#A1A1A6] font-medium text-xs">
              Discogs token
            </label>
            <input
              type={showSecrets ? "text" : "password"}
              placeholder="Optional Discogs personal token"
              value={settings.DISCOGS_TOKEN || ""}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  DISCOGS_TOKEN: e.target.value,
                })
              }
              className="col-span-2 px-3 py-1.5 rounded-lg bg-black/40 border border-white/[0.08] text-[#F5F5F7] font-mono text-xs focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF]"
            />
          </div>

          <div className="grid grid-cols-3 items-center gap-3">
            <label className="text-[#A1A1A6] font-medium text-xs">
              Songlink API key
            </label>
            <input
              type={showSecrets ? "text" : "password"}
              placeholder="Optional Songlink / Odesli API key"
              value={settings.SONGLINK_API_KEY || ""}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  SONGLINK_API_KEY: e.target.value,
                })
              }
              className="col-span-2 px-3 py-1.5 rounded-lg bg-black/40 border border-white/[0.08] text-[#F5F5F7] font-mono text-xs focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF]"
            />
          </div>
        </div>
      </div>

      {/* Engine Parameters Group */}
      <div className="p-4 rounded-2xl glass-panel space-y-3">
        <div className="flex items-center space-x-2 border-b border-white/[0.08] pb-2.5">
          <Sliders className="w-4 h-4 text-[#0A84FF]" />
          <h4 className="text-xs font-semibold text-[#F5F5F7]">
            Engine and network parameters
          </h4>
        </div>

        <div className="space-y-2.5 text-xs tabular-nums">
          <div className="grid grid-cols-3 items-center gap-3">
            <label className="text-[#A1A1A6] font-medium text-xs">
              MusicBrainz User-Agent
            </label>
            <input
              type="text"
              value={settings.MUSICBRAINZ_USER_AGENT}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  MUSICBRAINZ_USER_AGENT: e.target.value,
                })
              }
              className="col-span-2 px-3 py-1.5 rounded-lg bg-black/40 border border-white/[0.08] text-[#F5F5F7] font-mono text-xs focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF]"
            />
          </div>

          <div className="grid grid-cols-3 items-center gap-3">
            <label className="text-[#A1A1A6] font-medium text-xs">
              Chromaprint binary (`fpcalc`)
            </label>
            <input
              type="text"
              value={settings.FPCALC_PATH}
              onChange={(e) =>
                setSettings({ ...settings, FPCALC_PATH: e.target.value })
              }
              className="col-span-2 px-3 py-1.5 rounded-lg bg-black/40 border border-white/[0.08] text-[#F5F5F7] font-mono text-xs focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF]"
            />
          </div>

          <div className="grid grid-cols-3 items-center gap-3">
            <label className="text-[#A1A1A6] font-medium text-xs">
              Minimum artwork size (px)
            </label>
            <input
              type="number"
              step="100"
              value={settings.COVER_ART_MIN_RESOLUTION}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  COVER_ART_MIN_RESOLUTION: parseInt(e.target.value, 10) || 600,
                })
              }
              className="col-span-2 px-3 py-1.5 rounded-lg bg-black/40 border border-white/[0.08] text-[#F5F5F7] tabular-nums text-xs focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF]"
            />
          </div>

          <div className="grid grid-cols-3 items-center gap-3">
            <label className="text-[#A1A1A6] font-medium text-xs">
              Default confidence (0.4 – 0.95)
            </label>
            <input
              type="number"
              step="0.05"
              min="0.4"
              max="0.95"
              value={settings.CONFIDENCE_THRESHOLD}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  CONFIDENCE_THRESHOLD: parseFloat(e.target.value) || 0.7,
                })
              }
              className="col-span-2 px-3 py-1.5 rounded-lg bg-black/40 border border-white/[0.08] text-[#F5F5F7] tabular-nums text-xs focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF]"
            />
          </div>

          <div className="grid grid-cols-3 items-center gap-3">
            <label className="text-[#A1A1A6] font-medium text-xs">
              Rate limit / timeout (sec)
            </label>
            <div className="col-span-2 grid grid-cols-2 gap-3">
              <input
                type="number"
                step="0.2"
                min="0.0"
                value={settings.RATE_LIMIT_DELAY}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    RATE_LIMIT_DELAY: parseFloat(e.target.value) || 1.0,
                  })
                }
                className="px-3 py-1.5 rounded-lg bg-black/40 border border-white/[0.08] text-[#F5F5F7] tabular-nums text-xs focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF]"
              />
              <input
                type="number"
                step="1.0"
                min="5.0"
                value={settings.REQUEST_TIMEOUT}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    REQUEST_TIMEOUT: parseFloat(e.target.value) || 15.0,
                  })
                }
                className="px-3 py-1.5 rounded-lg bg-black/40 border border-white/[0.08] text-[#F5F5F7] tabular-nums text-xs focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF]"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Save Action */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSave}
          disabled={loading}
          className="apple-btn-primary flex items-center space-x-2 px-5 py-2 rounded-lg text-white text-xs font-semibold"
        >
          <Save className="w-3.5 h-3.5" />
          <span>Save settings</span>
        </button>
      </div>
    </div>
  );
};
