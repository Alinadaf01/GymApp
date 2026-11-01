import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/page-header";
import { StudentForm } from "@/components/students/student-form";

export const metadata: Metadata = { title: "افزودن شاگرد | پنل مربی Basharnia" };

export default function NewStudentPage() {
  return (
    <>
      <PageHeader title="افزودن شاگرد" description="ساخت پرونده جدید" />
      <StudentForm />
    </>
  );
}
