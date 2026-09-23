import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { BackendBanner, SiteFooter, SiteHeader } from "@/components/chrome";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "StudyForge — turn your notes into a study kit", template: "%s · StudyForge" },
  description:
    "Upload your notes, slides or textbook chapter. StudyForge maps every unit and topic, then builds MCQ tests, exam-style Q&A and narrated video lessons — each answer checked against your own material.",
  applicationName: "StudyForge",
  openGraph: {
    title: "StudyForge — AI study kits from your own notes",
    description: "MCQ tests, exam-style Q&A and narrated video lessons for every topic in your document.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f7fb" },
    { media: "(prefers-color-scheme: dark)", color: "#090d1b" },
  ],
};

// Apply the saved/system theme before first paint to avoid a flash.
const themeScript = `(() => { try {
  const saved = localStorage.getItem("theme");
  const dark = saved ? saved === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.classList.toggle("dark", dark);
} catch {} })();`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="flex min-h-full flex-col font-sans">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2 focus:shadow-card"
        >
          Skip to content
        </a>
        <SiteHeader />
        <BackendBanner />
        <main id="main" className="flex-1">
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
