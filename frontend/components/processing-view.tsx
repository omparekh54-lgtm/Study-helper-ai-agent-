"use client";

import { useEffect, useState } from "react";
import { Check, FileText, Loader2 } from "lucide-react";
import type { DocumentOut } from "@/lib/types";
import { cn, formatDuration, pluralize } from "@/lib/utils";
import { Card } from "./ui";

function useElapsed(since: string) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  return Math.max(0, (now - new Date(since).getTime()) / 1000);
}

export function ProcessingView({ doc }: { doc: DocumentOut }) {
  const elapsed = useElapsed(doc.created_at);
  const steps = [
    { label: "Document read", detail: `${pluralize(doc.page_count, doc.source_label)} of text extracted`, state: "done" as const },
    {
      label: "Mapping units & topics",
      detail: doc.status === "queued" ? "Waiting for a free slot…" : doc.stage_detail,
      state: "active" as const,
    },
    { label: "Writing quizzes, Q&A & video scripts", detail: "Topic by topic, from your pages", state: "todo" as const },
    { label: "Fact-checking every answer", detail: "Quotes matched to your document, then double-checked", state: "todo" as const },
  ];

  return (
    <div className="mx-auto max-w-2xl px-4 py-14 sm:px-6 sm:py-20">
      <div className="mb-10 flex flex-col items-center text-center">
        <div className="relative mb-6">
          <div className="absolute inset-0 animate-ping rounded-3xl bg-primary/20 [animation-duration:2.4s]" aria-hidden />
          <div className="relative grid size-16 animate-float place-items-center rounded-3xl bg-gradient-to-br from-primary to-accent text-white shadow-[0_12px_32px_-12px_var(--primary)]">
            <FileText className="size-7" aria-hidden />
          </div>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-balance sm:text-3xl">Building your study kit</h1>
        <p className="mt-2 max-w-md text-muted">
          Reading <span className="font-medium text-text-soft">{doc.filename}</span>. Topics will appear as soon as they&apos;re mapped
          — usually within a minute.
        </p>
      </div>

      <Card className="p-2 sm:p-3">
        <ol aria-live="polite">
          {steps.map((step, i) => (
            <li key={step.label} className={cn("flex gap-4 rounded-xl p-3 sm:p-4", step.state === "active" && "bg-primary-soft/60")}>
              <div className="flex flex-col items-center">
                <div
                  className={cn(
                    "grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold",
                    step.state === "done" && "bg-success text-white",
                    step.state === "active" && "bg-primary text-on-primary",
                    step.state === "todo" && "border border-border-strong text-muted",
                  )}
                >
                  {step.state === "done" ? <Check className="size-4" /> : step.state === "active" ? <Loader2 className="size-4 animate-spin" /> : i + 1}
                </div>
              </div>
              <div className="min-w-0 pt-1">
                <p className={cn("font-medium", step.state === "todo" && "text-muted")}>{step.label}</p>
                <p className="mt-0.5 text-sm text-muted">{step.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </Card>

      <p className="mt-6 text-center text-sm text-muted">
        {formatDuration(elapsed)} elapsed · You can leave this page — it&apos;s saved in your library and keeps building.
      </p>
    </div>
  );
}
