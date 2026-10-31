import type { Metadata } from "next";
import { ComingSoon } from "@/components/layout/coming-soon";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "برنامه‌ها | پنل مربی Basharnia" };

export default function ProgramsPage() {
  return (
    <>
      <PageHeader title="برنامه‌ها" description="برنامه‌های تمرینی، غذایی و مکمل" />
      <ComingSoon phase={4} />
    </>
  );
}
