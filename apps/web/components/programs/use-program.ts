"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Program } from "@/lib/types";

/** Loads a program. Re-runs when a page hidden by Next.js (Activity) becomes visible again. */
export function useProgram(id: string) {
  const [program, setProgram] = useState<Program | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<Program>(`/api/programs/${id}`)
      .then((p) => !cancelled && setProgram(p))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [id]);

  return { program, setProgram, error };
}
