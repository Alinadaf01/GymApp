import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/page-header";
import { ChangePasswordForm } from "@/components/settings/change-password-form";

export const metadata: Metadata = { title: "تنظیمات | پنل مربی Basharnia" };

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="تنظیمات" description="امنیت حساب و تنظیمات پنل" />
      <div className="grid max-w-xl gap-6">
        <ChangePasswordForm />
      </div>
    </>
  );
}
