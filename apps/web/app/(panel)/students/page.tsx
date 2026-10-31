import type { Metadata } from "next";
import { ComingSoon } from "@/components/layout/coming-soon";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "شاگردان | پنل مربی Basharnia" };

export default function StudentsPage() {
  return (
    <>
      <PageHeader title="شاگردان" description="فهرست و پرونده شاگردان" />
      <ComingSoon phase={3} />
    </>
  );
}
