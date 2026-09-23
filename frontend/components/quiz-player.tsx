"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Check, ChevronDown, Clock, ListChecks, Play, RotateCcw, Target, X } from "lucide-react";
import { recordScore } from "@/lib/library";
import type { Question } from "@/lib/types";
import { cn, formatDuration, LETTERS, pluralize, shuffle } from "@/lib/utils";
import { Badge, Button, Card, DifficultyBadge, Progress, SourceQuote, Toggle, VerificationBadge } from "./ui";

type Mode = "practice" | "exam";
interface Answer {
  question: Question;
  choice: number;
}

interface Props {
  questions: Question[];
  scoreKey: string;
  title: string;
  allowModeChoice?: boolean;
  defaultMode?: Mode;
  showTopic?: boolean;
  next?: { href: string; label: string };
  topicLinkBase?: string; // for mock test breakdown links: `${base}/${topicId}`
}

export function QuizPlayer({ questions, scoreKey, title, allowModeChoice, defaultMode = "practice", showTopic, next, topicLinkBase }: Props) {
  const [stage, setStage] = useState<"intro" | "playing" | "results">("intro");
  const [mode, setMode] = useState<Mode>(defaultMode);
  const [deck, setDeck] = useState<Question[]>([]);
  const [index, setIndex] = useState(0);
  const [choice, setChoice] = useState<number | null>(null);
  const [locked, setLocked] = useState(false);
  const [answers, setAnswers] = useState<Answer[]>([]);
  const [startedAt, setStartedAt] = useState(0);
  const [finishedAt, setFinishedAt] = useState(0);
  const [reviewOnly, setReviewOnly] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const begin = useCallback((items: Question[], mistakesOnly = false) => {
    setDeck(shuffle(items));
    setIndex(0);
    setChoice(null);
    setLocked(false);
    setAnswers([]);
    setReviewOnly(mistakesOnly);
    setStartedAt(Date.now());
    setStage("playing");
    requestAnimationFrame(() => containerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, []);

  const current = deck[index];
  const isLast = index === deck.length - 1;

  const confirm = useCallback(() => {
    if (choice === null || !current) return;
    if (mode === "practice" && !locked) {
      setLocked(true);
      setAnswers((a) => [...a, { question: current, choice }]);
      return;
    }
    const all = mode === "exam" ? [...answers, { question: current, choice }] : answers;
    if (mode === "exam") setAnswers(all);
    if (isLast) {
      setFinishedAt(Date.now());
      setStage("results");
      if (!reviewOnly) {
        const correct = all.filter((a) => a.choice === a.question.answer_index).length;
        recordScore(scoreKey, correct, all.length);
      }
    } else {
      setIndex((i) => i + 1);
      setChoice(null);
      setLocked(false);
    }
  }, [choice, current, mode, locked, answers, isLast, reviewOnly, scoreKey]);

  // Keyboard: 1–4 / A–D to choose, Enter to confirm / continue.
  useEffect(() => {
    if (stage !== "playing") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.metaKey || e.ctrlKey) return;
      const k = e.key.toLowerCase();
      const idx = ["1", "2", "3", "4"].indexOf(k) !== -1 ? Number(k) - 1 : ["a", "b", "c", "d"].indexOf(k);
      if (idx >= 0 && idx < 4 && !locked) {
        setChoice(idx);
        e.preventDefault();
      } else if (k === "enter" || (k === "arrowright" && locked)) {
        confirm();
        e.preventDefault();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [stage, locked, confirm]);

  if (questions.length === 0) {
    return <Card className="p-8 text-center text-muted">No questions available yet.</Card>;
  }

  if (stage === "intro") {
    const mix = (["easy", "medium", "hard"] as const).map((d) => [d, questions.filter((q) => q.difficulty === d).length] as const);
    return (
      <Card ref={containerRef} className="overflow-hidden">
        <div className="dot-grid border-b border-border bg-surface-2/40 px-6 py-10 text-center sm:px-10">
          <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-primary text-on-primary shadow-[0_10px_24px_-10px_var(--primary)]">
            <ListChecks className="size-7" aria-hidden />
          </div>
          <h2 className="mt-5 text-xl font-semibold tracking-tight">{title}</h2>
          <p className="mt-1.5 text-sm text-muted">
            {pluralize(questions.length, "question")} · about {Math.max(1, Math.round(questions.length * 0.5))} min
          </p>
          <div className="mt-4 flex justify-center gap-2">
            {mix.filter(([, n]) => n > 0).map(([d, n]) => (
              <Badge key={d} tone={d === "easy" ? "success" : d === "hard" ? "danger" : "warning"} className="capitalize">
                {n} {d}
              </Badge>
            ))}
          </div>
        </div>
        <div className="flex flex-col items-center gap-5 px-6 py-7">
          {allowModeChoice && (
            <div className="flex flex-col items-center gap-2 text-center">
              <Toggle checked={mode === "exam"} onChange={(v) => setMode(v ? "exam" : "practice")} label="Exam mode" />
              <p className="max-w-sm text-xs text-muted">
                {mode === "exam" ? "Answers are revealed at the end, like a real test." : "See the answer and explanation after each question."}
              </p>
            </div>
          )}
          <Button size="lg" onClick={() => begin(questions)} icon={<Play className="size-4" />}>
            Start {allowModeChoice && mode === "exam" ? "test" : "quiz"}
          </Button>
          <p className="hidden text-xs text-muted sm:block">Tip: press 1–4 to choose and Enter to continue.</p>
        </div>
      </Card>
    );
  }

  if (stage === "results") {
    return (
      <Results
        answers={answers}
        seconds={(finishedAt - startedAt) / 1000}
        reviewOnly={reviewOnly}
        onRetry={() => begin(questions)}
        onRetryMistakes={(qs) => begin(qs, true)}
        next={next}
        showTopic={showTopic}
        topicLinkBase={topicLinkBase}
      />
    );
  }

  const answeredCorrect = locked && choice === current.answer_index;
  return (
    <Card ref={containerRef} className="scroll-mt-24 overflow-hidden">
      <div className="border-b border-border px-5 pt-5 pb-4 sm:px-7">
        <div className="flex items-center justify-between gap-3 text-sm">
          <span className="font-medium text-text-soft">
            Question {index + 1} <span className="text-muted">of {deck.length}</span>
          </span>
          <div className="flex items-center gap-2">
            {reviewOnly && <Badge tone="warning">Mistakes review</Badge>}
            {mode === "exam" && <Badge tone="primary">Exam mode</Badge>}
            <DifficultyBadge difficulty={current.difficulty} />
          </div>
        </div>
        <Progress value={(index + (locked || mode === "exam" ? 1 : 0)) / deck.length} className="mt-3 h-1.5" />
      </div>

      <div className="px-5 py-6 sm:px-7 sm:py-7" key={current.id}>
        {showTopic && current.topic_title && <p className="mb-2 text-xs font-semibold tracking-wide text-primary uppercase">{current.topic_title}</p>}
        <h3 className="animate-fade-up text-lg leading-snug font-semibold text-balance sm:text-xl" id={`q-${current.id}`}>
          {current.question}
        </h3>

        <div role="radiogroup" aria-labelledby={`q-${current.id}`} className="mt-6 grid gap-2.5">
          {current.options.map((option, i) => {
            const selected = choice === i;
            const isAnswer = i === current.answer_index;
            const showState = locked && mode === "practice";
            return (
              <button
                key={i}
                role="radio"
                aria-checked={selected}
                disabled={locked}
                onClick={() => setChoice(i)}
                className={cn(
                  "group flex w-full items-center gap-3.5 rounded-xl border-2 px-4 py-3.5 text-left text-[15px] transition-all",
                  !showState && !selected && "border-border bg-surface hover:border-primary/50 hover:bg-primary-soft/30",
                  !showState && selected && "border-primary bg-primary-soft/60",
                  showState && isAnswer && "animate-pop border-success bg-success-soft",
                  showState && selected && !isAnswer && "border-danger bg-danger-soft",
                  showState && !selected && !isAnswer && "border-border opacity-60",
                )}
              >
                <span
                  className={cn(
                    "grid size-8 shrink-0 place-items-center rounded-lg text-sm font-semibold transition-colors",
                    showState && isAnswer
                      ? "bg-success text-white"
                      : showState && selected
                        ? "bg-danger text-white"
                        : selected
                          ? "bg-primary text-on-primary"
                          : "bg-surface-2 text-text-soft group-hover:bg-primary-soft group-hover:text-primary-ink",
                  )}
                >
                  {showState && isAnswer ? <Check className="size-4" /> : showState && selected ? <X className="size-4" /> : LETTERS[i]}
                </span>
                <span className="flex-1">{option}</span>
              </button>
            );
          })}
        </div>

        {locked && mode === "practice" && (
          <div className="mt-6 animate-fade-up space-y-3" aria-live="polite">
            <div
              className={cn(
                "rounded-xl px-4 py-3.5",
                answeredCorrect ? "bg-success-soft" : "bg-danger-soft",
              )}
            >
              <p className={cn("font-semibold", answeredCorrect ? "text-success" : "text-danger")}>
                {answeredCorrect ? "Correct!" : `Not quite — the answer is ${LETTERS[current.answer_index]}.`}
              </p>
              <p className="mt-1 text-sm text-text-soft">{current.explanation}</p>
            </div>
            <SourceQuote quote={current.source_quote} loc={current.source_loc} />
            <div className="flex justify-end">
              <VerificationBadge verification={current.verification} loc={current.source_loc} />
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-border bg-surface-2/40 px-5 py-4 sm:px-7">
        <p className="hidden text-xs text-muted sm:block">
          {locked ? "Press Enter for the next question" : "Choose an answer · keys 1–4"}
        </p>
        <Button onClick={confirm} disabled={choice === null} className="ml-auto" icon={locked || mode === "exam" ? undefined : <Check className="size-4" />}>
          {mode === "practice" && !locked ? "Check answer" : isLast ? "See results" : "Next question"}
          {(locked || mode === "exam") && <ArrowRight className="size-4" />}
        </Button>
      </div>
    </Card>
  );
}

// ---- Results ----------------------------------------------------------------------------------

function ScoreRing({ value }: { value: number }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const color = value >= 0.8 ? "var(--success)" : value >= 0.5 ? "var(--warning)" : "var(--danger)";
  return (
    <div className="relative size-36">
      <svg viewBox="0 0 120 120" className="size-full -rotate-90" aria-hidden>
        <circle cx="60" cy="60" r={r} fill="none" stroke="var(--surface-2)" strokeWidth="10" />
        <circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - value)}
          className="transition-[stroke-dashoffset] duration-1000 ease-out"
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        <span className="text-3xl font-semibold tabular-nums">{Math.round(value * 100)}%</span>
      </div>
    </div>
  );
}

function Results({
  answers,
  seconds,
  reviewOnly,
  onRetry,
  onRetryMistakes,
  next,
  showTopic,
  topicLinkBase,
}: {
  answers: Answer[];
  seconds: number;
  reviewOnly: boolean;
  onRetry: () => void;
  onRetryMistakes: (qs: Question[]) => void;
  next?: { href: string; label: string };
  showTopic?: boolean;
  topicLinkBase?: string;
}) {
  const correct = answers.filter((a) => a.choice === a.question.answer_index).length;
  const wrong = answers.filter((a) => a.choice !== a.question.answer_index);
  const ratio = answers.length ? correct / answers.length : 0;
  const [open, setOpen] = useState<number | null>(null);
  const headline =
    ratio >= 0.9 ? "Outstanding!" : ratio >= 0.7 ? "Great work!" : ratio >= 0.5 ? "Good effort — review the misses" : "Keep going — you'll get there";

  const byTopic = useMemo(() => {
    const map = new Map<string, { title: string; correct: number; total: number }>();
    for (const a of answers) {
      const id = a.question.topic_id ?? "topic";
      const entry = map.get(id) ?? { title: a.question.topic_title ?? "", correct: 0, total: 0 };
      entry.total += 1;
      if (a.choice === a.question.answer_index) entry.correct += 1;
      map.set(id, entry);
    }
    return [...map.entries()].sort((x, y) => x[1].correct / x[1].total - y[1].correct / y[1].total);
  }, [answers]);

  return (
    <div className="space-y-6">
      <Card className="animate-fade-up overflow-hidden">
        <div className="flex flex-col items-center gap-6 px-6 py-8 sm:flex-row sm:gap-10 sm:px-10">
          <ScoreRing value={ratio} />
          <div className="flex-1 text-center sm:text-left">
            <p className="text-sm font-medium text-muted">{reviewOnly ? "Mistakes review complete" : "Quiz complete"}</p>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight">{headline}</h2>
            <div className="mt-3 flex flex-wrap justify-center gap-x-5 gap-y-1 text-sm text-text-soft sm:justify-start">
              <span className="inline-flex items-center gap-1.5">
                <Check className="size-4 text-success" /> {correct} correct
              </span>
              <span className="inline-flex items-center gap-1.5">
                <X className="size-4 text-danger" /> {wrong.length} to review
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Clock className="size-4 text-muted" /> {formatDuration(seconds)}
              </span>
            </div>
            <div className="mt-6 flex flex-wrap justify-center gap-2 sm:justify-start">
              {wrong.length > 0 && (
                <Button onClick={() => onRetryMistakes(wrong.map((w) => w.question))} icon={<Target className="size-4" />}>
                  Practise my {pluralize(wrong.length, "mistake")}
                </Button>
              )}
              <Button variant={wrong.length ? "outline" : "primary"} onClick={onRetry} icon={<RotateCcw className="size-4" />}>
                Retake
              </Button>
              {next && (
                <Button variant="outline" href={next.href}>
                  {next.label} <ArrowRight className="size-4" />
                </Button>
              )}
            </div>
          </div>
        </div>
      </Card>

      {showTopic && byTopic.length > 1 && (
        <Card className="p-5 sm:p-6">
          <h3 className="font-semibold">Score by topic</h3>
          <p className="mt-0.5 text-sm text-muted">Weakest first — these are the topics to revise.</p>
          <ul className="mt-4 space-y-3">
            {byTopic.map(([id, t]) => {
              const r = t.correct / t.total;
              return (
                <li key={id} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1.5 sm:grid-cols-[minmax(0,14rem)_1fr_auto]">
                  {topicLinkBase ? (
                    <Link href={`${topicLinkBase}/${id}`} className="truncate text-sm font-medium hover:text-primary">
                      {t.title}
                    </Link>
                  ) : (
                    <span className="truncate text-sm font-medium">{t.title}</span>
                  )}
                  <Progress value={r} tone={r >= 0.7 ? "success" : "primary"} className="order-3 col-span-2 sm:order-none sm:col-span-1" />
                  <span className="text-sm text-muted tabular-nums">
                    {t.correct}/{t.total}
                  </span>
                </li>
              );
            })}
          </ul>
        </Card>
      )}

      <div>
        <h3 className="mb-3 font-semibold">Review answers</h3>
        <ol className="space-y-2.5">
          {answers.map((a, i) => {
            const ok = a.choice === a.question.answer_index;
            const expanded = open === i;
            return (
              <li key={`${a.question.id}-${i}`}>
                <Card className="overflow-hidden">
                  <button
                    className="flex w-full items-start gap-3 px-4 py-3.5 text-left"
                    onClick={() => setOpen(expanded ? null : i)}
                    aria-expanded={expanded}
                  >
                    <span className={cn("mt-0.5 grid size-6 shrink-0 place-items-center rounded-full", ok ? "bg-success-soft text-success" : "bg-danger-soft text-danger")}>
                      {ok ? <Check className="size-3.5" /> : <X className="size-3.5" />}
                    </span>
                    <span className="flex-1 text-sm font-medium">{a.question.question}</span>
                    <ChevronDown className={cn("mt-0.5 size-4 shrink-0 text-muted transition-transform", expanded && "rotate-180")} />
                  </button>
                  {expanded && (
                    <div className="animate-fade-up space-y-3 border-t border-border px-4 py-4 text-sm">
                      {!ok && (
                        <p>
                          <span className="font-medium text-danger">Your answer:</span> {LETTERS[a.choice]}. {a.question.options[a.choice]}
                        </p>
                      )}
                      <p>
                        <span className="font-medium text-success">Correct answer:</span> {LETTERS[a.question.answer_index]}.{" "}
                        {a.question.options[a.question.answer_index]}
                      </p>
                      <p className="text-text-soft">{a.question.explanation}</p>
                      <SourceQuote quote={a.question.source_quote} loc={a.question.source_loc} />
                    </div>
                  )}
                </Card>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
