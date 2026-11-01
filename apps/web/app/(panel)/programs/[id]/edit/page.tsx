import type { Metadata } from "next";
import { Suspense } from "react";
import { EditProgram } from "@/components/programs/edit-program";

export const metadata: Metadata = { title: "ویرایش برنامه | پنل مربی Basharnia" };

export default function EditProgramPage() {
  return (
    <Suspense>
      <EditProgram />
    </Suspense>
  );
}
