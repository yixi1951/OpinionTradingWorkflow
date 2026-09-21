import { DashboardShell } from "@/components/dashboard-shell";
import { Toaster } from "@/components/ui/sonner";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <DashboardShell>
      {children}
      <Toaster richColors position="top-right" />
    </DashboardShell>
  );
}
