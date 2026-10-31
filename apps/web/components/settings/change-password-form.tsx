"use client";

import { useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";

const MIN_LENGTH = 10;

export function ChangePasswordForm() {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formEl = e.currentTarget;
    const form = new FormData(formEl);
    const current = String(form.get("current") ?? "");
    const next = String(form.get("next") ?? "");
    const confirm = String(form.get("confirm") ?? "");

    if (next.length < MIN_LENGTH) return setError(`رمز جدید باید حداقل ${MIN_LENGTH.toLocaleString("fa-IR")} کاراکتر باشد.`);
    if (next !== confirm) return setError("تکرار رمز جدید با آن یکسان نیست.");

    setPending(true);
    setError(null);
    try {
      await apiFetch("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      formEl.reset();
      toast.success("رمز عبور تغییر کرد. نشست‌های دیگر خارج شدند.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPending(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>تغییر رمز عبور</CardTitle>
        <CardDescription>پس از تغییر، همه دستگاه‌های دیگر از حساب خارج می‌شوند.</CardDescription>
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
            <Label htmlFor="current">رمز فعلی</Label>
            <Input id="current" name="current" type="password" autoComplete="current-password" dir="ltr" required />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="next">رمز جدید</Label>
            <Input id="next" name="next" type="password" autoComplete="new-password" dir="ltr" required />
            <p className="text-xs text-muted-foreground">حداقل {MIN_LENGTH.toLocaleString("fa-IR")} کاراکتر</p>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="confirm">تکرار رمز جدید</Label>
            <Input id="confirm" name="confirm" type="password" autoComplete="new-password" dir="ltr" required />
          </div>
          <Button type="submit" disabled={pending} className="self-start">
            {pending && <Loader2 className="animate-spin" aria-hidden />}
            ذخیره رمز جدید
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
