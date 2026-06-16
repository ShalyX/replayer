import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Agent Reputation Registry",
  description: "Portable AI agent reputation backed by GenLayer.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
