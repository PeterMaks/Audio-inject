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

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onTabChange,
  scannedCount,
  incompleteCount,
  wavCount,
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
          label: "Engine & API Keys",
          icon: Settings,
        },
      ],
    },
  ];

  return (
    <aside className="w-60 flex flex-col justify-between border-r border-white/[0.08] bg-[#141416]/65 backdrop-blur-xl px-3 py-4 select-none shrink-0 z-40">
      <div className="space-y-6">
        {sections.map((section) => (
          <div key={section.heading} className="space-y-1">
            <div className="px-3 pb-1 text-[11px] font-semibold tracking-wider text-[#86868B] uppercase">
              {section.heading}
            </div>
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onTabChange(item.id)}
                  className={`relative w-full flex items-center justify-between px-3 py-2 rounded-[10px] text-[13px] font-medium transition-colors duration-150 active:scale-[0.98] ${
                    isActive
                      ? "text-[#F5F5F7]"
                      : "text-[#86868B] hover:text-[#F5F5F7]"
                  }`}
                >
                  {isActive && (
                    <motion.div
                      layoutId="sidebar-active-pill"
                      transition={{
                        type: "spring",
                        duration: 0.3,
                        bounce: 0,
                      }}
                      className="absolute inset-0 rounded-[10px] bg-white/[0.11] border border-white/[0.08] shadow-sm"
                    />
                  )}

                  <div className="relative z-10 flex items-center space-x-2.5">
                    <Icon
                      className={`w-4 h-4 transition-colors duration-150 ${
                        isActive ? "text-[#0A84FF]" : "text-[#86868B]"
                      }`}
                    />
                    <span>{item.label}</span>
                  </div>

                  {item.badge && (
                    <span
                      className={`relative z-10 px-2 py-0.5 rounded-full text-[11px] tabular-nums font-semibold ${
                        item.badgeTone === "accent"
                          ? "bg-[#FF453A]/20 text-[#FF6961]"
                          : item.badgeTone === "amber"
                            ? "bg-[#FF9F0A]/20 text-[#FF9F0A]"
                            : "bg-white/[0.08] text-[#F5F5F7]/80"
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

      {/* Concentric Spec Card: Outer rounded-[16px] p-3, Inner Spec Rows */}
      <div className="p-3 rounded-[16px] surface-elevated space-y-1.5">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-[#86868B]">Audio Engine</span>
          <span className="text-[#F5F5F7]/90 font-medium">Bit-Perfect PCM</span>
        </div>
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-[#86868B]">Artwork CDN</span>
          <span className="text-[#F5F5F7]/90 font-medium tabular-nums">
            3000 × 3000 px
          </span>
        </div>
      </div>
    </aside>
  );
};