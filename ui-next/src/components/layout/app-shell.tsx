"use client";

import { useState } from "react";
import { Menu, Lock } from "lucide-react";
import { Sidebar, SidebarContent } from "./sidebar";
import { Sheet, SheetTrigger, SheetContent } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { ProfileProvider } from "@/hooks/use-profile";
import { AuthProvider, useAuth } from "@/hooks/use-auth";
import { ResumeUploadProvider } from "@/hooks/use-resume-upload";

function ViewOnlyBanner() {
  const { canEdit, isLoading } = useAuth();
  if (isLoading || canEdit) return null;
  return (
    <div className="flex items-center gap-2 bg-blue-50 border-b border-blue-200 px-4 py-2 text-sm text-blue-700">
      <Lock className="h-4 w-4 shrink-0" />
      <span>View-only mode &mdash; you can browse but cannot make changes.</span>
    </div>
  );
}

function AppShellInner({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <Sidebar />

      {/* Mobile header + sheet */}
      <div className="fixed left-0 top-0 z-30 flex h-14 w-full items-center border-b bg-white px-4 lg:hidden">
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="sm" className="mr-3">
              <Menu className="h-5 w-5" />
              <span className="sr-only">Toggle menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent className="w-64 p-0">
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </SheetContent>
        </Sheet>
        <span className="text-sm font-bold text-gray-800">Job Tracker</span>
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col lg:ml-64">
        <ViewOnlyBanner />
        <main className="flex-1 overflow-y-auto p-4 pt-18 lg:p-8 lg:pt-8">
          {children}
        </main>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ProfileProvider>
        <ResumeUploadProvider>
          <AppShellInner>{children}</AppShellInner>
        </ResumeUploadProvider>
      </ProfileProvider>
    </AuthProvider>
  );
}
