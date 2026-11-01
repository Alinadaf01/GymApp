import type { Metadata } from "next";
import { Suspense } from "react";
import { EditStudent } from "@/components/students/edit-student";

export const metadata: Metadata = { title: "ویرایش شاگرد | پنل مربی Basharnia" };

export default function EditStudentPage() {
  return (
    <Suspense>
      <EditStudent />
    </Suspense>
  );
}
