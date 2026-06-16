import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "RepLayer",
  description: "Portable reputation for AI agents, verified by GenLayer.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
