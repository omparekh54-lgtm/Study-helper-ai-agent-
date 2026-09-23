import {
  BadgeCheck,
  Brain,
  CheckCircle2,
  FileDown,
  Film,
  Layers,
  ListChecks,
  MessageSquareText,
  ShieldCheck,
  Target,
  UploadCloud,
  Wand2,
} from "lucide-react";
import { Library } from "@/components/library";
import { UploadCard } from "@/components/upload-card";

const STEPS = [
  { icon: UploadCloud, title: "Upload your material", text: "Lecture notes, a textbook chapter or slides — PDF, Word, PowerPoint or text." },
  { icon: Layers, title: "Units & topics are mapped", text: "Gemini reads everything and organises it into a syllabus, keeping track of every page." },
  { icon: Wand2, title: "A study kit per topic", text: "MCQ practice tests, exam-style theory Q&A and a narrated video lesson for each topic." },
  { icon: ShieldCheck, title: "Every answer fact-checked", text: "Each answer must quote your document, and an independent model (Groq) double-checks it." },
];

const FEATURES = [
  { icon: ListChecks, title: "MCQ practice tests", text: "Instant feedback, explanations and the exact line from your notes that proves each answer." },
  { icon: MessageSquareText, title: "Exam-style theory Q&A", text: "Short and long answers written like model exam answers. Self-test mode hides them until you're ready." },
  { icon: Film, title: "Narrated video lessons", text: "A 60–90 second explainer for every topic, with slides, voice-over, captions and chapters." },
  { icon: Target, title: "Full mock tests", text: "Questions drawn from every unit, with a per-topic breakdown showing exactly what to revise." },
  { icon: FileDown, title: "Printable PDFs", text: "Download a complete study pack, or practice tests with an answer key, to revise offline." },
  { icon: BadgeCheck, title: "Grounded in your notes", text: "No generic internet answers — everything is generated from, and checked against, your material." },
];

export default function Home() {
  return (
    <div className="page-glow">
      {/* Hero */}
      <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pt-12 pb-20 sm:px-6 md:pt-20 lg:grid-cols-[1.05fr_1fr] lg:gap-16">
        <div className="animate-fade-up">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 text-xs font-medium text-text-soft shadow-card">
            <Brain className="size-3.5 text-primary" aria-hidden />
            AI study assistant · free &amp; open source
          </span>
          <h1 className="mt-6 text-4xl leading-[1.08] font-semibold tracking-tight text-balance sm:text-5xl lg:text-[3.4rem]">
            Turn your notes into a{" "}
            <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">complete study kit</span>
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-relaxed text-text-soft text-pretty">
            Upload a document and StudyForge maps every unit and topic, then builds practice tests, exam-style Q&amp;A and narrated
            video lessons — with every answer checked against your own material.
          </p>
          <ul className="mt-7 grid gap-2.5 text-[15px] text-text-soft sm:grid-cols-2">
            {["MCQ tests with explanations", "Theory questions & model answers", "Narrated video per topic", "Answers cite your pages"].map(
              (item) => (
                <li key={item} className="flex items-center gap-2.5">
                  <CheckCircle2 className="size-[18px] shrink-0 text-accent" aria-hidden />
                  {item}
                </li>
              ),
            )}
          </ul>
        </div>
        <div className="animate-fade-up [animation-delay:120ms]">
          <UploadCard />
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-24 border-y border-border/70 bg-surface/60">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold text-primary">How it works</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">From a PDF to a revision plan in minutes</h2>
          </div>
          <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, i) => (
              <li key={step.title} className="relative rounded-2xl border border-border bg-surface p-5 shadow-card">
                <div className="flex items-center justify-between">
                  <div className="grid size-10 place-items-center rounded-xl bg-primary-soft text-primary">
                    <step.icon className="size-5" aria-hidden />
                  </div>
                  <span className="font-mono text-xs font-medium text-muted">0{i + 1}</span>
                </div>
                <h3 className="mt-4 font-semibold">{step.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{step.text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold text-primary">What you get</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Everything you need to revise a topic</h2>
        </div>
        <div className="mt-10 grid gap-x-8 gap-y-9 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="flex gap-4">
              <div className="grid size-10 shrink-0 place-items-center rounded-xl border border-border bg-surface text-primary shadow-card">
                <f.icon className="size-5" aria-hidden />
              </div>
              <div>
                <h3 className="font-semibold">{f.title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-muted">{f.text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Library />
      </div>
    </div>
  );
}
