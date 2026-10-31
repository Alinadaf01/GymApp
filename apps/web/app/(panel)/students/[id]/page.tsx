import type { Metadata } from "next";
import { Suspense } from "react";
import { StudentProfile } from "@/components/students/student-profile";

export const metadata: Metadata = { title: "پرونده شاگرد | پنل مربی Basharnia" };

export default function StudentPage() {
  return (
    <Suspense>
      <StudentProfile />
    </Suspense>
  );
}
