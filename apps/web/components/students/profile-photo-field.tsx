"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ImagePlus, Trash2, Undo2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StudentAvatar } from "./student-avatar";

export const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_MB = 20;

export type PhotoChange =
  | { kind: "none" }
  | { kind: "upload"; file: File; consent: boolean }
  | { kind: "remove" };

/** Pick / preview / remove a profile photo. The actual upload happens on form submit. */
export function ProfilePhotoField({
  name,
  currentUrl,
  consentRecorded,
  value,
  onChange,
  error,
}: {
  name: string;
  currentUrl: string | null;
  consentRecorded: boolean;
  value: PhotoChange;
  onChange: (v: PhotoChange) => void;
  error?: string | null;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const consentId = useId();
  const [localError, setLocalError] = useState<string | null>(null);

  const file = value.kind === "upload" ? value.file : null;
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  function pick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      setLocalError("فقط تصویر JPG، PNG یا WEBP قابل قبول است.");
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setLocalError(`حجم تصویر نباید بیش از ${MAX_MB.toLocaleString("fa-IR")} مگابایت باشد.`);
      return;
    }
    setLocalError(null);
    onChange({ kind: "upload", file, consent: consentRecorded });
  }

  const shownUrl = value.kind === "remove" ? null : currentUrl;
  const message = localError ?? error;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-4">
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview} alt="پیش‌نمایش تصویر" className="size-20 shrink-0 rounded-full object-cover" />
        ) : (
          <StudentAvatar name={name || "؟"} photoUrl={shownUrl} size="lg" />
        )}
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
            <ImagePlus aria-hidden />
            {currentUrl || preview ? "تغییر تصویر" : "انتخاب تصویر"}
          </Button>
          {value.kind === "upload" && (
            <Button type="button" variant="ghost" size="sm" onClick={() => onChange({ kind: "none" })}>
              <Undo2 aria-hidden />
              انصراف
            </Button>
          )}
          {value.kind === "none" && currentUrl && (
            <Button type="button" variant="ghost" size="sm" onClick={() => onChange({ kind: "remove" })}>
              <Trash2 aria-hidden />
              حذف تصویر
            </Button>
          )}
          {value.kind === "remove" && (
            <Button type="button" variant="ghost" size="sm" onClick={() => onChange({ kind: "none" })}>
              <Undo2 aria-hidden />
              بازگرداندن
            </Button>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_IMAGE_TYPES.join(",")}
          className="sr-only"
          tabIndex={-1}
          aria-label="فایل تصویر پروفایل"
          onChange={pick}
        />
      </div>

      {value.kind === "remove" && <p className="text-sm text-muted-foreground">تصویر پس از ذخیره حذف می‌شود.</p>}

      {value.kind === "upload" && !consentRecorded && (
        <label htmlFor={consentId} className="flex items-start gap-2 text-sm leading-6">
          <input
            id={consentId}
            type="checkbox"
            className="mt-1 size-4 accent-primary"
            checked={value.consent}
            onChange={(e) => onChange({ ...value, consent: e.target.checked })}
          />
          رضایت شاگرد برای ثبت و نگهداری تصویر گرفته شده است.
        </label>
      )}

      {message && (
        <p className="text-sm text-destructive" role="alert">
          {message}
        </p>
      )}
    </div>
  );
}
