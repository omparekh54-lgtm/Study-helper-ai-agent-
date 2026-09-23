"use client";

import { useEffect, useRef, useState } from "react";
import { Captions, Download, Film, Loader2, Play, RotateCcw, Sparkles } from "lucide-react";
import { api, apiUrl } from "@/lib/api";
import type { VideoInfo } from "@/lib/types";
import { cn, formatBytes, formatDuration } from "@/lib/utils";
import { Button, Callout, Card } from "./ui";

export function VideoPanel({ topicId, title, video, onChange }: { topicId: string; title: string; video: VideoInfo; onChange: () => void }) {
  const [requesting, setRequesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const request = async () => {
    setRequesting(true);
    setError(null);
    try {
      await api.requestVideo(topicId);
      onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't start the video.");
    } finally {
      setRequesting(false);
    }
  };

  if (video.status === "ready" && video.url) {
    return <Player video={video} title={title} />;
  }

  const inProgress = video.status === "queued" || video.status === "generating";
  return (
    <div className="space-y-5">
      <Card className="overflow-hidden">
        <div className="relative aspect-video overflow-hidden bg-[#0a0e1e]">
          <div className="absolute inset-0 bg-[radial-gradient(40rem_20rem_at_80%_0%,rgba(129,140,248,0.35),transparent_60%),radial-gradient(30rem_18rem_at_0%_100%,rgba(45,212,191,0.22),transparent_60%)]" />
          <div className="relative flex h-full flex-col items-center justify-center px-6 text-center text-white">
            {inProgress ? (
              <>
                <Loader2 className="size-9 animate-spin text-[#a5b4fc]" aria-hidden />
                <p className="mt-4 text-lg font-semibold">Creating your video lesson</p>
                <p className="mt-1 text-sm text-white/70" aria-live="polite">
                  {video.status === "queued" ? "Waiting for a free slot…" : video.detail || "Starting…"}
                </p>
                <p className="mt-4 max-w-sm text-xs text-white/50">
                  Slides are designed, narrated and encoded on our free server — usually about a minute. This page updates by itself.
                </p>
              </>
            ) : (
              <>
                <div className="grid size-14 place-items-center rounded-2xl bg-white/10 backdrop-blur">
                  <Film className="size-7" aria-hidden />
                </div>
                <p className="mt-4 text-lg font-semibold">Narrated video lesson</p>
                <p className="mt-1 max-w-sm text-sm text-white/70">
                  A 60–90 second explainer with slides, voice-over and captions, made from this topic&apos;s pages.
                </p>
                <Button
                  className="mt-5"
                  onClick={request}
                  loading={requesting}
                  icon={video.status === "failed" ? <RotateCcw className="size-4" /> : <Sparkles className="size-4" />}
                >
                  {video.status === "failed" ? "Try again" : "Create video lesson"}
                </Button>
              </>
            )}
          </div>
        </div>
      </Card>
      {(error || video.error) && <Callout tone="danger">{error ?? video.error}</Callout>}
      {video.scenes.length > 0 && (
        <Card className="p-5">
          <h3 className="text-sm font-semibold">What this lesson covers</h3>
          <ol className="mt-3 space-y-2">
            {video.scenes.map((s, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="w-5 shrink-0 font-mono text-xs leading-5 text-muted">{i + 1}</span>
                <span className="text-text-soft">{s.heading || s.narration.slice(0, 80)}</span>
              </li>
            ))}
          </ol>
        </Card>
      )}
    </div>
  );
}

function Player({ video, title }: { video: VideoInfo; title: string }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  const scenes = video.scenes.filter((s) => s.start !== null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onTime = () => setTime(el.currentTime);
    el.addEventListener("timeupdate", onTime);
    return () => el.removeEventListener("timeupdate", onTime);
  }, []);

  const active = scenes.reduce((acc, s, i) => ((s.start ?? 0) <= time + 0.05 ? i : acc), 0);
  const seek = (t: number) => {
    const el = ref.current;
    if (!el) return;
    el.currentTime = t;
    void el.play();
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
      <div className="space-y-3">
        <Card className="overflow-hidden bg-black">
          <video
            ref={ref}
            controls
            playsInline
            preload="metadata"
            crossOrigin="anonymous"
            className="aspect-video w-full bg-black"
            src={apiUrl(video.url!)}
            poster={video.poster_url ? apiUrl(video.poster_url) : undefined}
            aria-label={`Video lesson: ${title}`}
          >
            {video.captions_url && <track kind="captions" src={apiUrl(video.captions_url)} srcLang="en" label="English" default />}
          </video>
        </Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="flex items-center gap-3 text-sm text-muted">
            <span className="inline-flex items-center gap-1.5">
              <Play className="size-3.5" /> {formatDuration(video.duration ?? 0)}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Captions className="size-4" /> Captions on
            </span>
            {video.size_bytes && <span>{formatBytes(video.size_bytes)}</span>}
          </p>
          <Button variant="outline" size="sm" href={`${apiUrl(video.url!)}?download=true`} external icon={<Download className="size-4" />}>
            Download MP4
          </Button>
        </div>
        {!video.narrated && (
          <Callout tone="warning">Voice narration was unavailable when this video was made, so it plays with captions only.</Callout>
        )}
      </div>

      <Card className="h-fit p-2">
        <p className="px-3 pt-2 pb-1 text-xs font-semibold tracking-wide text-muted uppercase">Chapters</p>
        <ol>
          {scenes.map((s, i) => (
            <li key={i}>
              <button
                onClick={() => seek(s.start ?? 0)}
                className={cn(
                  "flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-colors",
                  i === active ? "bg-primary-soft text-primary-ink" : "text-text-soft hover:bg-surface-2",
                )}
                aria-current={i === active ? "true" : undefined}
              >
                <span className="mt-px w-9 shrink-0 font-mono text-xs tabular-nums opacity-80">{formatDuration(s.start ?? 0)}</span>
                <span className="font-medium">{s.heading || `Scene ${i + 1}`}</span>
              </button>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
