import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Source_Serif_4 } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";

const serif = Source_Serif_4({ subsets: ["latin"], variable: "--font-source-serif" });
const sans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-plex-sans" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400"], variable: "--font-plex-mono" });

export const metadata: Metadata = {
  title: "AgentLab | Source-checked AI research",
  description: "AgentLab researches the web, verifies claims, and turns findings into clear, source-backed reports.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable} ${mono.variable}`}>
      <body className="bg-paper font-sans text-[15px] leading-normal text-ink antialiased">
        {children}
        <Toaster position="bottom-right" theme="system" />
      </body>
    </html>
  );
}
