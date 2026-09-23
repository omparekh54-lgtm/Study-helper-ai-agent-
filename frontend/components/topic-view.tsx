"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { ArrowLeft, ArrowRight, BookOpen, FileDown, Film, Lightbulb, ListChecks, Loader2, MessageSquareText, MonitorPlay, Trophy } from "lucide-react";
import { apiUrl, fetcher } from "@/lib/api";
import { useScores } from "@/lib/library";
import type { TopicDetail } from "@/lib/types";
import { cn, pluralize } from "@/lib/utils";
import { QAPanel } from "./qa-panel";
import { QuizPlayer } from "./quiz-player";
import { Badge, Button, Card, EmptyState, Skeleton } from "./ui";
import { VideoPanel } from "./video-panel";
import { YouTubePanel } from "./youtube-panel";

const TABS = [
  { id: "quiz", label: "Practice quiz", icon: ListChecks },
  { id: "qa", label: "Theory Q&A", icon: MessageSquareText },
  { id: "video", label: "Video lesson", icon: Film },
  { id: "more", label: "More videos", icon: MonitorPlay },
] as const;
type TabId = (typeof TABS)[number]["id"];

function useHashTab(): [TabId, (t: TabId) => void] {
  const [tab, setTab] = useState<TabId>("quiz");
  useEffect(() => {
    const read = () => {
      const h = window.location.hash.slice(1) as TabId;
      if (TABS.some((t) => t.id === h)) setTab(h);
    };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  const change = (t: TabId) => {
    setTab(t);
    history.replaceState(null, "", `#${t}`);
  };
  return [tab, change];
}

export function TopicView({ documentId, topicId }: { documentId: string; topicId: string }) {
  const [tab, setTab] = useHashTab();
  const { data: topic, error, mutate } = useSWR<TopicDetail>(`/api/topics/${topicId}`, fetcher, {
    refreshInterval: (t) =>
      !t ? 0 : t.kit_status !== "ready" ? 3000 : t.video.status === "queued" || t.video.status === "generating" ? 3000 : 0,
    shouldRetryOnError: (err) => (err as { status?: number })?.status !== 404,
  });
  const scores = useScores();

  if ((error as { status?: number } | undefined)?.status === 404) {
    return (
      <div className="mx-auto max-w-lg px-4 py-20">
        <Card>
          <EmptyState icon={<BookOpen className="size-6" />} title="Topic not found" action={<Button href={`/d/${documentId}`}>Back to document</Button>} />
        </Card>
      </div>
    );
  }
  if (!topic) return <TopicSkeleton />;

  if (topic.kit_status !== "ready") {
    return (
      <div className="mx-auto max-w-lg px-4 py-20">
        <Card>
          <EmptyState
            icon={<Loader2 className="size-6 animate-spin" />}
            title="This topic is still being prepared"
            action={<Button variant="outline" href={`/d/${documentId}`}>Back to all topics</Button>}
          >
            {topic.kit_status === "failed" ? topic.kit_error : "Questions are being written and fact-checked. This page will update automatically."}
          </EmptyState>
        </Card>
      </div>
    );
  }

  const score = scores[topic.id];
  const verified = topic.questions.filter((q) => q.verification === "verified").length;

  return (
    <div className="page-glow">
      <div className="mx-auto max-w-6xl px-4 pt-8 sm:px-6 sm:pt-10">
        <nav className="flex min-w-0 items-center gap-2 text-sm text-muted" aria-label="Breadcrumb">
          <Link href={`/d/${documentId}`} className="inline-flex min-w-0 items-center gap-1.5 hover:text-text">
            <ArrowLeft className="size-4 shrink-0" />
            <span className="truncate">{topic.document_title}</span>
          </Link>
        </nav>

        <header className="mt-5 max-w-3xl animate-fade-up">
          <p className="text-xs font-semibold tracking-wide text-primary uppercase">
            {topic.unit_title} · Topic {topic.idx + 1} of {topic.total_topics}
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{topic.title}</h1>
          <p className="mt-3 text-[15px] leading-relaxed text-text-soft">{topic.summary}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Badge>{topic.loc_label}</Badge>
            <Badge tone="success">{verified}/{topic.questions.length} questions verified</Badge>
            {score && (
              <Badge tone="primary">
                <Trophy className="size-3" /> Best score {score.correct}/{score.total}
              </Badge>
            )}
          </div>
        </header>

        <div className="mt-8 grid gap-8 pb-4 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="min-w-0">
            <div role="tablist" aria-label="Study materials" className="-mx-4 mb-5 flex gap-1 overflow-x-auto px-4 sm:mx-0 sm:px-0">
              <div className="inline-flex gap-1 rounded-2xl border border-border bg-surface p-1 shadow-card">
                {TABS.map((t) => {
                  const selected = tab === t.id;
                  const count =
                    t.id === "quiz" ? topic.questions.length : t.id === "qa" ? topic.qa.length : null;
                  const videoBusy = t.id === "video" && (topic.video.status === "queued" || topic.video.status === "generating");
                  return (
                    <button
                      key={t.id}
                      role="tab"
                      aria-selected={selected}
                      aria-controls={`panel-${t.id}`}
                      id={`tab-${t.id}`}
                      onClick={() => setTab(t.id)}
                      className={cn(
                        "inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium whitespace-nowrap transition-all",
                        selected ? "bg-primary text-on-primary shadow-sm" : "text-text-soft hover:bg-surface-2 hover:text-text",
                      )}
                    >
                      {videoBusy ? <Loader2 className="size-4 animate-spin" /> : <t.icon className="size-4" aria-hidden />}
                      {t.label}
                      {count !== null && (
                        <span className={cn("rounded-md px-1.5 text-xs", selected ? "bg-white/20" : "bg-surface-2 text-muted")}>{count}</span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="animate-fade-up" key={tab}>
              {tab === "quiz" && (
                <QuizPlayer
                  questions={topic.questions}
                  scoreKey={topic.id}
                  title={`${topic.title} — practice quiz`}
                  next={topic.next_topic ? { href: `/d/${documentId}/t/${topic.next_topic.id}`, label: "Next topic" } : undefined}
                />
              )}
              {tab === "qa" && <QAPanel items={topic.qa} topicId={topic.id} />}
              {tab === "video" && <VideoPanel topicId={topic.id} title={topic.title} video={topic.video} onChange={() => mutate()} />}
              {tab === "more" && <YouTubePanel youtube={topic.youtube} />}
            </div>
          </div>

          <aside className="space-y-4 lg:sticky lg:top-24 lg:h-fit">
            <Card className="p-5">
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <Lightbulb className="size-4 text-warning" aria-hidden /> Key points
              </h2>
              <ul className="mt-3 space-y-2.5">
                {topic.key_points.map((k, i) => (
                  <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-text-soft">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden />
                    {k}
                  </li>
                ))}
              </ul>
            </Card>
            <Card className="p-5">
              <h2 className="text-sm font-semibold">Downloads</h2>
              <div className="mt-3 grid gap-2">
                <Button variant="outline" size="sm" className="justify-start" href={apiUrl(`/api/topics/${topic.id}/quiz.pdf`)} external icon={<FileDown className="size-4" />}>
                  Practice test + answer key
                </Button>
                <Button variant="outline" size="sm" className="justify-start" href={apiUrl(`/api/topics/${topic.id}/qa.pdf`)} external icon={<FileDown className="size-4" />}>
                  Theory Q&amp;A
                </Button>
              </div>
            </Card>
          </aside>
        </div>

        <nav className="mt-6 grid gap-3 border-t border-border pt-8 sm:grid-cols-2" aria-label="Topic navigation">
          {topic.prev_topic ? (
            <Link href={`/d/${documentId}/t/${topic.prev_topic.id}`} className="group rounded-2xl border border-border bg-surface p-4 shadow-card transition-colors hover:border-primary/40">
              <span className="inline-flex items-center gap-1 text-xs text-muted">
                <ArrowLeft className="size-3.5" /> Previous topic
              </span>
              <span className="mt-1 block truncate font-medium group-hover:text-primary">{topic.prev_topic.title}</span>
            </Link>
          ) : (
            <span />
          )}
          {topic.next_topic && (
            <Link href={`/d/${documentId}/t/${topic.next_topic.id}`} className="group rounded-2xl border border-border bg-surface p-4 text-right shadow-card transition-colors hover:border-primary/40">
              <span className="inline-flex items-center gap-1 text-xs text-muted">
                Next topic <ArrowRight className="size-3.5" />
              </span>
              <span className="mt-1 block truncate font-medium group-hover:text-primary">{topic.next_topic.title}</span>
            </Link>
          )}
        </nav>
        <p className="mt-6 text-center text-xs text-muted">
          {pluralize(topic.questions.length, "question")} and {pluralize(topic.qa.length, "answer")} generated from {topic.loc_label} of your document.
        </p>
      </div>
    </div>
  );
}

function TopicSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-10 sm:px-6" aria-busy>
      <Skeleton className="h-4 w-48" />
      <Skeleton className="mt-6 h-3 w-40" />
      <Skeleton className="mt-3 h-9 w-2/3" />
      <Skeleton className="mt-3 h-4 w-1/2" />
      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_300px]">
        <Skeleton className="h-96" />
        <Skeleton className="h-64" />
      </div>
    </div>
  );
}
