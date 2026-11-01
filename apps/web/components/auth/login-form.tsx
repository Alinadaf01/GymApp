"use client";

import { useState } from "react";
import { AlertCircle, Dumbbell, Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch, safeNextPath } from "@/lib/api";

export function LoginForm() {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setPending(true);
    setError(null);
    try {
      await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: form.get("username"), password: form.get("password") }),
      });
      const next = new URLSearchParams(window.location.search).get("next");
      window.location.assign(safeNextPath(next));
    } catch (err) {
      setError((err as Error).message);
      setPending(false);
    }
  }

  return (
    <Card className="w-full max-w-sm">
      <CardHeader className="items-center text-center">
        <span className="mb-2 flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <Dumbbell className="size-6" aria-hidden />
        </span>
        <CardTitle className="text-xl">ورود به پنل مربی</CardTitle>
        <CardDescription>Basharnia Coach CRM</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          {error && (
            <Alert variant="destructive">
              <AlertCircle aria-hidden />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="flex flex-col gap-2">
            <Label htmlFor="username">نام کاربری</Label>
            <Input
              id="username"
              name="username"
              autoComplete="username"
              dir="ltr"
              required
              autoFocus
              aria-invalid={!!error}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="password">رمز عبور</Label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              dir="ltr"
              required
              aria-invalid={!!error}
            />
          </div>
          <Button type="submit" size="lg" disabled={pending} className="mt-2">
            {pending && <Loader2 className="animate-spin" aria-hidden />}
            ورود
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
