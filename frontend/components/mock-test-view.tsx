"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { ArrowLeft, Target } from "lucide-react";
import { fetcher } from "@/lib/api";
import { useScores } from "@/lib/library";
import type { DocumentOut, MockTest } from "@/lib/types";
import { cn } from "@/lib/utils";
import { QuizPlayer } from "./quiz-player";
import { Badge, Button, Callout, Card, Skeleton } from "./ui";

const SIZES = [10, 20, 30];

export function MockTestView({ documentId }: { documentId: string }) {
  const [count, setCount] = useState<number | null>(null);
  const { data: doc } = useSWR<DocumentOut>(`/api/documents/${documentId}`, fetcher);
  const { data: test, error, isLoading } = useSWR<MockTest>(
    count ? `/api/documents/${documentId}/mock-test?count=${count}&k=${count}` : null,
    fetcher,
    { revalidateOnFocus: false, revalidateIfStale: false },
  );
  const scores = useScores();
  const best = scores[`mock:${documentId}`];
  const available = doc?.counts.questions ?? 0;

  return (
    <div className="page-glow">
      <div className="mx-auto max-w-3xl px-4 pt-8 sm:px-6 sm:pt-10">
        <Link href={`/d/${documentId}`} className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-text">
          <ArrowLeft className="size-4" /> {doc?.title ?? "Back to document"}
        </Link>
        <header className="mt-5 mb-8">
          <p className="text-xs font-semibold tracking-wide text-primary uppercase">Mock test</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Test yourself on everything</h1>
          <p className="mt-2 text-text-soft">
            Questions are drawn from every unit so you can find the topics that need more revision.
            {best && (
              <Badge tone="primary" className="ml-2 align-middle">
                Best {best.correct}/{best.total}
              </Badge>
            )}
          </p>
        </header>

        {!count ? (
          <Card className="p-6 sm:p-8">
            <div className="flex items-center gap-3">
              <div className="grid size-11 place-items-center rounded-xl bg-primary-soft text-primary">
                <Target className="size-5" aria-hidden />
              </div>
              <div>
                <h2 className="font-semibold">How long should the test be?</h2>
                <p className="text-sm text-muted">{doc ? `${available} questions available across ${doc.counts.ready_topics} topics` : "Loading…"}</p>
              </div>
            </div>
            <div className="mt-6 grid grid-cols-3 gap-3">
              {SIZES.map((n) => {
                const disabled = !!doc && available < Math.min(n, 5);
                return (
                  <button
                    key={n}
                    disabled={disabled}
                    onClick={() => setCount(Math.min(n, Math.max(available, 5)))}
                    className={cn(
                      "rounded-2xl border-2 border-border bg-surface p-4 text-left transition-all hover:border-primary hover:bg-primary-soft/40 disabled:opacity-40",
                    )}
                  >
                    <span className="block text-2xl font-semibold tabular-nums">{Math.min(n, available || n)}</span>
                    <span className="text-sm text-muted">questions · ~{Math.round(Math.min(n, available || n) * 0.6)} min</span>
                  </button>
                );
              })}
            </div>
          </Card>
        ) : error ? (
          <Callout tone="danger" action={<Button size="sm" variant="outline" onClick={() => setCount(null)}>Back</Button>}>
            {(error as Error).message}
          </Callout>
        ) : isLoading || !test ? (
          <Skeleton className="h-96" />
        ) : (
          <QuizPlayer
            questions={test.questions}
            scoreKey={`mock:${documentId}`}
            title={`Mock test · ${test.questions.length} questions`}
            allowModeChoice
            defaultMode="exam"
            showTopic
            topicLinkBase={`/d/${documentId}/t`}
          />
        )}
      </div>
    </div>
  );
}
