"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton, useAuth } from "@clerk/nextjs";
import { useState, useEffect } from "react";

export function Header() {
  const pathname = usePathname();
  const { isSignedIn, isLoaded } = useAuth();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header 
      className={`fixed z-50 w-full transition-all duration-500 ease-out ${
        scrolled ? "top-2 left-0 right-0 px-4" : "top-4 left-0 right-0 px-4 sm:px-6 lg:px-8"
      }`}
    >
      <div 
        className={`relative mx-auto flex items-center justify-between rounded-2xl glass-panel transition-all duration-500 ease-out ${
          scrolled ? "h-12 max-w-4xl px-5" : "h-14 max-w-7xl px-6 gap-4"
        }`}
      >
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <img 
            src="/logo.png" 
            alt="Logo" 
            className={`w-auto rounded-sm object-contain transition-all duration-500 ${scrolled ? "h-6" : "h-8"}`} 
          />
          <span 
            className={`font-serif font-bold tracking-wide text-foreground transition-all duration-500 ${scrolled ? "text-lg hidden sm:block" : "text-xl"}`}
          >
            QUBIT
          </span>
        </Link>

        <nav className={`hidden md:flex items-center transition-all duration-500 ${scrolled ? "gap-5 text-[13px]" : "gap-8"}`}>
          {isSignedIn && (
            <>
              <Link 
                href="/" 
                className={`font-serif font-bold transition ${pathname === "/" ? "text-primary" : "text-foreground/70 hover:text-primary"} ${scrolled ? "text-sm" : "text-[15px]"}`}
              >
                Home
              </Link>
              <Link 
                href="/dashboard" 
                className={`font-serif font-bold transition ${pathname === "/dashboard" ? "text-primary" : "text-foreground/70 hover:text-primary"} ${scrolled ? "text-sm" : "text-[15px]"}`}
              >
                Dashboard
              </Link>
              <Link 
                href="/history" 
                className={`font-serif font-bold transition ${pathname === "/history" ? "text-primary" : "text-foreground/70 hover:text-primary"} ${scrolled ? "text-sm" : "text-[15px]"}`}
              >
                History
              </Link>
              <Link 
                href="/analytics" 
                className={`font-serif font-bold transition ${pathname === "/analytics" ? "text-primary" : "text-foreground/70 hover:text-primary"} ${scrolled ? "text-sm" : "text-[15px]"}`}
              >
                Analytics
              </Link>
              <Link 
                href="/knowledge" 
                className={`font-serif font-bold transition ${pathname === "/knowledge" ? "text-primary" : "text-foreground/70 hover:text-primary"} ${scrolled ? "text-sm" : "text-[15px]"}`}
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
              className="font-serif text-[14px] font-bold px-4 py-2 rounded-lg transition bg-primary text-primary-foreground hover:opacity-90 shadow-sm"
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
