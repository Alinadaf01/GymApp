import { ClipboardList, LayoutDashboard, Settings, Users, type LucideIcon } from "lucide-react";

export type NavItem = { href: string; label: string; icon: LucideIcon };

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "داشبورد", icon: LayoutDashboard },
  { href: "/students", label: "شاگردان", icon: Users },
  { href: "/programs", label: "برنامه‌ها", icon: ClipboardList },
  { href: "/settings", label: "تنظیمات", icon: Settings },
];
