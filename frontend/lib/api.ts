import type { DocumentOut, Health, MockTest, TopicDetail, VideoInfo } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

/** Absolute URL for backend-relative paths like `/api/topics/…/video.mp4`. */
export function apiUrl(path: string): string {
  return path.startsWith("http") ? path : `${API_URL}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), { ...init, headers: { Accept: "application/json", ...init?.headers } });
  } catch {
    throw new ApiError("Can't reach the StudyForge server. It may be waking up — please try again in a moment.", 0);
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") message = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(message, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const fetcher = <T,>(path: string) => request<T>(path);

export const api = {
  health: () => request<Health>("/api/health", { cache: "no-store" }),
  document: (id: string) => request<DocumentOut>(`/api/documents/${id}`),
  topic: (id: string) => request<TopicDetail>(`/api/topics/${id}`),
  mockTest: (id: string, count: number) => request<MockTest>(`/api/documents/${id}/mock-test?count=${count}`),
  retryDocument: (id: string) => request<DocumentOut>(`/api/documents/${id}/retry`, { method: "POST" }),
  retryTopic: (id: string) => request<{ id: string }>(`/api/topics/${id}/retry`, { method: "POST" }),
  requestVideo: (id: string) => request<VideoInfo>(`/api/topics/${id}/video`, { method: "POST" }),
  deleteDocument: (id: string) => request<void>(`/api/documents/${id}`, { method: "DELETE" }),
};

/** Upload with progress events (fetch can't report upload progress). */
export function uploadDocument(file: File, onProgress: (fraction: number) => void): Promise<DocumentOut> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", apiUrl("/api/documents"));
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) return resolve(xhr.response as DocumentOut);
      const detail = (xhr.response as { detail?: string } | null)?.detail;
      reject(new ApiError(typeof detail === "string" ? detail : `Upload failed (${xhr.status})`, xhr.status));
    };
    xhr.onerror = () =>
      reject(new ApiError("Couldn't reach the server. It may still be waking up — please try again in a few seconds.", 0));
    xhr.ontimeout = () => reject(new ApiError("The upload timed out. Please try again.", 0));
    xhr.timeout = 180_000;
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}
