import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Bell,
  Bot,
  ChartLine,
  ClipboardCheck,
  Eye,
  History,
  LayoutDashboard,
  LineChart,
  MessageSquareText,
  PlayCircle,
  Sparkles,
  Star,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  labelZh: string;
  icon: LucideIcon;
  group?: "main" | "data" | "ops";
};

export const navItems: NavItem[] = [
  { href: "/", label: "Overview", labelZh: "总览", icon: LayoutDashboard, group: "main" },
  { href: "/watchlist", label: "Watchlist", labelZh: "自选股", icon: Star, group: "main" },
  { href: "/alerts", label: "Alerts", labelZh: "信号预警", icon: Bell, group: "main" },
  { href: "/review", label: "Review", labelZh: "舆情复盘", icon: ClipboardCheck, group: "main" },
  { href: "/ai", label: "AI pipeline", labelZh: "AI 筛选", icon: Sparkles, group: "data" },
  { href: "/picks", label: "Picks", labelZh: "选股", icon: ChartLine, group: "data" },
  { href: "/openclaw", label: "OpenClaw", labelZh: "OpenClaw", icon: Bot, group: "data" },
  { href: "/sentiment", label: "Sentiment", labelZh: "舆情", icon: LineChart, group: "data" },
  { href: "/comments", label: "Comments", labelZh: "评论依据", icon: MessageSquareText, group: "data" },
  { href: "/eval", label: "Eval", labelZh: "评估", icon: Activity, group: "data" },
  { href: "/analyst", label: "Analyst", labelZh: "分析师", icon: Eye, group: "data" },
  { href: "/memory", label: "Memory", labelZh: "记忆", icon: History, group: "ops" },
  { href: "/run", label: "Run daily", labelZh: "运行", icon: PlayCircle, group: "ops" },
];

export function navTitle(pathname: string): NavItem | undefined {
  if (pathname === "/") return navItems[0];
  return navItems.find((n) => n.href !== "/" && pathname.startsWith(n.href));
}
