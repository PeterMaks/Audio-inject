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
    <aside className="w-58 flex flex-col justify-between border-r border-white/[0.08] bg-[#161618]/85 backdrop-blur-2xl px-3 py-4 select-none shrink-0 z-40">
      <div className="space-y-5">
        {sections.map((section) => (
          <div key={section.heading} className="space-y-1">
            <div className="px-2.5 pb-1 text-[11px] font-semibold tracking-wider text-[#8E8E93] uppercase">
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
                  className={`relative w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    isActive
                      ? "text-[#FFFFFF]"
                      : "text-[#8E8E93] hover:text-[#FFFFFF]"
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
                      className="absolute inset-0 rounded-lg bg-white/[0.12] border border-white/[0.08] shadow-sm"
                    />
                  )}

                  <div className="relative z-10 flex items-center space-x-2.5 truncate">
                    <Icon
                      className={`w-4 h-4 shrink-0 transition-colors ${
                        isActive ? "text-[#007AFF]" : "text-[#8E8E93]"
                      }`}
                    />
                    <span className="truncate">{item.label}</span>
                  </div>

                  {item.badge && (
                    <span
                      className={`relative z-10 px-2 py-0.5 rounded-full text-[11px] tabular-nums font-semibold shrink-0 ml-1.5 ${
                        item.badgeTone === "accent"
                          ? "bg-[#FF3B30]/20 text-[#FF6961] border border-[#FF3B30]/30"
                          : item.badgeTone === "amber"
                            ? "bg-[#FF9500]/20 text-[#FF9500] border border-[#FF9500]/30"
                            : "bg-white/[0.08] text-[#FFFFFF] border border-white/[0.08]"
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

      {/* Concentric Engine Specs Card */}
      <div className="p-3 rounded-xl surface-elevated space-y-1.5">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-[#8E8E93]">Audio engine</span>
          <span className="text-[#FFFFFF] font-medium">Bit-perfect PCM</span>
        </div>
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-[#8E8E93]">Artwork master</span>
          <span className="text-[#FFFFFF] font-medium tabular-nums">
            3000 × 3000 px
          </span>
        </div>
      </div>
    </aside>
  );
});
