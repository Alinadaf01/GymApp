import type { Metadata } from "next";
import { Suspense } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { NewProgramForm } from "@/components/programs/new-program-form";

export const metadata: Metadata = { title: "برنامه جدید | پنل مربی Basharnia" };

export default function NewProgramPage() {
  return (
    <>
      <PageHeader title="ثبت برنامه جدید" description="ابتدا پیش‌نویس ساخته می‌شود؛ تا تأیید شما نهایی نمی‌شود." />
      <Suspense>
        <NewProgramForm />
      </Suspense>
    </>
  );
}
