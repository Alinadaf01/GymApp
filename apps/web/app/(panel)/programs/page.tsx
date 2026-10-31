import type { Metadata } from "next";
import { Suspense } from "react";
import { ProgramsList } from "@/components/programs/programs-list";

export const metadata: Metadata = { title: "برنامه‌ها | پنل مربی Basharnia" };

export default function ProgramsPage() {
  return (
    <Suspense>
      <ProgramsList />
    </Suspense>
  );
}
