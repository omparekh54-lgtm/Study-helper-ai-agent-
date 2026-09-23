"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import useSWR from "swr";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Check,
  FileDown,
  Film,
  Link2,
  ListChecks,
  Loader2,
  MessageSquareText,
  RotateCcw,
  Target,
  Trash2,
  Trophy,
} from "lucide-react";
import { api, apiUrl, fetcher } from "@/lib/api";
import { forgetDocument, rememberDocument, useScores } from "@/lib/library";
import type { DocumentOut, TopicSummary } from "@/lib/types";
import { cn, pluralize } from "@/lib/utils";
import { ProcessingView } from "./processing-view";
import { Badge, Button, Callout, Card, EmptyState, Progress, Skeleton } from "./ui";

function needsPolling(doc?: DocumentOut): number {
  if (!doc) return 0;
  const topics = doc.units.flatMap((u) => u.topics);
  if (doc.status === "queued" || doc.status === "processing") return 2500;
  if (topics.some((t) => t.kit_status === "pending" || t.kit_status === "generating")) return 2500;
  if (topics.some((t) => t.video_status === "queued" || t.video_status === "generating")) return 6000;
  return 0;
}

export function DocumentView({ id }: { id: string }) {
  const { data: doc, error, mutate } = useSWR<DocumentOut>(`/api/documents/${id}`, fetcher, {
    refreshInterval: (d) => needsPolling(d),
    shouldRetryOnError: (err) => (err as { status?: number })?.status !== 404,
    errorRetryInterval: 4000,
  });

  useEffect(() => {
    if (doc) rememberDocument({ id: doc.id, title: doc.title, filename: doc.filename });
  }, [doc?.id, doc?.title, doc?.filename]); // eslint-disable-line react-hooks/exhaustive-deps

  const status = (error as { status?: number } | undefined)?.status;
  if (status === 404) {
    return (
      <div className="mx-auto max-w-lg px-4 py-20">
        <Card>
          <EmptyState icon={<BookOpen className="size-6" />} title="Document not found" action={<Button href="/">Upload a document</Button>}>
            This link doesn&apos;t match any document — it may have been deleted.
          </EmptyState>
        </Card>
      </div>
    );
  }
  if (!doc) return <DashboardSkeleton />;

  const topicCount = doc.counts.topics;
  if (topicCount === 0 && doc.status !== "failed") return <ProcessingView doc={doc} />;
  if (topicCount === 0) return <FailedView doc={doc} onRetry={async () => mutate(await api.retryDocument(doc.id), false)} />;
  return <Dashboard doc={doc} refresh={() => mutate()} />;
}

function FailedView({ doc, onRetry }: { doc: DocumentOut; onRetry: () => Promise<unknown> }) {
  const [busy, setBusy] = useState(false);
  return (
    <div className="mx-auto max-w-lg px-4 py-20">
      <Card>
        <EmptyState
          icon={<AlertTriangle className="size-6" />}
          title="We couldn't build this study kit"
          action={
            <div className="flex gap-2">
              <Button
                loading={busy}
                icon={<RotateCcw className="size-4" />}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await onRetry();
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Try again
              </Button>
              <Button variant="outline" href="/">
                Upload another
              </Button>
            </div>
          }
        >
          {doc.error ?? "Something went wrong while processing your document."}
        </EmptyState>
      </Card>
    </div>
  );
}

function Stat({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4 shadow-card">
      <div className="flex items-center gap-2 text-sm text-muted">
        <span className="text-primary">{icon}</span>
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
    </div>
  );
}

function Dashboard({ doc, refresh }: { doc: DocumentOut; refresh: () => void }) {
  const router = useRouter();
  const [copied, setCopied] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const c = doc.counts;
  const building = c.ready_topics + c.failed_topics < c.topics;
  const verifiedPct = c.questions ? Math.round((c.verified_questions / c.questions) * 100) : 0;

  const share = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked */
    }
  };

  const remove = async () => {
    if (!confirm(`Delete "${doc.title}" and everything generated from it? This can't be undone.`)) return;
    setDeleting(true);
    try {
      await api.deleteDocument(doc.id);
      forgetDocument(doc.id);
      router.push("/");
    } catch {
      setDeleting(false);
    }
  };

  return (
    <div className="page-glow">
      <div className="mx-auto max-w-6xl px-4 pt-8 pb-10 sm:px-6 sm:pt-10">
        <nav className="text-sm text-muted" aria-label="Breadcrumb">
          <Link href="/#library" className="hover:text-text">
            Library
          </Link>
          <span className="mx-2">/</span>
          <span className="text-text-soft">{doc.filename}</span>
        </nav>

        <div className="mt-4 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl animate-fade-up">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="primary" className="uppercase">
                {doc.file_type}
              </Badge>
              <Badge>{pluralize(doc.page_count, doc.source_label)}</Badge>
              <Badge>{pluralize(doc.units.length, "unit")}</Badge>
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{doc.title}</h1>
            {doc.summary && <p className="mt-3 text-[15px] leading-relaxed text-text-soft">{doc.summary}</p>}
          </div>
          <div className="flex flex-wrap gap-2 lg:shrink-0 lg:flex-nowrap lg:justify-end">
            <Button href={`/d/${doc.id}/test`} icon={<Target className="size-4" />} disabled={c.ready_topics === 0} className={c.ready_topics === 0 ? "pointer-events-none opacity-50" : ""}>
              Mock test
            </Button>
            <Button
              variant="outline"
              href={c.ready_topics ? apiUrl(`/api/documents/${doc.id}/study-pack.pdf`) : undefined}
              external
              icon={<FileDown className="size-4" />}
              disabled={!c.ready_topics}
            >
              Study pack PDF
            </Button>
            <Button variant="outline" onClick={share} icon={copied ? <Check className="size-4 text-success" /> : <Link2 className="size-4" />}>
              {copied ? "Link copied" : "Share"}
            </Button>
            <Button variant="ghost" onClick={remove} loading={deleting} aria-label="Delete document" icon={<Trash2 className="size-4" />} />
          </div>
        </div>

        {building && (
          <Card className="mt-8 flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:gap-6">
            <div className="flex items-center gap-3">
              <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
                <Loader2 className="size-5 animate-spin" aria-hidden />
              </div>
              <div>
                <p className="font-medium">Building study kits · {c.ready_topics} of {c.topics} topics ready</p>
                <p className="text-sm text-muted">Topics unlock as they finish — you can start studying the ready ones now.</p>
              </div>
            </div>
            <Progress value={c.topics ? c.ready_topics / c.topics : 0} className="sm:ml-auto sm:max-w-xs" />
          </Card>
        )}

        {doc.status === "ready" && c.failed_topics > 0 && (
          <Callout tone="warning" className="mt-6" title={`${pluralize(c.failed_topics, "topic")} couldn't be generated`}>
            Use the retry button on the topic card — the AI service may have been busy.
          </Callout>
        )}

        <div className="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat icon={<BookOpen className="size-4" />} label="Topics" value={c.topics} sub={pluralize(doc.units.length, "unit")} />
          <Stat
            icon={<ListChecks className="size-4" />}
            label="Practice questions"
            value={c.questions}
            sub={c.questions ? `${verifiedPct}% independently verified` : "Generating…"}
          />
          <Stat icon={<MessageSquareText className="size-4" />} label="Theory Q&A" value={c.qa} sub="Exam-style model answers" />
          <Stat icon={<Film className="size-4" />} label="Video lessons" value={`${c.videos_ready}/${c.topics}`} sub={c.videos_ready < c.ready_topics ? "More rendering in the background" : "Narrated with captions"} />
        </div>
      </div>

      <div className="mx-auto max-w-6xl space-y-10 px-4 sm:px-6">
        {doc.units.map((unit) => (
          <section key={unit.idx} aria-labelledby={`unit-${unit.idx}`}>
            <div className="mb-4 flex items-baseline gap-3">
              <h2 id={`unit-${unit.idx}`} className="text-lg font-semibold tracking-tight">
                {unit.title}
              </h2>
              <span className="text-sm text-muted">{pluralize(unit.topics.length, "topic")}</span>
            </div>
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {unit.topics.map((topic) => (
                <TopicCard key={topic.id} topic={topic} docId={doc.id} onRetried={refresh} />
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

function TopicCard({ topic, docId, onRetried }: { topic: TopicSummary; docId: string; onRetried: () => void }) {
  const scores = useScores();
  const score = scores[topic.id];
  const [retrying, setRetrying] = useState(false);
  const ready = topic.kit_status === "ready";

  const body = (
    <>
      <div className="flex items-start justify-between gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-surface-2 font-mono text-xs font-semibold text-text-soft">
          {String(topic.idx + 1).padStart(2, "0")}
        </span>
        {score ? (
          <Badge tone={score.correct / score.total >= 0.8 ? "success" : score.correct / score.total >= 0.5 ? "warning" : "danger"}>
            <Trophy className="size-3" aria-hidden /> Best {score.correct}/{score.total}
          </Badge>
        ) : (
          <span className="text-xs text-muted">{topic.loc_label}</span>
        )}
      </div>
      <h3 className="mt-4 font-semibold leading-snug text-balance">{topic.title}</h3>
      <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-muted">{topic.summary}</p>

      <div className="mt-auto pt-5">
        {ready ? (
          <div className="flex items-center gap-3 text-xs font-medium text-text-soft">
            <span className="inline-flex items-center gap-1">
              <ListChecks className="size-3.5 text-primary" aria-hidden /> {topic.question_count} MCQs
            </span>
            <span className="inline-flex items-center gap-1">
              <MessageSquareText className="size-3.5 text-primary" aria-hidden /> {topic.qa_count} Q&amp;A
            </span>
            <span className="inline-flex items-center gap-1" title={`Video: ${topic.video_status}`}>
              {topic.video_status === "ready" ? (
                <Film className="size-3.5 text-accent" aria-hidden />
              ) : topic.video_status === "failed" ? (
                <Film className="size-3.5 text-muted" aria-hidden />
              ) : (
                <Loader2 className="size-3.5 animate-spin text-muted" aria-hidden />
              )}
              Video
            </span>
            <ArrowRight className="ml-auto size-4 text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
          </div>
        ) : topic.kit_status === "failed" ? (
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-danger">{topic.kit_error ?? "Generation failed"}</p>
            <Button
              size="sm"
              variant="danger"
              loading={retrying}
              icon={<RotateCcw className="size-3.5" />}
              onClick={async () => {
                setRetrying(true);
                try {
                  await api.retryTopic(topic.id);
                  onRetried();
                } finally {
                  setRetrying(false);
                }
              }}
            >
              Retry
            </Button>
          </div>
        ) : (
          <div className="space-y-2.5">
            <p className="flex items-center gap-2 text-xs font-medium text-muted">
              <Loader2 className={cn("size-3.5", topic.kit_status === "generating" && "animate-spin text-primary")} aria-hidden />
              {topic.kit_status === "generating" ? "Writing & fact-checking questions…" : "Queued"}
            </p>
            <Skeleton className="h-1.5 w-full" />
          </div>
        )}
      </div>
    </>
  );

  const cls = cn(
    "group flex h-full min-h-[196px] flex-col rounded-2xl border bg-surface p-5 shadow-card transition-all",
    ready ? "border-border hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-card-lg" : "border-border/70",
    topic.kit_status === "failed" && "border-danger/30",
  );

  return (
    <li className="animate-fade-up">
      {ready ? (
        <Link href={`/d/${docId}/t/${topic.id}`} className={cls}>
          {body}
        </Link>
      ) : (
        <div className={cls}>{body}</div>
      )}
    </li>
  );
}

function DashboardSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-10 sm:px-6" aria-busy>
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-6 h-9 w-2/3" />
      <Skeleton className="mt-3 h-4 w-1/2" />
      <div className="mt-10 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-48" />
        ))}
      </div>
    </div>
  );
}
