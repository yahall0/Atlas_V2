"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "FIR Review", href: "/dashboard/fir" },
  { label: "Charge Sheet", href: "/dashboard/chargesheet" },
  { label: "SOP Assistant", href: "/dashboard/sop" },
];

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
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 text-white flex flex-col">
        <div className="p-6">
          <h1 className="text-xl font-bold">ATLAS</h1>
          <p className="text-xs text-gray-400 mt-1">Criminal Justice Support</p>
        </div>
        <Separator className="bg-gray-700" />
        <nav className="flex-1 p-4 space-y-1">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`block px-4 py-2 rounded text-sm ${
                pathname === item.href
                  ? "bg-gray-700 text-white"
                  : "text-gray-300 hover:bg-gray-800"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="h-16 border-b flex items-center justify-between px-6 bg-white">
          <span className="font-semibold text-lg">ATLAS</span>
          <div className="flex items-center gap-3">
            {user && (
              <>
                <span className="text-sm">{user.full_name}</span>
                <Badge variant="secondary">{user.role}</Badge>
              </>
            )}
            <Button variant="outline" size="sm" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 bg-gray-50">{children}</main>
      </div>
    </div>
  );
}
