"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api";
import {
  LayoutDashboard,
  FileText,
  ScrollText,
  BookOpen,
  LogOut,
  Shield,
  ChevronRight,
} from "lucide-react";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "FIR Review", href: "/dashboard/fir", icon: FileText },
  { label: "Charge Sheet", href: "/dashboard/chargesheet", icon: ScrollText },
  { label: "SOP Assistant", href: "/dashboard/sop", icon: BookOpen },
];

const ROLE_COLOURS: Record<string, string> = {
  ADMIN: "bg-purple-100 text-purple-800",
  SHO: "bg-blue-100 text-blue-800",
  IO: "bg-emerald-100 text-emerald-800",
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<{
    username: string;
    role: string;
    full_name: string;
  } | null>(null);

  useEffect(() => {
    apiClient("/api/v1/auth/me")
      .then(setUser)
      .catch(() => router.push("/login"));
  }, [router]);

  function handleLogout() {
    localStorage.removeItem("atlas_token");
    router.push("/login");
  }

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* Sidebar */}
      <aside className="w-64 bg-gradient-to-b from-slate-900 to-slate-800 text-white flex flex-col shadow-xl">
        {/* Brand */}
        <div className="p-6 flex items-center gap-3">
          <div className="w-9 h-9 bg-blue-500 rounded-lg flex items-center justify-center shadow">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-wide">ATLAS</h1>
            <p className="text-[10px] text-slate-400 leading-none">Criminal Justice Platform</p>
          </div>
        </div>

        <div className="mx-4 h-px bg-slate-700" />

        <nav className="flex-1 p-3 space-y-0.5 mt-2">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  active
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-300 hover:bg-slate-700 hover:text-white"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
                {active && <ChevronRight className="w-3.5 h-3.5 ml-auto opacity-70" />}
              </Link>
            );
          })}
        </nav>

        {/* User card */}
        {user && (
          <div className="m-3 p-3 bg-slate-700/50 rounded-lg border border-slate-600">
            <p className="text-sm font-medium truncate">{user.full_name}</p>
            <p className="text-xs text-slate-400 truncate">{user.username}</p>
            <span className={`inline-block mt-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full ${ROLE_COLOURS[user.role] ?? "bg-slate-600 text-white"}`}>
              {user.role}
            </span>
          </div>
        )}
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-14 border-b border-slate-200 flex items-center justify-between px-6 bg-white shadow-sm">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <span className="font-semibold text-slate-800">
              {NAV_ITEMS.find(n => pathname === n.href || (n.href !== "/dashboard" && pathname.startsWith(n.href)))?.label ?? "ATLAS"}
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            className="text-slate-500 hover:text-slate-800 gap-2"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </Button>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
