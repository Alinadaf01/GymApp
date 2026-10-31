import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

// Vazirmatn (SIL OFL 1.1) served locally — no external font CDN
const vazirmatn = localFont({
  src: [
    { path: "./fonts/vazirmatn-arabic-wght-normal.woff2", weight: "100 900", style: "normal" },
    { path: "./fonts/vazirmatn-latin-wght-normal.woff2", weight: "100 900", style: "normal" },
  ],
  variable: "--font-vazirmatn",
  display: "swap",
});

export const metadata: Metadata = {
  title: "پنل مربی Basharnia",
  description: "سامانه مدیریت شاگردان و برنامه‌های تمرینی Basharnia",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f6f7f9",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fa" dir="rtl" className={`${vazirmatn.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
