"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain } from "lucide-react";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import { navItems } from "@/lib/nav";
import { DashboardMotion } from "@/components/dashboard-motion";

const groups: { key: "main" | "data" | "ops"; label: string }[] = [
  { key: "main", label: "监控" },
  { key: "data", label: "数据" },
  { key: "ops", label: "运维" },
];

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen bg-[#f6f7f9] text-foreground">
      <aside className="hidden w-60 shrink-0 border-r border-border/80 bg-white shadow-sm md:flex md:flex-col">
        <div className="flex items-center gap-2 px-4 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-600/10">
            <Brain className="h-5 w-5 text-emerald-700" />
          </div>
          <div>
            <p className="text-sm font-semibold tracking-tight">Opinion Trading</p>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
              Next 工作台
            </p>
          </div>
        </div>
        <Separator />
        <nav className="flex flex-1 flex-col gap-4 overflow-y-auto p-2">
          {groups.map((g) => (
            <div key={g.key}>
              <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {g.label}
              </p>
              <div className="flex flex-col gap-0.5">
                {navItems
                  .filter((n) => n.group === g.key)
                  .map((item) => {
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
                          "group flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition-all duration-200",
                          "hover:bg-emerald-50 hover:text-emerald-900 hover:shadow-sm",
                          active
                            ? "bg-emerald-600/10 font-medium text-emerald-900 shadow-sm ring-1 ring-emerald-600/15"
                            : "text-muted-foreground",
                        )}
                      >
                        <Icon
                          className={cn(
                            "h-4 w-4 shrink-0 transition-transform group-hover:scale-110",
                            active && "text-emerald-700",
                          )}
                        />
                        <span>{item.labelZh}</span>
                      </Link>
                    );
                  })}
              </div>
            </div>
          ))}
        </nav>
        <p className="border-t border-border/60 p-3 text-[10px] leading-relaxed text-muted-foreground">
          主界面 · Streamlit 已弃用 · 浅色主题
        </p>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border/80 bg-white/90 px-4 py-3 backdrop-blur md:hidden">
          <span className="text-sm font-semibold">Opinion Trading</span>
          <select
            className="max-w-[55%] rounded-lg border border-border bg-card px-2 py-1.5 text-xs shadow-sm"
            value={pathname}
            onChange={(e) => {
              window.location.href = e.target.value;
            }}
          >
            {navItems.map((n) => (
              <option key={n.href} value={n.href}>
                {n.labelZh}
              </option>
            ))}
          </select>
        </header>
        <main className="flex-1 overflow-auto p-4 md:p-8">
          <div className="mx-auto max-w-6xl">
            <DashboardMotion>{children}</DashboardMotion>
          </div>
        </main>
      </div>
    </div>
  );
}
