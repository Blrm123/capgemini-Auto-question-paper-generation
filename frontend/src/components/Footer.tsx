import React from 'react';
import Link from 'next/link';

export function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-secondary border-t border-border">
      <div className="mx-auto max-w-7xl px-6 lg:px-12 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-12">
          <div className="md:col-span-2">
            <Link href="/" className="inline-flex items-center gap-2 mb-4">
              <img src="/logo.png" alt="Logo" className="h-8 w-auto rounded-sm object-contain" />
              <span className="text-xl font-bold tracking-wide text-secondary-foreground">
                QUBIT
              </span>
            </Link>
            <p className="text-secondary-foreground/80 text-sm max-w-sm">
              Empowering educators to generate precise, balanced, and fully formatted exam papers in minutes using advanced AI.
            </p>
          </div>
          
          <div>
            <h4 className="font-semibold text-secondary-foreground mb-4">Product</h4>
            <ul className="space-y-3">
              <li>
                <Link href="/dashboard" className="text-sm text-secondary-foreground/80 hover:text-primary transition">
                  Generator
                </Link>
              </li>
              <li>
                <Link href="/history" className="text-sm text-secondary-foreground/80 hover:text-primary transition">
                  History
                </Link>
              </li>
              <li>
                <Link href="/analytics" className="text-sm text-secondary-foreground/80 hover:text-primary transition">
                  Analytics
                </Link>
              </li>
            </ul>
          </div>
          
          <div>
            <h4 className="font-semibold text-secondary-foreground mb-4">Resources</h4>
            <ul className="space-y-3">
              <li>
                <Link href="/knowledge" className="text-sm text-secondary-foreground/80 hover:text-primary transition">
                  Knowledge Base
                </Link>
              </li>
              <li>
                <a href="https://github.com/capgemini/qpapergen" target="_blank" rel="noreferrer" className="text-sm text-secondary-foreground/80 hover:text-primary transition">
                  Documentation
                </a>
              </li>
              <li>
                <Link href="#" className="text-sm text-secondary-foreground/80 hover:text-primary transition">
                  Support
                </Link>
              </li>
            </ul>
          </div>
          
          <div>
            <h4 className="font-semibold text-secondary-foreground mb-4">Legal</h4>
            <ul className="space-y-3">
              <li>
                <Link href="#" className="text-sm text-secondary-foreground/80 hover:text-primary transition">Privacy Policy</Link>
              </li>
              <li>
                <Link href="#" className="text-sm text-secondary-foreground/80 hover:text-primary transition">Terms of Service</Link>
              </li>
            </ul>
          </div>
        </div>
        
        <div className="border-t border-border/50 pt-8 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-secondary-foreground/60">
            &copy; {currentYear} QUBIT. All rights reserved.
          </p>
          <div className="flex items-center gap-6">
            <Link href="#" className="text-sm text-secondary-foreground/80 hover:text-secondary-foreground transition">
              Privacy Policy
            </Link>
            <Link href="#" className="text-sm text-secondary-foreground/80 hover:text-secondary-foreground transition">
              Terms of Service
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
