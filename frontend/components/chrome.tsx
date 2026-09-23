"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import { CodeXml, Moon, Sun, RefreshCw } from "lucide-react";
import { retryBackend, useBackend } from "@/lib/backend";
import { cn } from "@/lib/utils";

export const REPO_URL = "https://github.com/omparekh54-lgtm/Study-helper-ai-agent-";

export function Logo({ className }: { className?: string }) {
  return (
    <Link href="/" className={cn("group inline-flex items-center gap-2.5", className)} aria-label="StudyForge home">
      <span className="relative grid size-8 place-items-center overflow-hidden rounded-[10px] bg-gradient-to-br from-primary to-accent shadow-[0_6px_16px_-6px_var(--primary)] transition-transform group-hover:scale-105">
        <svg viewBox="0 0 24 24" className="size-[18px] text-white" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M4 19.5V6a2 2 0 0 1 2-2h11.5a.5.5 0 0 1 .5.5V17" />
          <path d="M6 17h12.5a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-.5.5H6a2 2 0 0 1 0-4" />
          <path d="m9.5 10 2 2 3.5-4" />
        </svg>
      </span>
      <span className="text-[17px] font-semibold tracking-tight">StudyForge</span>
    </Link>
  );
}

function subscribeTheme(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

function ThemeToggle() {
  const dark = useSyncExternalStore(
    subscribeTheme,
    () => document.documentElement.classList.contains("dark"),
    () => false,
  );
  const toggle = () => {
    const next = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {}
  };
  return (
    <button
      onClick={toggle}
      className="grid size-9 place-items-center rounded-xl text-text-soft transition-colors hover:bg-surface-2 hover:text-text"
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {dark ? <Sun className="size-[18px]" /> : <Moon className="size-[18px]" />}
    </button>
  );
}

export function BackendDot() {
  const state = useBackend();
  const label = {
    checking: "Connecting…",
    waking: "Waking up the engine…",
    ready: "Engine ready",
    down: "Engine offline",
  }[state];
  return (
    <span
      className="hidden items-center gap-2 rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-medium text-text-soft sm:inline-flex"
      title={
        state === "waking"
          ? "StudyForge runs on a free server that naps when idle. It takes up to a minute to wake up."
          : undefined
      }
    >
      <span className="relative flex size-2">
        {state !== "ready" && state !== "down" && (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-warning opacity-60" />
        )}
        <span
          className={cn(
            "relative inline-flex size-2 rounded-full",
            state === "ready" ? "bg-success" : state === "down" ? "bg-danger" : "bg-warning",
          )}
        />
      </span>
      {label}
    </span>
  );
}

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-bg/75 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Logo />
        <nav className="flex items-center gap-1.5">
          <BackendDot />
          <Link href="/#library" className="hidden rounded-xl px-3 py-2 text-sm font-medium text-text-soft hover:bg-surface-2 hover:text-text md:block">
            Library
          </Link>
          <Link href="/#how" className="hidden rounded-xl px-3 py-2 text-sm font-medium text-text-soft hover:bg-surface-2 hover:text-text md:block">
            How it works
          </Link>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="grid size-9 place-items-center rounded-xl text-text-soft transition-colors hover:bg-surface-2 hover:text-text"
            aria-label="Source code on GitHub"
          >
            <CodeXml className="size-[18px]" />
          </a>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}

export function BackendBanner() {
  const state = useBackend();
  if (state === "waking") {
    return (
      <div className="border-b border-warning/20 bg-warning-soft px-4 py-2 text-center text-[13px] font-medium text-warning">
        Waking up the StudyForge engine — it naps on free hosting and takes up to a minute to start. Everything will load automatically.
      </div>
    );
  }
  if (state === "down") {
    return (
      <div className="flex items-center justify-center gap-3 border-b border-danger/20 bg-danger-soft px-4 py-2 text-[13px] font-medium text-danger">
        The StudyForge engine isn&apos;t responding right now.
        <button onClick={retryBackend} className="inline-flex items-center gap-1 underline underline-offset-2">
          <RefreshCw className="size-3.5" /> Try again
        </button>
      </div>
    );
  }
  return null;
}

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-4 py-8 text-sm text-muted sm:flex-row sm:px-6">
        <p>
          <span className="font-medium text-text-soft">StudyForge</span> · AI study kits from your own notes
        </p>
        <p className="flex items-center gap-4">
          <span>Gemini · Groq · FastAPI · Next.js</span>
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 hover:text-text">
            <CodeXml className="size-4" /> Source code
          </a>
        </p>
      </div>
    </footer>
  );
}
