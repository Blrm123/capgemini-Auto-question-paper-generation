"use client";

import React from 'react';
import Link from 'next/link';
import { useAuth } from "@clerk/nextjs";
import Shuffle from './Shuffle';

interface HeroSectionProps {
  title?: React.ReactNode;
  description?: string;
  bgImageUrl?: string;
}

export function HeroSection({
  title = "From Syllabus to Exam",
  description = "Save hours of work with AI that understands your syllabus, covers every unit, balances difficulty levels, and produces ready-to-use examination papers.",
  bgImageUrl = "/background.png"
}: HeroSectionProps) {
  const { isSignedIn, isLoaded } = useAuth();
  
  const buttonText = isSignedIn ? "Get Started" : "Login";
  const buttonHref = isSignedIn ? "/dashboard" : "/sign-in";

  return (
    <section className="relative w-full min-h-screen flex items-end pb-24 lg:pb-32 overflow-hidden bg-background">
      {/* Background Image Container */}
      <div 
        className="absolute inset-0 bg-cover bg-center bg-no-repeat opacity-90"
        style={{ backgroundImage: `url('${bgImageUrl}')` }}
      >
        {/* Added a subtle black overlay to mix in some dark theme */}
        <div className="absolute inset-0 bg-black/30" />
      </div>

      <div className="relative z-10 mx-auto w-full max-w-7xl px-6 lg:px-12 xl:px-16">
        <div className="max-w-3xl">
          <Shuffle
            text={title as string}
            tag="h1"
            className="text-5xl font-extrabold tracking-tight text-primary/60 drop-shadow-xl sm:text-6xl lg:text-[5rem] mb-6 text-balance leading-[1.05] [-webkit-text-stroke:1.5px_black]"
            shuffleDirection="right"
            duration={0.35}
            animationMode="evenodd"
            shuffleTimes={1}
            ease="power3.out"
            stagger={0.03}
            threshold={0.1}
            triggerOnce={true}
            triggerOnHover={true}
            respectReducedMotion={true}
            loop={false}
            loopDelay={0}
            textAlign="left"
          />
          <div className="flex flex-wrap items-center gap-6">
            <Link
              href={buttonHref}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-secondary px-4 py-2.5 text-sm font-semibold text-secondary-foreground shadow-lg transition-all duration-300 hover:bg-secondary/90 border border-border"
            >
              <div className="bg-background/20 rounded text-secondary-foreground p-1">
                {/* SVG Icon */}
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              {buttonText}
            </Link>
            
            <Link
              href="/history"
              className="inline-flex items-center text-sm font-medium text-muted-foreground transition-colors duration-300 hover:text-foreground"
            >
              Read Documentation <span className="ml-2 font-normal">&rarr;</span>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
