import { Compass } from "lucide-react";
import { Button } from "@/components/ui";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center px-4 py-24 text-center">
      <div className="grid size-14 place-items-center rounded-2xl bg-primary-soft text-primary">
        <Compass className="size-7" aria-hidden />
      </div>
      <h1 className="mt-6 text-2xl font-semibold tracking-tight">Page not found</h1>
      <p className="mt-2 text-muted">The page you&apos;re looking for doesn&apos;t exist or has moved.</p>
      <Button href="/" className="mt-6">
        Go to StudyForge
      </Button>
    </div>
  );
}
