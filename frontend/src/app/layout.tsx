import type { Metadata } from "next";
import { ClerkProvider } from '@clerk/nextjs'
import { Inter, Fraunces, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Providers from "./providers";
import { Header } from "@/components/Header";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-serif",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "QUBIT",
  description: "AI-assisted university examination paper creation.",
  icons: {
    icon: "/logo.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${fraunces.variable} ${jetbrainsMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col font-serif bg-background text-foreground">
        <ClerkProvider>
          <Providers>
            <Header />
            <main className="pt-24 flex-1">
              {children}
            </main>
          </Providers>
        </ClerkProvider>
      </body>
    </html>
  );
}
