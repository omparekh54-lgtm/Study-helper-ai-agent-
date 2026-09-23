"use client";

import { useRouter } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import { FileText, Sparkles, UploadCloud, X } from "lucide-react";
import { apiUrl, uploadDocument } from "@/lib/api";
import { useBackend, waitForReady } from "@/lib/backend";
import { rememberDocument } from "@/lib/library";
import { cn, formatBytes } from "@/lib/utils";
import { Button, Callout, Progress } from "./ui";

const MAX_MB = 20;
const ACCEPT = ".pdf,.docx,.pptx,.txt,.md";
const EXTENSIONS = ["pdf", "docx", "pptx", "txt", "md"];

type Phase = { kind: "idle" } | { kind: "waiting"; file: File } | { kind: "uploading"; file: File; progress: number } | { kind: "done"; file: File };

export function UploadCard() {
  const router = useRouter();
  const backend = useBackend();
  const inputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingSample, setLoadingSample] = useState(false);

  const start = useCallback(
    async (file: File) => {
      setError(null);
      const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
      if (ext === "doc" || ext === "ppt") return setError(`Old .${ext} files aren't supported — save it as .${ext}x or PDF first.`);
      if (!EXTENSIONS.includes(ext)) return setError("Please upload a PDF, Word (.docx), PowerPoint (.pptx), TXT or Markdown file.");
      if (file.size > MAX_MB * 1024 * 1024) return setError(`That file is ${formatBytes(file.size)} — the limit is ${MAX_MB} MB.`);
      if (file.size === 0) return setError("That file is empty.");

      try {
        setPhase({ kind: "waiting", file });
        await waitForReady();
        setPhase({ kind: "uploading", file, progress: 0 });
        const doc = await uploadDocument(file, (progress) => setPhase({ kind: "uploading", file, progress }));
        setPhase({ kind: "done", file });
        rememberDocument({ id: doc.id, title: doc.title, filename: doc.filename });
        router.push(`/d/${doc.id}`);
      } catch (e) {
        setPhase({ kind: "idle" });
        setError(e instanceof Error ? e.message : "Upload failed. Please try again.");
      }
    },
    [router],
  );

  const trySample = async () => {
    setLoadingSample(true);
    try {
      await waitForReady();
      const res = await fetch(apiUrl("/api/sample.pdf"));
      if (!res.ok) throw new Error("Couldn't load the sample document. Please try again.");
      const blob = await res.blob();
      await start(new File([blob], "photosynthesis-notes.pdf", { type: "application/pdf" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load the sample document.");
    } finally {
      setLoadingSample(false);
    }
  };

  const busy = phase.kind !== "idle";

  return (
    <div className="relative">
      <div className="absolute -inset-3 -z-10 rounded-[28px] bg-gradient-to-br from-primary/25 via-transparent to-accent/25 blur-2xl" aria-hidden />
      <div className="rounded-3xl border border-border bg-surface p-3 shadow-card-lg sm:p-4">
        <div
          role="button"
          tabIndex={busy ? -1 : 0}
          aria-label="Upload a document"
          aria-disabled={busy}
          onClick={() => !busy && inputRef.current?.click()}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && !busy && (e.preventDefault(), inputRef.current?.click())}
          onDragOver={(e) => {
            e.preventDefault();
            if (!busy) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const file = e.dataTransfer.files?.[0];
            if (file && !busy) void start(file);
          }}
          className={cn(
            "group relative flex min-h-[270px] flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-all",
            dragging ? "scale-[1.01] border-primary bg-primary-soft" : "border-border-strong bg-surface-2/50 hover:border-primary/60 hover:bg-primary-soft/40",
            busy ? "cursor-default" : "cursor-pointer",
          )}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void start(file);
              e.target.value = "";
            }}
          />

          {phase.kind === "idle" ? (
            <>
              <div className="mb-5 grid size-14 place-items-center rounded-2xl bg-surface text-primary shadow-card transition-transform group-hover:-translate-y-0.5">
                <UploadCloud className="size-7" aria-hidden />
              </div>
              <p className="text-base font-semibold">
                {dragging ? "Drop it here" : "Drop your notes here"}
              </p>
              <p className="mt-1 text-sm text-muted">
                or <span className="font-medium text-primary underline-offset-2 group-hover:underline">browse files</span>
              </p>
              <div className="mt-5 flex flex-wrap justify-center gap-1.5">
                {["PDF", "DOCX", "PPTX", "TXT"].map((t) => (
                  <span key={t} className="rounded-md border border-border bg-surface px-2 py-0.5 text-[11px] font-semibold tracking-wide text-muted">
                    {t}
                  </span>
                ))}
                <span className="px-1 py-0.5 text-[11px] text-muted">up to {MAX_MB} MB</span>
              </div>
            </>
          ) : (
            <div className="w-full max-w-sm animate-fade-up">
              <div className="mb-5 flex items-center gap-3 rounded-xl border border-border bg-surface p-3 text-left">
                <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary-soft text-primary">
                  <FileText className="size-5" aria-hidden />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{phase.file.name}</p>
                  <p className="text-xs text-muted">{formatBytes(phase.file.size)}</p>
                </div>
              </div>
              <Progress value={phase.kind === "uploading" ? phase.progress : phase.kind === "done" ? 1 : 0.04} />
              <p className="mt-3 text-sm text-muted" aria-live="polite">
                {phase.kind === "waiting"
                  ? backend === "ready"
                    ? "Starting upload…"
                    : "Waking up the engine — this can take up to a minute on free hosting…"
                  : phase.kind === "uploading"
                    ? phase.progress < 1
                      ? `Uploading… ${Math.round(phase.progress * 100)}%`
                      : "Reading your document…"
                    : "Opening your study space…"}
              </p>
            </div>
          )}
        </div>

        {error && (
          <Callout
            tone="danger"
            className="mt-3"
            action={
              <button onClick={() => setError(null)} aria-label="Dismiss" className="opacity-70 hover:opacity-100">
                <X className="size-4" />
              </button>
            }
          >
            {error}
          </Callout>
        )}

        <div className="mt-3 flex flex-col items-center justify-between gap-2 px-1 sm:flex-row">
          <p className="text-xs text-muted">No sign-up. Your document stays private to its link.</p>
          <Button variant="secondary" size="sm" onClick={trySample} loading={loadingSample} disabled={busy} icon={<Sparkles className="size-3.5" />}>
            Try a sample document
          </Button>
        </div>
      </div>
    </div>
  );
}
