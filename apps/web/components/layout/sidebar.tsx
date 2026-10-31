"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Dumbbell, LogOut, Menu } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "./nav";

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Dumbbell className="size-5" aria-hidden />
      </span>
      <div className="leading-tight">
        <div className="font-bold">Basharnia</div>
        <div className="text-xs text-muted-foreground">پنل مربی</div>
      </div>
    </div>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="منوی اصلی" className="flex flex-col gap-1">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
              active ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="size-5" aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

function UserFooter() {
  const { user } = useAuth();
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function logout() {
    setBusy(true);
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
      router.replace("/login");
    } catch (e) {
      toast.error((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center justify-between gap-2 border-t pt-4">
      <span className="truncate text-sm text-muted-foreground ltr">{user?.username}</span>
      <Button variant="ghost" size="sm" onClick={logout} disabled={busy}>
        <LogOut aria-hidden />
        خروج
      </Button>
    </div>
  );
}

/** Desktop: fixed sidebar on the start (right) side. Mobile: top bar + slide-in sheet. */
export function Sidebar() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <aside className="sticky top-0 hidden h-svh w-64 shrink-0 flex-col gap-6 border-l bg-card p-4 lg:flex">
        <Brand />
        <div className="flex-1">
          <NavLinks />
        </div>
        <UserFooter />
      </aside>

      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b bg-card px-4 lg:hidden">
        <Brand />
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="باز کردن منو">
              <Menu className="size-6" />
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="p-4" aria-describedby={undefined}>
            <SheetTitle className="sr-only">منوی اصلی</SheetTitle>
            <Brand />
            <div className="flex-1">
              <NavLinks onNavigate={() => setOpen(false)} />
            </div>
            <UserFooter />
          </SheetContent>
        </Sheet>
      </header>
    </>
  );
}
