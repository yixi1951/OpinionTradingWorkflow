"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

type HoverCardProps = React.ComponentProps<typeof motion.div> & {
  children: React.ReactNode;
  className?: string;
};

export function HoverCard({ children, className, ...rest }: HoverCardProps) {
  return (
    <motion.div
      whileHover={{ y: -2, scale: 1.005 }}
      transition={{ type: "spring", stiffness: 400, damping: 28 }}
      className={cn(
        "rounded-2xl border border-border/80 bg-card shadow-sm transition-shadow duration-300",
        "hover:border-emerald-500/25 hover:shadow-md hover:shadow-emerald-500/5",
        "motion-reduce:transform-none motion-reduce:transition-none",
        className,
      )}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
