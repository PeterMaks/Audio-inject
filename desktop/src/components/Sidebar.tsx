import React from "react";
import {
  FolderSearch,
  Sparkles,
  FileAudio,
  Disc,
  Settings,
} from "lucide-react";

export type ActiveTab = "scan" | "inject" | "inspect" | "convert" | "settings";

interface SidebarProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  scannedCount: number;
  incompleteCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onTabChange,
  scannedCount,
  incompleteCount,
}) => {
  const sections = [
    {
      heading: "Library",
      items: [
        {
          id: "scan" as ActiveTab,
          label: "All Tracks",
          icon: FolderSearch,
          badge: scannedCount > 0 ? `${scannedCount}` : undefined,
          badgeTone: "neutral",
        },
        {
          id: "inspect" as ActiveTab,
          label: "Track Inspector",
          icon: FileAudio,
        },
      ],
    },
    {
      heading: "Mastering & Tagging",
      items: [
        {
          id: "inject" as ActiveTab,
          label: "Waterfall Injector",
          icon: Sparkles,
          badge: incompleteCount > 0 ? `${incompleteCount}` : undefined,
          badgeTone: "accent",
        },
        {
          id: "convert" as ActiveTab,
          label: "WAV to FLAC",
          icon: Disc,
        },
      ],
    },
    {
      heading: "Preferences",
      items: [
        {
          id: "settings" as ActiveTab,
          label: "Engine & API Keys",
          icon: Settings,
        },
      ],
    },
  ];

  return (
    <aside className="w-60 flex flex-col justify-between border-r border-white/[0.07] bg-[#121217]/55 backdrop-blur-2xl px-3 py-4 select-none shrink-0 z-40">
      <div className="space-y-6">
        {sections.map((section) => (
          <div key={section.heading} className="space-y-1">
            <div className="px-3 pb-1 text-[11px] font-semibold tracking-wide text-white/35 uppercase">
              {section.heading}
            </div>
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onTabChange(item.id)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-150 ${isActive
                      ? "bg-white/[0.12] text-white shadow-sm"
                      : "text-white/60 hover:text-white/90 hover:bg-white/[0.05]"
                    }`}
                >
                  <div className="flex items-center space-x-2.5">
                    <Icon
                      className={`w-4 h-4 ${isActive ? "text-[#0A84FF]" : "text-white/50"
                        }`}
                    />
                    <span>{item.label}</span>
                  </div>

                  {item.badge && (
                    <span
                      className={`px-2 py-0.5 rounded-full text-[11px] tabular-nums font-medium ${item.badgeTone === "accent"
                          ? "bg-[#FF453A]/20 text-[#FF6961]"
                          : "bg-white/[0.08] text-white/70"
                        }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* Apple Music Style Lossless Spec Footer */}
      <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-1.5">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-white/40">Audio Engine</span>
          <span className="text-white/80 font-medium">Bit-Perfect</span>
        </div>
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-white/40">Artwork CDN</span>
          <span className="text-white/80 font-medium tabular-nums">
            3000 × 3000 px
          </span>
        </div>
      </div>
    </aside>
  );
};