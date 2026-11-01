import type { Metadata } from "next";
import Link from "next/link";
import { BookOpen, ChevronLeft } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/layout/page-header";
import { ChangePasswordForm } from "@/components/settings/change-password-form";
import { PdfTemplateForm } from "@/components/settings/pdf-template-form";

export const metadata: Metadata = { title: "تنظیمات | پنل مربی Basharnia" };

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="تنظیمات" description="سربرگ PDF و امنیت حساب" />
      <div className="grid max-w-2xl gap-6">
        <Link href="/settings/dictionary" className="block">
          <Card className="transition-colors hover:bg-muted/30">
            <CardContent className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-3">
                <BookOpen className="size-5 text-muted-foreground" aria-hidden />
                <span>
                  <span className="block font-semibold">فرهنگ لغت حرکات</span>
                  <span className="text-sm text-muted-foreground">نام حرکات و مترادف‌ها برای تشخیص از ویس</span>
                </span>
              </span>
              <ChevronLeft className="size-5 text-muted-foreground" aria-hidden />
            </CardContent>
          </Card>
        </Link>
        <PdfTemplateForm />
        <ChangePasswordForm />
      </div>
    </>
  );
}
