"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { navTitle } from "@/lib/nav";

export function PageChrome({
  title,
  description,
  children,
  actions,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  const pathname = usePathname();
  const crumb = navTitle(pathname);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-6 motion-reduce:transform-none"
    >
      <nav className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
        <Link href="/" className="transition-colors hover:text-foreground">
          工作台
        </Link>
        {crumb && crumb.href !== "/" && (
          <>
            <ChevronRight className="h-3 w-3" />
            <span className="text-foreground">{crumb.labelZh}</span>
          </>
        )}
      </nav>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {description && (
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{description}</p>
          )}
        </div>
        {actions}
      </div>
      {children}
    </motion.div>
  );
}
