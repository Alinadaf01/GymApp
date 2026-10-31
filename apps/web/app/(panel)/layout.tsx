import { AuthGate } from "@/components/auth/auth-gate";
import { AuthProvider } from "@/components/auth/auth-provider";
import { Sidebar } from "@/components/layout/sidebar";

export default function PanelLayout({ children }: LayoutProps<"/">) {
  return (
    <AuthProvider>
      <div className="flex min-h-svh flex-col lg:flex-row">
        <Sidebar />
        <main className="flex min-w-0 flex-1 flex-col px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
          <AuthGate>{children}</AuthGate>
        </main>
      </div>
    </AuthProvider>
  );
}
