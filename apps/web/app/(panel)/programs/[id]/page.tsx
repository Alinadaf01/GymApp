import type { Metadata } from "next";
import { Suspense } from "react";
import { ProgramView } from "@/components/programs/program-view";

export const metadata: Metadata = { title: "برنامه | پنل مربی Basharnia" };

export default function ProgramPage() {
  return (
    <Suspense>
      <ProgramView />
    </Suspense>
  );
}
