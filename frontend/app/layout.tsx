import type { Metadata } from "next";
import { Inter, Instrument_Serif, Geist } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";
import SessionProvider from "@/components/providers/SessionProvider";
import { Toaster } from "sonner";

const geist = Geist({ subsets: ['latin'], variable: '--font-sans' });

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-serif",
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "MATRIQ | National Material Intelligence Platform",
  description:
    "AI-powered catalog standardization, deduplication, and cross-CPSE material harmonization for the National Master Registry.",
  icons: {
    icon: "/logo.svg",
    shortcut: "/logo.svg",
    apple: "/logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-scroll-behavior="smooth"
      className={cn("antialiased dark", inter.variable, instrumentSerif.variable, "font-sans", geist.variable)}
    >
      <body className="bg-[#0A0809] text-white">
        <SessionProvider>{children}</SessionProvider>
        <Toaster position="bottom-right" theme="dark" closeButton />
      </body>
    </html>
  );
}

