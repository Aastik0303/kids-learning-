import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Nursery Learning",
  description: "Prototype nursery learning platform"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="day-sky-backdrop" aria-hidden="true">
          <span className="day-sun" />
          <span className="day-cloud cloud-a" />
          <span className="day-cloud cloud-b" />
          <span className="day-cloud cloud-c" />
          <span className="day-birds birds-a" />
          <span className="day-birds birds-b" />
        </div>
        <div className="site-content">
          <Providers>{children}</Providers>
        </div>
      </body>
    </html>
  );
}
