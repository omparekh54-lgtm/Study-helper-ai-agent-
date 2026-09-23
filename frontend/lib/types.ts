// Mirrors backend/app/api_models.py

export type DocStatus = "queued" | "processing" | "ready" | "failed";
export type KitStatus = "pending" | "generating" | "ready" | "failed";
export type VideoStatus = "none" | "queued" | "generating" | "ready" | "failed";
export type Verification = "verified" | "quote_checked";

export interface TopicSummary {
  id: string;
  idx: number;
  title: string;
  summary: string;
  loc_label: string;
  kit_status: KitStatus;
  kit_error: string | null;
  video_status: VideoStatus;
  question_count: number;
  verified_count: number;
  qa_count: number;
}

export interface Unit {
  idx: number;
  title: string;
  topics: TopicSummary[];
}

export interface DocumentOut {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  source_label: "page" | "slide" | "section";
  page_count: number;
  status: DocStatus;
  stage: "parsing" | "outlining" | "building" | "done";
  stage_detail: string;
  error: string | null;
  summary: string;
  created_at: string;
  counts: {
    topics: number;
    ready_topics: number;
    failed_topics: number;
    questions: number;
    verified_questions: number;
    qa: number;
    videos_ready: number;
  };
  units: Unit[];
  duplicate: boolean;
}

export interface Question {
  id: number;
  question: string;
  options: string[];
  answer_index: number;
  explanation: string;
  difficulty: "easy" | "medium" | "hard";
  source_quote: string;
  source_loc: string;
  verification: Verification;
  topic_id?: string;
  topic_title?: string;
}

export interface QAItem {
  id: number;
  question: string;
  answer: string;
  kind: "short" | "long";
  source_quote: string;
  source_loc: string;
  verification: Verification;
}

export interface Scene {
  heading: string;
  narration: string;
  start: number | null;
  end: number | null;
}

export interface VideoInfo {
  status: VideoStatus;
  detail: string;
  error: string | null;
  duration: number | null;
  size_bytes: number | null;
  url: string | null;
  captions_url: string | null;
  poster_url: string | null;
  scenes: Scene[];
  narrated: boolean;
}

export interface YouTubeInfo {
  mode: "api" | "search";
  query: string;
  items: { video_id: string; title: string; channel: string; thumbnail: string; url: string }[];
  links: { label: string; query: string; url: string }[];
}

export interface TopicDetail {
  id: string;
  document_id: string;
  document_title: string;
  source_label: string;
  unit_title: string;
  idx: number;
  total_topics: number;
  title: string;
  summary: string;
  key_points: string[];
  loc_label: string;
  kit_status: KitStatus;
  kit_error: string | null;
  questions: Question[];
  qa: QAItem[];
  video: VideoInfo;
  youtube: YouTubeInfo;
  prev_topic: { id: string; title: string } | null;
  next_topic: { id: string; title: string } | null;
}

export interface MockTest {
  document_id: string;
  document_title: string;
  questions: Question[];
}

export interface Health {
  status: string;
  database: boolean;
  generator: string;
  verifier: string;
  video: boolean;
  youtube: string;
  version: string;
}
