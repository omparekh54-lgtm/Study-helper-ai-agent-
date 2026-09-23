"use client";

/**
 * The API runs on a free instance that sleeps after 15 idle minutes and takes ~30–60 s to
 * wake. We ping it as soon as the app loads so it is usually awake by the time you upload,
 * and we tell the user what's going on instead of showing a mysterious spinner.
 */

import { useEffect, useSyncExternalStore } from "react";
import { api } from "./api";

export type BackendState = "checking" | "waking" | "ready" | "down";

let state: BackendState = "checking";
let started = false;
const listeners = new Set<() => void>();

function set(next: BackendState) {
  if (next !== state) {
    state = next;
    listeners.forEach((l) => l());
  }
}

async function probe() {
  const begin = Date.now();
  const slowTimer = setTimeout(() => state === "checking" && set("waking"), 2500);
  while (Date.now() - begin < 120_000) {
    try {
      await api.health();
      clearTimeout(slowTimer);
      set("ready");
      return;
    } catch {
      set("waking");
      await new Promise((r) => setTimeout(r, 3000));
    }
  }
  clearTimeout(slowTimer);
  set("down");
}

export function wakeBackend() {
  if (!started) {
    started = true;
    void probe();
  }
}

export function retryBackend() {
  started = false;
  set("checking");
  wakeBackend();
}

/** Resolves once the API answers (or rejects after `timeoutMs`). */
export function waitForReady(timeoutMs = 120_000): Promise<void> {
  wakeBackend();
  if (state === "ready") return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      listeners.delete(check);
      reject(new Error("The StudyForge engine didn't wake up in time. Please try again."));
    }, timeoutMs);
    function check() {
      if (state === "ready") {
        clearTimeout(timer);
        listeners.delete(check);
        resolve();
      } else if (state === "down") {
        retryBackend();
      }
    }
    listeners.add(check);
  });
}

export function useBackend(): BackendState {
  useEffect(() => wakeBackend(), []);
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => state,
    () => "checking" as BackendState,
  );
}
