"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { User } from "@/lib/types";

type AuthState = { user: User | null; loading: boolean; error: string | null };

const AuthContext = createContext<AuthState>({ user: null, loading: true, error: null });

export function useAuth() {
  return useContext(AuthContext);
}

/** Loads the current coach; apiFetch redirects to /login on 401. */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    apiFetch<User>("/api/auth/me")
      .then((user) => !cancelled && setState({ user, loading: false, error: null }))
      .catch((e: Error) => !cancelled && setState({ user: null, loading: false, error: e.message }));
    return () => {
      cancelled = true;
    };
  }, []);

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}
