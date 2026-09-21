"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Brain,
  ChartLine,
  History,
  LayoutDashboard,
  LineChart,
  PlayCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";

const nav = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/picks", label: "Picks", icon: ChartLine },
  { href: "/sentiment", label: "Sentiment", icon: LineChart },
  { href: "/eval", label: "Eval", icon: Activity },
  { href: "/memory", label: "Memory", icon: History },
  { href: "/run", label: "Run daily", icon: PlayCircle },
];

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-56 shrink-0 border-r border-border bg-sidebar md:flex md:flex-col">
        <div className="flex items-center gap-2 px-4 py-5">
          <Brain className="h-5 w-5 text-emerald-400" />
          <div>
            <p className="text-sm font-semibold tracking-tight">Opinion Trading</p>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
              Workflow
            </p>
          </div>
        </div>
        <Separator />
        <nav className="flex flex-1 flex-col gap-0.5 p-2">
          {nav.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <p className="p-3 text-[10px] leading-relaxed text-muted-foreground">
          Next.js dashboard · API-backed · Streamlit deprecated for primary UI
        </p>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border px-4 py-3 md:hidden">
          <span className="text-sm font-semibold">Opinion Trading</span>
          <select
            className="rounded-md border border-border bg-card px-2 py-1 text-xs"
            value={pathname}
            onChange={(e) => {
              window.location.href = e.target.value;
            }}
          >
            {nav.map((n) => (
              <option key={n.href} value={n.href}>{n.label}</option>
            ))}
          </select>
        </header>
        <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
