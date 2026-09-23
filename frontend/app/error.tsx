"use client";

import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center px-4 py-24 text-center">
      <div className="grid size-14 place-items-center rounded-2xl bg-danger-soft text-danger">
        <AlertTriangle className="size-7" aria-hidden />
      </div>
      <h1 className="mt-6 text-2xl font-semibold tracking-tight">Something went wrong</h1>
      <p className="mt-2 text-muted">An unexpected error occurred. Your documents are safe — try again.</p>
      <div className="mt-6 flex gap-2">
        <Button onClick={reset} icon={<RotateCcw className="size-4" />}>
          Try again
        </Button>
        <Button variant="outline" href="/">
          Home
        </Button>
      </div>
    </div>
  );
}
