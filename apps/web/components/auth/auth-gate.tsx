"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import { useAuth } from "./auth-provider";
import { Alert, AlertDescription } from "@/components/ui/alert";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading, error } = useAuth();
  if (loading || (!user && !error)) {
    return (
      <div className="flex flex-1 items-center justify-center py-24 text-muted-foreground" role="status">
        <Loader2 className="size-6 animate-spin" aria-hidden />
        <span className="sr-only">در حال بارگذاری</span>
      </div>
    );
  }
  if (!user) {
    return (
      <div className="mx-auto w-full max-w-md py-24">
        <Alert variant="destructive">
          <AlertCircle aria-hidden />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }
  return <>{children}</>;
}
