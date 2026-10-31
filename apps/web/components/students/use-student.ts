"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Student } from "@/lib/types";

export function useStudent(id: string) {
  const [student, setStudent] = useState<Student | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<Student>(`/api/students/${id}`)
      .then((s) => !cancelled && setStudent(s))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [id]);

  return { student, setStudent, error };
}
