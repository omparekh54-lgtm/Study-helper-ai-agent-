"use client";

import Link from "next/link";
import useSWR from "swr";
import { ArrowRight, BookOpen, FileText, Trash2 } from "lucide-react";
import { fetcher } from "@/lib/api";
import { forgetDocument, useLibrary, type LibraryEntry } from "@/lib/library";
import type { DocumentOut } from "@/lib/types";
import { pluralize, timeAgo } from "@/lib/utils";
import { Badge, Card, EmptyState, Skeleton } from "./ui";

function LibraryRow({ entry }: { entry: LibraryEntry }) {
  const { data, error } = useSWR<DocumentOut>(`/api/documents/${entry.id}`, fetcher, {
    revalidateOnFocus: false,
    shouldRetryOnError: (err) => (err as { status?: number })?.status !== 404,
  });
  const gone = (error as { status?: number } | undefined)?.status === 404;

  return (
    <li className="group relative">
      <Link
        href={`/d/${entry.id}`}
        className="flex items-center gap-4 rounded-2xl border border-border bg-surface p-4 shadow-card transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-card-lg"
      >
        <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
          <FileText className="size-5" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{data?.title ?? entry.title}</p>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
            <span className="truncate">{entry.filename}</span>
            <span>Added {timeAgo(entry.addedAt)}</span>
            {data && data.counts.topics > 0 && (
              <span>
                {pluralize(data.counts.topics, "topic")} · {pluralize(data.counts.questions, "question")}
              </span>
            )}
          </div>
        </div>
        <div className="hidden shrink-0 sm:block">
          {gone ? (
            <Badge tone="danger">Deleted</Badge>
          ) : !data ? (
            <Skeleton className="h-5 w-16" />
          ) : data.status === "ready" ? (
            <Badge tone="success">Ready</Badge>
          ) : data.status === "failed" ? (
            <Badge tone="danger">Failed</Badge>
          ) : (
            <Badge tone="warning">Building</Badge>
          )}
        </div>
        <ArrowRight className="size-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
      </Link>
      <button
        onClick={() => forgetDocument(entry.id)}
        className="absolute -top-2 -right-2 grid size-7 place-items-center rounded-full border border-border bg-surface text-muted opacity-0 shadow-card transition-opacity group-hover:opacity-100 hover:text-danger focus:opacity-100"
        aria-label={`Remove ${entry.title} from this list`}
        title="Remove from this list (doesn't delete the document)"
      >
        <Trash2 className="size-3.5" />
      </button>
    </li>
  );
}

export function Library() {
  const library = useLibrary();
  return (
    <section id="library" className="scroll-mt-24">
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Your library</h2>
          <p className="mt-1 text-sm text-muted">Documents you&apos;ve uploaded on this device.</p>
        </div>
      </div>
      {library.length === 0 ? (
        <Card>
          <EmptyState icon={<BookOpen className="size-6" />} title="Nothing here yet">
            Upload your first document above — it will appear here so you can come back to it anytime.
          </EmptyState>
        </Card>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {library.map((entry) => (
            <LibraryRow key={entry.id} entry={entry} />
          ))}
        </ul>
      )}
    </section>
  );
}
