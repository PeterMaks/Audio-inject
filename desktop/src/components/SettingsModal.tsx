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
        setSettings(data);
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
      setSettings(updated);
      onSaved?.();
    } catch (e) {
      console.error("Failed to save settings:", e);
    }
  };

  return (
    <div className="flex flex-col h-full space-y-5 overflow-y-auto pr-1 max-w-3xl">
      {/* Credentials Group */}
      <div className="p-5 rounded-2xl glass-panel space-y-4">
        <div className="flex items-center justify-between border-b border-white/[0.07] pb-3">
          <div className="flex items-center space-x-2">
            <Key className="w-4 h-4 text-[#0A84FF]" />
            <h4 className="text-xs font-semibold text-white">
              Streaming & Acoustic API Credentials
            </h4>
          </div>
          <button
            type="button"
            onClick={() => setShowSecrets(!showSecrets)}
            className="flex items-center space-x-1 text-[11px] text-white/50 hover:text-white"
          >
            {showSecrets ? (
              <>
                <EyeOff className="w-3.5 h-3.5" />
                <span>Hide Keys</span>
              </>
            ) : (
              <>
                <Eye className="w-3.5 h-3.5" />
                <span>Show Keys</span>
              </>
            )}
          </button>
        </div>

        <div className="space-y-3 text-xs">
          <div className="grid grid-cols-3 items-center gap-4">
            <label className="text-white/75 font-medium">AcoustID API Key</label>
            <input
              type={showSecrets ? "text" : "password"}
              placeholder="Required for Chromaprint waveform lookup"
              value={settings.ACOUSTID_API_KEY}
              onChange={(e) =>
                setSettings({ ...settings, ACOUSTID_API_KEY: e.target.value })
              }
              className="col-span-2 px-3 py-2 rounded-xl bg-black/30 border border-white/[0.1] text-white font-mono text-[11px] focus:outline-none focus:border-[#0A84FF]"
            />
          </div>

          <div className="grid grid-cols-3 items-center gap-4">
            <label className="text-white/75 font-medium">Spotify Client ID</label>
            <input
              type="text"
              placeholder="Optional — falls back to Apple iTunes & Deezer"
              value={settings.SPOTIFY_CLIENT_ID}
              onChange={(e) =>
                setSettings({ ...settings, SPOTIFY_CLIENT_ID: e.target.value })
              }
              className="col-span-2 px-3 py-2 rounded-xl bg-black/30 border border-white/[0.1] text-white font-mono text-[11px] focus:outline-none focus:border-[#0A84FF]"
            />
          </div>

          <div className="grid grid-cols-3 items-center gap-4">
            <label className="text-white/75 font-medium">
              Spotify Client Secret
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
              className="col-span-2 px-3 py-2 rounded-xl bg-black/30 border border-white/[0.1] text-white font-mono text-[11px] focus:outline-none focus:border-[#0A84FF]"
            />
          </div>

          <div className="grid grid-cols-3 items-center gap-4">
            <label className="text-white/75 font-medium">Songlink / Odesli API Key</label>
            <input
              type={showSecrets ? "text" : "password"}
              placeholder="Optional Songlink API key"
              value={settings.SONGLINK_API_KEY || ""}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  SONGLINK_API_KEY: e.target.value,
                })
              }
              className="col-span-2 px-3 py-2 rounded-xl bg-black/30 border border-white/[0.1] text-white font-mono text-[11px] focus:outline-none focus:border-[#0A84FF]"
            />
          </div>
        </div>
      </div>

      {/* Engine Parameters Group */}
      <div className="p-5 rounded-2xl glass-panel space-y-4">
        <div className="flex items-center space-x-2 border-b border-white/[0.07] pb-3">
          <Sliders className="w-4 h-4 text-[#0A84FF]" />
          <h4 className="text-xs font-semibold text-white">
            Engine & Network Parameters
          </h4>
        </div>

        <div className="space-y-3 text-xs">
          <div className="grid grid-cols-3 items-center gap-4">
            <label className="text-white/75 font-medium">
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
              className="col-span-2 px-3 py-2 rounded-xl bg-black/30 border border-white/[0.1] text-white font-mono text-[11px] focus:outline-none focus:border-[#0A84FF]"
            />
          </div>

          <div className="grid grid-cols-3 items-center gap-4">
            <label className="text-white/75 font-medium">
              Chromaprint Binary (`fpcalc`)
            </label>
            <input
              type="text"
              value={settings.FPCALC_PATH}
              onChange={(e) =>
                setSettings({ ...settings, FPCALC_PATH: e.target.value })
              }
              className="col-span-2 px-3 py-2 rounded-xl bg-black/30 border border-white/[0.1] text-white font-mono text-[11px] focus:outline-none focus:border-[#0A84FF]"
            />
          </div>

          <div className="grid grid-cols-3 items-center gap-4">
            <label className="text-white/75 font-medium">
              Minimum Artwork Size (px)
            </label>
            <input
              type="number"
              step="100"
              value={settings.COVER_ART_MIN_RESOLUTION}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  COVER_ART_MIN_RESOLUTION: parseInt(e.target.value, 10),
                })
              }
              className="col-span-2 px-3 py-2 rounded-xl bg-black/30 border border-white/[0.1] text-white tabular-nums text-xs focus:outline-none focus:border-[#0A84FF]"
            />
          </div>
        </div>
      </div>

      {/* Save Action */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={loading}
          className="apple-btn-primary flex items-center space-x-2 px-6 py-2.5 rounded-xl text-white text-xs font-semibold"
        >
          <Save className="w-4 h-4" />
          <span>Save Settings</span>
        </button>
      </div>
    </div>
  );
};