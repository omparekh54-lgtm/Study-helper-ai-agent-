"use client";

import { useState } from "react";
import { ExternalLink, Play, Search } from "lucide-react";
import type { YouTubeInfo } from "@/lib/types";
import { Card } from "./ui";

export function YouTubePanel({ youtube }: { youtube: YouTubeInfo }) {
  const [playing, setPlaying] = useState<string | null>(null);

  return (
    <div className="space-y-5">
      {youtube.items.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {youtube.items.map((v) => (
            <Card key={v.video_id} className="overflow-hidden">
              <div className="relative aspect-video bg-black">
                {playing === v.video_id ? (
                  <iframe
                    src={`https://www.youtube-nocookie.com/embed/${v.video_id}?autoplay=1&rel=0`}
                    title={v.title}
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                    className="absolute inset-0 size-full"
                  />
                ) : (
                  <button onClick={() => setPlaying(v.video_id)} className="group absolute inset-0" aria-label={`Play ${v.title}`}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={v.thumbnail} alt="" className="size-full object-cover transition-transform duration-300 group-hover:scale-[1.03]" loading="lazy" />
                    <span className="absolute inset-0 grid place-items-center bg-black/25 transition-colors group-hover:bg-black/35">
                      <span className="grid size-14 place-items-center rounded-full bg-white/95 text-black shadow-lg transition-transform group-hover:scale-110">
                        <Play className="ml-0.5 size-6 fill-current" aria-hidden />
                      </span>
                    </span>
                  </button>
                )}
              </div>
              <div className="p-4">
                <p className="line-clamp-2 text-sm leading-snug font-medium">{v.title}</p>
                <div className="mt-1.5 flex items-center justify-between gap-2 text-xs text-muted">
                  <span className="truncate">{v.channel}</span>
                  <a href={v.url} target="_blank" rel="noopener noreferrer" className="inline-flex shrink-0 items-center gap-1 hover:text-text">
                    Open on YouTube <ExternalLink className="size-3" />
                  </a>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <div>
        {youtube.items.length === 0 && (
          <p className="mb-4 text-sm text-muted">
            Want another explanation? These searches are tuned to exactly this topic, so the first results are usually spot on.
          </p>
        )}
        <div className="grid gap-3 sm:grid-cols-3">
          {youtube.links.map((l) => (
            <a
              key={l.url}
              href={l.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex flex-col rounded-2xl border border-border bg-surface p-4 shadow-card transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-card-lg"
            >
              <span className="flex items-center justify-between text-sm font-semibold">
                {l.label}
                <ExternalLink className="size-3.5 text-muted transition-colors group-hover:text-primary" aria-hidden />
              </span>
              <span className="mt-2 inline-flex items-center gap-1.5 text-xs text-muted">
                <Search className="size-3.5 shrink-0" aria-hidden />
                <span className="truncate">{l.query}</span>
              </span>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
