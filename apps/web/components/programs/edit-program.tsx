"use client";

import { useParams } from "next/navigation";
import { AlertCircle, Loader2 } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ProgramEditor } from "./program-editor";
import { useProgram } from "./use-program";

export function EditProgram() {
  const { id } = useParams<{ id: string }>();
  const { program, error } = useProgram(id);
  if (error)
    return (
      <Alert variant="destructive">
        <AlertCircle aria-hidden />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  if (!program)
    return (
      <div className="flex justify-center py-24 text-muted-foreground" role="status">
        <Loader2 className="size-6 animate-spin" aria-hidden />
        <span className="sr-only">در حال بارگذاری</span>
      </div>
    );
  if (program.status === "archived")
    return (
      <Alert>
        <AlertCircle aria-hidden />
        <AlertDescription>برنامه بایگانی‌شده قابل ویرایش نیست. از صفحه برنامه، از آن کپی بگیرید.</AlertDescription>
      </Alert>
    );
  return (
    <>
      <PageHeader title={`ویرایش: ${program.title}`} />
      {/* Remount when the program changes on the server, so a hidden editor never saves stale data */}
      <ProgramEditor key={`${program.id}:${program.updated_at}`} program={program} />
    </>
  );
}
