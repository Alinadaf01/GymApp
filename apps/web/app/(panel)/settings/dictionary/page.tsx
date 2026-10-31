import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DictionaryManager } from "@/components/settings/dictionary-manager";

export const metadata: Metadata = { title: "فرهنگ لغت حرکات | پنل مربی Basharnia" };

export default function DictionaryPage() {
  return (
    <div className="max-w-3xl">
      <Link href="/settings" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline">
        <ArrowRight className="size-4" aria-hidden />
        تنظیمات
      </Link>
      <PageHeader title="فرهنگ لغت حرکات" description="نام‌های استاندارد و مترادف‌هایی که در ویس گفته می‌شوند" />
      <DictionaryManager />
    </div>
  );
}
