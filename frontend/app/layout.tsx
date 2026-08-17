import type { Metadata, Viewport } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Saksham IQ",
  description: "Saksham IQ — prototype nursery learning platform"
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // Never lock zoom — pinning maximumScale to 1 or setting userScalable:false
  // fails WCAG 1.4.4, and parents with low vision use this app too.
  maximumScale: 5,
  // Lets the page paint into the notch area; `env(safe-area-inset-*)` in
  // globals.css then keeps actual controls clear of it.
  viewportFit: "cover",
  themeColor: "#f5b84b"
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
