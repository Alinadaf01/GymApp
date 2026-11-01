"use client";

import { useState } from "react";
import { Archive, ArchiveRestore } from "lucide-react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import type { Student } from "@/lib/types";

function updatePayload(s: Student, status: Student["status"]) {
  const { first_name, last_name, phone, birth_date, gender, height_cm, initial_weight_kg, current_weight_kg,
    training_history, goal, limitations_notes, start_date, coach_notes } = s;
  return {
    first_name, last_name, phone, birth_date, gender, height_cm, initial_weight_kg, current_weight_kg,
    training_history, goal, limitations_notes, start_date, coach_notes, status,
  };
}

/** Archive (soft delete, with confirmation) or restore a student. Nothing is permanently deleted. */
export function ArchiveButton({ student, onChanged }: { student: Student; onChanged: (s: Student) => void }) {
  const [busy, setBusy] = useState(false);
  const archived = student.status === "archived";

  async function archive() {
    setBusy(true);
    try {
      onChanged(await apiFetch<Student>(`/api/students/${student.id}`, { method: "DELETE" }));
      toast.success("شاگرد بایگانی شد.");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function restore() {
    setBusy(true);
    try {
      const updated = await apiFetch<Student>(`/api/students/${student.id}`, {
        method: "PUT",
        body: JSON.stringify(updatePayload(student, "active")),
      });
      onChanged(updated);
      toast.success("شاگرد از بایگانی خارج شد.");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (archived) {
    return (
      <Button variant="outline" onClick={restore} disabled={busy}>
        <ArchiveRestore aria-hidden />
        خروج از بایگانی
      </Button>
    );
  }

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline" disabled={busy}>
          <Archive aria-hidden />
          بایگانی
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>بایگانی {student.full_name}؟</AlertDialogTitle>
          <AlertDialogDescription>
            شاگرد از فهرست اصلی پنهان می‌شود، اما پرونده، برنامه‌ها، PDFها و سوابق او حذف نمی‌شوند و هر زمان
            قابل بازگرداندن است.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogAction onClick={archive}>بله، بایگانی شود</AlertDialogAction>
          <AlertDialogCancel>انصراف</AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
