"use client";

import { useParams } from "next/navigation";
import { AlertCircle, Loader2 } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { StudentForm } from "./student-form";
import { useStudent } from "./use-student";

export function EditStudent() {
  const { id } = useParams<{ id: string }>();
  const { student, error } = useStudent(id);
  if (error)
    return (
      <Alert variant="destructive">
        <AlertCircle aria-hidden />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  if (!student)
    return (
      <div className="flex justify-center py-24 text-muted-foreground" role="status">
        <Loader2 className="size-6 animate-spin" aria-hidden />
        <span className="sr-only">در حال بارگذاری</span>
      </div>
    );
  return (
    <>
      <PageHeader title={`ویرایش ${student.full_name}`} />
      {/* Remount when the record changes on the server (e.g. archived from the profile)
          so a page kept hidden by Next.js never submits stale values. */}
      <StudentForm key={`${student.id}:${student.updated_at}`} student={student} />
    </>
  );
}
