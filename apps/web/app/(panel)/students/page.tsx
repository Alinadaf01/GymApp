import type { Metadata } from "next";
import { Suspense } from "react";
import { StudentsList } from "@/components/students/students-list";

export const metadata: Metadata = { title: "شاگردان | پنل مربی Basharnia" };

export default function StudentsPage() {
  return (
    <Suspense>
      <StudentsList />
    </Suspense>
  );
}
