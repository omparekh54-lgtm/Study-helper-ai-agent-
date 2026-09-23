"use client";

import Link from "next/link";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, Loader2, ShieldCheck, Quote } from "lucide-react";
import { cn } from "@/lib/utils";

// ---- Button -------------------------------------------------------------------------------

type Variant = "primary" | "secondary" | "ghost" | "outline" | "danger";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary:
    "bg-primary text-on-primary hover:bg-primary-hover shadow-[0_1px_0_rgba(255,255,255,0.15)_inset,0_8px_20px_-8px_var(--primary)]",
  secondary: "bg-primary-soft text-primary-ink hover:brightness-95 dark:hover:brightness-125",
  outline: "border border-border-strong bg-surface text-text hover:bg-surface-2",
  ghost: "text-text-soft hover:bg-surface-2 hover:text-text",
  danger: "bg-danger-soft text-danger hover:brightness-95 dark:hover:brightness-125",
};
const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5 rounded-lg",
  md: "h-10 px-4 text-sm gap-2 rounded-xl",
  lg: "h-12 px-6 text-[15px] gap-2.5 rounded-xl",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  href?: string;
  external?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, href, external, icon, className, children, disabled, ...props },
  ref,
) {
  const cls = cn(
    "inline-flex select-none items-center justify-center font-medium whitespace-nowrap transition-all duration-150",
    "active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50",
    variants[variant],
    sizes[size],
    className,
  );
  const content = (
    <>
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </>
  );
  if (href) {
    return external ? (
      <a href={href} target="_blank" rel="noopener noreferrer" className={cls}>
        {content}
      </a>
    ) : (
      <Link href={href} className={cls}>
        {content}
      </Link>
    );
  }
  return (
    <button ref={ref} className={cls} disabled={disabled || loading} {...props}>
      {content}
    </button>
  );
});

// ---- Surfaces -------------------------------------------------------------------------------

export function Card({ className, children, ...props }: React.ComponentProps<"div">) {
  return (
    <div className={cn("rounded-2xl border border-border bg-surface shadow-card", className)} {...props}>
      {children}
    </div>
  );
}

export function Badge({
  tone = "neutral",
  className,
  children,
  title,
}: {
  tone?: "neutral" | "primary" | "success" | "warning" | "danger" | "accent";
  className?: string;
  children: ReactNode;
  title?: string;
}) {
  const tones = {
    neutral: "bg-surface-2 text-text-soft",
    primary: "bg-primary-soft text-primary-ink",
    success: "bg-success-soft text-success",
    warning: "bg-warning-soft text-warning",
    danger: "bg-danger-soft text-danger",
    accent: "bg-accent-soft text-accent",
  };
  return (
    <span
      title={title}
      className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", tones[tone], className)}
    >
      {children}
    </span>
  );
}

export function Progress({ value, className, tone = "primary" }: { value: number; className?: string; tone?: "primary" | "success" }) {
  const pct = Math.max(0, Math.min(100, value * 100));
  return (
    <div
      className={cn("h-2 w-full overflow-hidden rounded-full bg-surface-2", className)}
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cn("h-full rounded-full transition-[width] duration-500 ease-out", tone === "success" ? "bg-success" : "bg-primary")}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin text-primary", className)} aria-hidden />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden />;
}

export function Callout({
  tone = "info",
  title,
  children,
  action,
  className,
}: {
  tone?: "info" | "warning" | "danger" | "success";
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  const map = {
    info: { cls: "bg-primary-soft text-primary-ink", Icon: Info },
    warning: { cls: "bg-warning-soft text-warning", Icon: AlertTriangle },
    danger: { cls: "bg-danger-soft text-danger", Icon: AlertTriangle },
    success: { cls: "bg-success-soft text-success", Icon: CheckCircle2 },
  }[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex items-start gap-3 rounded-xl px-4 py-3", map.cls, className)}>
      <map.Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1 text-sm">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn("opacity-90", Boolean(title) && "mt-0.5")}>{children}</div>}
      </div>
      {action}
    </div>
  );
}

export function EmptyState({ icon, title, children, action }: { icon: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-4 grid size-12 place-items-center rounded-2xl bg-primary-soft text-primary">{icon}</div>
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <p className="mt-1.5 max-w-md text-sm text-muted">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

// ---- Domain badges ------------------------------------------------------------------------------

export function VerificationBadge({ verification, loc }: { verification: string; loc?: string }) {
  const verified = verification === "verified";
  return (
    <Badge
      tone={verified ? "success" : "accent"}
      title={
        verified
          ? `The quoted source${loc ? ` (${loc})` : ""} was found in your document, and an independent AI model confirmed it supports this answer.`
          : `The quoted source${loc ? ` (${loc})` : ""} was found word-for-word in your document.`
      }
    >
      <ShieldCheck className="size-3.5" aria-hidden />
      {verified ? "Verified" : "Source-checked"}
    </Badge>
  );
}

export function DifficultyBadge({ difficulty }: { difficulty: string }) {
  const tone = difficulty === "easy" ? "success" : difficulty === "hard" ? "danger" : "warning";
  return (
    <Badge tone={tone} className="capitalize">
      {difficulty}
    </Badge>
  );
}

export function SourceQuote({ quote, loc, className }: { quote: string; loc: string; className?: string }) {
  if (!quote) return null;
  return (
    <figure className={cn("relative rounded-xl border border-border bg-surface-2/60 py-3 pr-4 pl-10 text-sm", className)}>
      <Quote className="absolute top-3 left-3.5 size-4 text-primary/60" aria-hidden />
      <blockquote className="text-text-soft italic">{quote}</blockquote>
      {loc && <figcaption className="mt-1.5 text-xs font-medium text-muted">From your notes · {loc}</figcaption>}
    </figure>
  );
}

// ---- Toggle -----------------------------------------------------------------------------------

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2.5 text-sm text-text-soft select-none">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-6 w-10 rounded-full transition-colors",
          checked ? "bg-primary" : "bg-border-strong",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 left-0.5 size-5 rounded-full bg-white shadow transition-transform",
            checked && "translate-x-4",
          )}
        />
      </button>
      {label}
    </label>
  );
}
