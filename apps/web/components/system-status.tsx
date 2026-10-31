"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { StatusBadge } from "@/components/ui/status-badge";

type Ready = { status: string; database: string };

export function SystemStatus() {
  const [api, setApi] = useState<boolean | null>(null);
  const [db, setDb] = useState<boolean | null>(null);

  useEffect(() => {
    apiFetch<Ready>("/api/health/ready")
      .then((r) => {
        setApi(true);
        setDb(r.database === "ok");
      })
      .catch(() => {
        setApi(false);
        setDb(false);
      });
  }, []);

  return (
    <div className="flex flex-wrap gap-3">
      <StatusBadge ok={api} label="سرور" />
      <StatusBadge ok={db} label="پایگاه داده" />
    </div>
  );
}
