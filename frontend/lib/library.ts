"use client";

/**
 * Per-browser storage. StudyForge has no accounts: your library and quiz scores live in
 * this browser, and documents are reachable by their private, unguessable link.
 */

import { useSyncExternalStore } from "react";

export interface LibraryEntry {
  id: string;
  title: string;
  filename: string;
  addedAt: string;
}

export interface Score {
  correct: number;
  total: number;
  at: string;
}

const LIB_KEY = "studyforge.library.v1";
const SCORE_KEY = "studyforge.scores.v1";
const listeners = new Set<() => void>();

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable (private mode) — the app still works, it just won't remember */
  }
  cache.clear();
  listeners.forEach((l) => l());
}

// useSyncExternalStore needs a stable snapshot between changes.
const cache = new Map<string, unknown>();
function snapshot<T>(key: string, fallback: T): T {
  if (!cache.has(key)) cache.set(key, read(key, fallback));
  return cache.get(key) as T;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const onStorage = (e: StorageEvent) => {
    if (e.key === LIB_KEY || e.key === SCORE_KEY) {
      cache.clear();
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

const EMPTY_LIB: LibraryEntry[] = [];
const EMPTY_SCORES: Record<string, Score> = {};

export function useLibrary(): LibraryEntry[] {
  return useSyncExternalStore(subscribe, () => snapshot(LIB_KEY, EMPTY_LIB), () => EMPTY_LIB);
}

export function useScores(): Record<string, Score> {
  return useSyncExternalStore(subscribe, () => snapshot(SCORE_KEY, EMPTY_SCORES), () => EMPTY_SCORES);
}

export function rememberDocument(entry: Omit<LibraryEntry, "addedAt">) {
  const lib = read<LibraryEntry[]>(LIB_KEY, []);
  const existing = lib.find((e) => e.id === entry.id);
  const next = existing
    ? lib.map((e) => (e.id === entry.id ? { ...e, title: entry.title } : e))
    : [{ ...entry, addedAt: new Date().toISOString() }, ...lib].slice(0, 30);
  if (JSON.stringify(next) !== JSON.stringify(lib)) write(LIB_KEY, next);
}

export function forgetDocument(id: string) {
  write(
    LIB_KEY,
    read<LibraryEntry[]>(LIB_KEY, []).filter((e) => e.id !== id),
  );
}

/** Keeps the best score per quiz key (topic id, or `mock:<docId>`). */
export function recordScore(key: string, correct: number, total: number) {
  const scores = read<Record<string, Score>>(SCORE_KEY, {});
  const prev = scores[key];
  if (!prev || correct / total >= prev.correct / prev.total) {
    write(SCORE_KEY, { ...scores, [key]: { correct, total, at: new Date().toISOString() } });
  }
}
