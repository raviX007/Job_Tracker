"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Briefcase,
  ClipboardCheck,
  Mail,
  BarChart3,
  Table,
  Play,
  Rocket,
  Settings,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/applications", label: "Applications", icon: Briefcase },
  { href: "/outcomes", label: "Update Outcomes", icon: ClipboardCheck, hideInDemo: true },
  { href: "/emails", label: "Cold Emails", icon: Mail },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/tracker", label: "Tracker", icon: Table },
  { href: "/pipeline", label: "Pipeline Runner", icon: Play, hideInDemo: true },
  { href: "/startups", label: "Startup Scout", icon: Rocket },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const isDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

  const filteredItems = isDemoMode
    ? NAV_ITEMS.filter((item) => !item.hideInDemo)
    : NAV_ITEMS;

  function handleSignOut() {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_username");
    localStorage.removeItem("job-tracker-profile-id");
    document.cookie = "auth_token=; path=/; max-age=0";
    window.location.href = "/login";
  }

  return (
    <div className="flex h-full flex-col bg-gradient-to-b from-[#0f1b2d] to-[#1e3a5f]">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/20">
          <Briefcase className="h-5 w-5 text-accent" />
        </div>
        <span className="text-lg font-bold text-white">Job Tracker</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-2">
        {filteredItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all",
                isActive
                  ? "border-l-3 border-accent bg-accent/15 text-white"
                  : "text-gray-300 hover:bg-white/10 hover:text-white",
              )}
            >
              <Icon className="h-4.5 w-4.5 shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Sign Out */}
      <div className="border-t border-white/10 px-3 py-4">
        <button
          onClick={handleSignOut}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-gray-300 transition-all hover:bg-white/10 hover:text-white"
        >
          <LogOut className="h-4.5 w-4.5 shrink-0" />
          Sign Out
        </button>
      </div>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 z-40 hidden h-screen w-64 lg:block">
      <SidebarContent />
    </aside>
  );
}
