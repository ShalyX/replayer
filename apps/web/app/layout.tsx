import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "RepLayer",
  description: "Portable reputation for AI agents, verified by GenLayer.",
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <footer className="site-footer">
          <span>Built on GenLayer</span>
          <a href="https://github.com/ShalyX/replayer" target="_blank" rel="noreferrer">GitHub</a>
        </footer>
      </body>
    </html>
  );
}
