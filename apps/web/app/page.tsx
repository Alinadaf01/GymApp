import { Dumbbell } from "lucide-react";
import { SystemStatus } from "@/components/system-status";

export default function Home() {
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-12">
      <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-8 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Dumbbell className="size-6" aria-hidden />
          </span>
          <div>
            <h1 className="text-xl font-bold">پنل مربی Basharnia</h1>
            <p className="text-sm text-muted">Coach CRM</p>
          </div>
        </div>
        <p className="mb-6 leading-7 text-muted">
          اسکلت اولیه سامانه آماده است. ورود مربی و داشبورد در فاز بعدی اضافه می‌شوند.
        </p>
        <SystemStatus />
      </section>
    </main>
  );
}
