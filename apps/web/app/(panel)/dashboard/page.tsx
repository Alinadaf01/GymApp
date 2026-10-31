import type { Metadata } from "next";
import { Dashboard } from "@/components/dashboard/dashboard";

export const metadata: Metadata = { title: "داشبورد | پنل مربی Basharnia" };

export default function DashboardPage() {
  return <Dashboard />;
}
