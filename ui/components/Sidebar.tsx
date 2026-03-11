"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  FileSearch,
  Users,
  FileUp,
  Activity,
  ChevronRight,
  Briefcase,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/requisitions", label: "Requisitions", icon: FileSearch },
  { href: "/team-members", label: "Team Members", icon: Users },
  { href: "/resumes", label: "Resume Ingestion", icon: FileUp },
  { href: "/system", label: "System Health", icon: Activity },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-slate-200 bg-white">
      {/* Logo */}
      <div className="flex h-16 shrink-0 items-center gap-3 border-b border-slate-100 px-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-sm">
          <Briefcase className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-900">IB Skill Mapper</p>
          <p className="text-xs text-slate-500">AI Matching System</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-4">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-indigo-50 text-indigo-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              )}
            >
              <Icon className={cn("h-4 w-4", active ? "text-indigo-600" : "text-slate-400")} />
              {label}
              {active && <ChevronRight className="ml-auto h-4 w-4 text-indigo-400" />}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-slate-100 p-4">
        <p className="text-xs text-slate-400">v0.1.0 · InfoBeans</p>
      </div>
    </aside>
  );
}
