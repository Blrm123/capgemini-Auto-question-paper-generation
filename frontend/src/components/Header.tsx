"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton, useAuth } from "@clerk/nextjs";

export function Header() {
  const pathname = usePathname();
  const isHome = pathname === "/";
  const { isSignedIn, isLoaded } = useAuth();

  return (
    <header 
      className={`fixed top-0 inset-x-0 z-50 w-full transition-all duration-300 py-4 ${
        isHome 
          ? "bg-black/20 backdrop-blur-[20px] border-b border-white/20 shadow-[0_8px_32px_0_rgba(0,0,0,0.37)]" 
          : "bg-background/60 backdrop-blur-xl border-b border-border/40 shadow-sm"
      }`}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 h-12">
        <Link href="/" className="flex items-center gap-2">
          <img src="/logo.jpeg" alt="Logo" className="h-8 w-auto rounded-sm object-contain" />
          <span className="text-lg font-bold tracking-wide text-foreground drop-shadow-sm">
            QUBIT
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {isSignedIn && (
            <>
              <Link 
                href="/" 
                className={`text-sm font-medium transition ${pathname === "/" ? "text-primary" : "text-foreground/70 hover:text-primary"}`}
              >
                Home
              </Link>
              <Link 
                href="/dashboard" 
                className={`text-sm font-medium transition ${pathname === "/dashboard" ? "text-primary" : "text-foreground/70 hover:text-primary"}`}
              >
                Dashboard
              </Link>
              <Link 
                href="/history" 
                className={`text-sm font-medium transition ${pathname === "/history" ? "text-primary" : "text-foreground/70 hover:text-primary"}`}
              >
                History
              </Link>
              <Link 
                href="/analytics" 
                className={`text-sm font-medium transition ${pathname === "/analytics" ? "text-primary" : "text-foreground/70 hover:text-primary"}`}
              >
                Analytics
              </Link>
              <Link 
                href="/knowledge" 
                className={`text-sm font-medium transition ${pathname === "/knowledge" ? "text-primary" : "text-foreground/70 hover:text-primary"}`}
              >
                Knowledge Base
              </Link>
            </>
          )}
        </nav>

        <div className="flex items-center gap-4">
          {isLoaded && !isSignedIn && (
            <Link
              href="/sign-in"
              className={`text-sm font-medium px-4 py-2 rounded-lg transition ${
                isHome 
                  ? "bg-secondary text-secondary-foreground hover:bg-secondary/90 shadow-lg" 
                  : "bg-secondary text-secondary-foreground hover:bg-secondary/90 shadow-sm"
              }`}
            >
              Login
            </Link>
          )}

          {isLoaded && isSignedIn && (
            <UserButton />
          )}
        </div>
      </div>
    </header>
  );
}
