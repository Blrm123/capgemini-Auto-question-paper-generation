"use client";

import React from 'react';
import Link from 'next/link';
import { useAuth } from "@clerk/nextjs";

export function CTASection() {
  const { isSignedIn, isLoaded } = useAuth();
  
  const buttonText = isSignedIn ? "Go to Dashboard" : "Start For Free";
  const buttonHref = isSignedIn ? "/dashboard" : "/sign-in";

  return (
    <section className="relative py-24 lg:py-32 bg-background overflow-hidden">
      {/* Decorative gradients */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-3xl h-[300px] opacity-30 bg-primary/20 blur-[100px] rounded-full pointer-events-none" />
      
      <div className="relative mx-auto max-w-4xl px-6 lg:px-12 text-center">
        <h2 className="text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl mb-6">
          Ready to transform your workflow?
        </h2>
        <p className="text-lg text-muted-foreground mb-10 max-w-2xl mx-auto leading-relaxed">
          Join thousands of educators who have reclaimed their weekends. Stop manually drafting exams and let our AI handle the heavy lifting while you maintain complete control.
        </p>
        
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href={buttonHref}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-8 py-4 text-base font-bold text-primary-foreground shadow-xl transition-all duration-300 hover:bg-primary/90 hover:-translate-y-1"
          >
            {buttonText}
          </Link>
        </div>
      </div>
    </section>
  );
}
