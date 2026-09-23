"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChevronDown, Eye, EyeOff, FileDown } from "lucide-react";
import { apiUrl } from "@/lib/api";
import type { QAItem } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, SourceQuote, Toggle, VerificationBadge } from "./ui";

export function QAPanel({ items, topicId }: { items: QAItem[]; topicId: string }) {
  const [selfTest, setSelfTest] = useState(false);
  const [revealed, setRevealed] = useState<Set<number>>(new Set());
  const [sources, setSources] = useState<Set<number>>(new Set());

  const toggle = (set: Set<number>, id: number) => {
    const next = new Set(set);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  };

  if (items.length === 0) {
    return <Card className="p-8 text-center text-muted">No theory questions for this topic.</Card>;
  }

  return (
    <div>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Toggle
            checked={selfTest}
            onChange={(v) => {
              setSelfTest(v);
              setRevealed(new Set());
            }}
            label="Self-test mode"
          />
          <p className="mt-1 pl-[52px] text-xs text-muted">Hide answers, think of yours first, then reveal.</p>
        </div>
        <Button variant="outline" size="sm" href={apiUrl(`/api/topics/${topicId}/qa.pdf`)} external icon={<FileDown className="size-4" />}>
          Download as PDF
        </Button>
      </div>

      <ol className="space-y-4">
        {items.map((item, i) => {
          const hidden = selfTest && !revealed.has(item.id);
          return (
            <li key={item.id}>
              <Card className="p-5 sm:p-6">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs font-semibold text-muted">Q{i + 1}</span>
                  <Badge tone={item.kind === "long" ? "primary" : "neutral"}>{item.kind === "long" ? "Long answer" : "Short answer"}</Badge>
                </div>
                <h3 className="mt-2.5 text-[17px] leading-snug font-semibold text-balance">{item.question}</h3>

                <div className="relative mt-4">
                  <div
                    className={cn(
                      "prose-answer text-[15px] leading-relaxed text-text-soft transition-[filter,opacity] duration-300",
                      hidden && "pointer-events-none select-none blur-[6px] opacity-60",
                    )}
                    aria-hidden={hidden}
                  >
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{item.answer}</ReactMarkdown>
                  </div>
                  {hidden && (
                    <div className="absolute inset-0 grid place-items-center">
                      <Button size="sm" onClick={() => setRevealed((s) => toggle(s, item.id))} icon={<Eye className="size-4" />}>
                        Reveal answer
                      </Button>
                    </div>
                  )}
                </div>

                <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4">
                  <button
                    onClick={() => setSources((s) => toggle(s, item.id))}
                    className="inline-flex items-center gap-1.5 text-sm font-medium text-text-soft hover:text-text"
                    aria-expanded={sources.has(item.id)}
                  >
                    <ChevronDown className={cn("size-4 transition-transform", sources.has(item.id) && "rotate-180")} />
                    {sources.has(item.id) ? "Hide source" : `Show source · ${item.source_loc}`}
                  </button>
                  <div className="flex items-center gap-2">
                    {selfTest && revealed.has(item.id) && (
                      <button onClick={() => setRevealed((s) => toggle(s, item.id))} className="text-muted hover:text-text" aria-label="Hide answer">
                        <EyeOff className="size-4" />
                      </button>
                    )}
                    <VerificationBadge verification={item.verification} loc={item.source_loc} />
                  </div>
                </div>
                {sources.has(item.id) && <SourceQuote quote={item.source_quote} loc={item.source_loc} className="mt-3 animate-fade-up" />}
              </Card>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
