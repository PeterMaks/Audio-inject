import React from "react";
import { motion } from "framer-motion";
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
  wavCount: number;
}

export const Sidebar: React.FC<SidebarProps> = React.memo(function Sidebar({
  activeTab,
  onTabChange,
  scannedCount,
  incompleteCount,
  wavCount,
}) {
  const sections = [
    {
      heading: "Library",
      items: [
        {
          id: "scan" as ActiveTab,
          label: "All tracks",
          icon: FolderSearch,
          badge: scannedCount > 0 ? `${scannedCount}` : undefined,
          badgeTone: "neutral",
        },
        {
          id: "inspect" as ActiveTab,
          label: "Track inspector",
          icon: FileAudio,
        },
      ],
    },
    {
      heading: "Mastering & Tagging",
      items: [
        {
          id: "inject" as ActiveTab,
          label: "Waterfall injector",
          icon: Sparkles,
          badge: incompleteCount > 0 ? `${incompleteCount}` : undefined,
          badgeTone: "accent",
        },
        {
          id: "convert" as ActiveTab,
          label: "WAV to FLAC",
          icon: Disc,
          badge: wavCount > 0 ? `${wavCount}` : undefined,
          badgeTone: "amber",
        },
      ],
    },
    {
      heading: "Preferences",
      items: [
        {
          id: "settings" as ActiveTab,
          label: "Settings",
          icon: Settings,
        },
      ],
    },
  ];

  return (
    <aside className="w-56 flex flex-col justify-between border-r border-white/[0.08] bg-[#181818] px-3 py-4 select-none shrink-0 z-40">
      <div className="space-y-5">
        {sections.map((section) => (
          <div key={section.heading} className="space-y-1">
            <div className="px-2.5 pb-1 text-xs font-semibold tracking-wider text-[#6E6E73] uppercase">
              {section.heading}
            </div>
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onTabChange(item.id)}
                  className={`relative w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "text-[#FFFFFF]"
                      : "text-[#A1A1A6] hover:text-[#F5F5F7]"
                  }`}
                >
                  {isActive && (
                    <motion.div
                      layoutId="sidebar-active-pill"
                      transition={{
                        type: "spring",
                        duration: 0.24,
                        bounce: 0,
                      }}
                      className="absolute inset-0 rounded-lg bg-white/[0.1] border border-white/[0.08] shadow-sm"
                    />
                  )}

                  <div className="relative z-10 flex items-center space-x-2.5 truncate">
                    <Icon
                      className={`w-4 h-4 shrink-0 transition-colors ${
                        isActive ? "text-[#0A84FF]" : "text-[#A1A1A6]"
                      }`}
                    />
                    <span className="truncate">{item.label}</span>
                  </div>

                  {item.badge && (
                    <span
                      className={`relative z-10 px-2 py-0.5 rounded-full text-xs tabular-nums font-semibold shrink-0 ml-1.5 ${
                        item.badgeTone === "accent"
                          ? "bg-[#FF453A]/20 text-[#FF6961]"
                          : item.badgeTone === "amber"
                            ? "bg-[#FF9F0A]/20 text-[#FF9F0A]"
                            : "bg-white/[0.08] text-[#F5F5F7]"
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

      {/* Concentric Engine Specs Card: Outer rounded-xl (12px), p-3 (12px) */}
      <div className="p-3 rounded-xl surface-elevated space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-[#A1A1A6]">Audio engine</span>
          <span className="text-[#F5F5F7] font-medium">Bit-perfect PCM</span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-[#A1A1A6]">Artwork master</span>
          <span className="text-[#F5F5F7] font-medium tabular-nums">
            3000 × 3000 px
          </span>
        </div>
      </div>
    </aside>
  );
});
