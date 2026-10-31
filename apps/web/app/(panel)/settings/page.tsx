import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/page-header";
import { ChangePasswordForm } from "@/components/settings/change-password-form";
import { PdfTemplateForm } from "@/components/settings/pdf-template-form";

export const metadata: Metadata = { title: "تنظیمات | پنل مربی Basharnia" };

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="تنظیمات" description="سربرگ PDF و امنیت حساب" />
      <div className="grid max-w-2xl gap-6">
        <PdfTemplateForm />
        <ChangePasswordForm />
      </div>
    </>
  );
}
