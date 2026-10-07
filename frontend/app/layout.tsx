import type { Metadata } from "next";
import { Toaster } from "sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentLab | Source-checked AI research",
  description: "AgentLab researches the web, verifies claims, and turns findings into clear, source-backed reports.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-paper font-sans text-[15px] leading-normal text-ink antialiased">
        {children}
        <Toaster position="bottom-right" theme="system" />
      </body>
    </html>
  );
}
