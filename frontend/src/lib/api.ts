/** Backend API base URL. In dev, defaults to localhost:8000. */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface HealthResponse {
  status: string;
  version: string;
  model: string;
  max_upload_size_mb: number;
}

export interface ValidatedQuestion {
  id: string;
  unit: string;
  topic: string;
  question: string;
  marks: number;
  difficulty: string;
  bloom_level: string;
  question_type: string;
  image_path?: string;
  options?: string[];
  correct_answer?: string;
}

export interface CatalogNode {
  name: string;
  type: "subject" | "chapter" | "document";
  chunk_count?: number;
  children?: Record<string, CatalogNode>;
}

export interface KnowledgeListResponse {
  success: boolean;
  catalog: Record<string, CatalogNode>;
}

export interface KnowledgeUploadResponse {
  success: boolean;
  message: string;
  file_names: string[];
  chunk_count: number;
}

export interface AnswerKeyItem {
  id: string;
  question: string;
  marks: number;
  model_answer: string;
  key_points: string[];
  marks_breakdown: string;
  image_path?: string;
}

export interface PaperMetadata {
  institution_name: string;
  course_name: string;
  course_code: string;
  semester: string;
  exam_type: string;
  duration: string;
  maximum_marks: number;
  date?: string | null;
}

export interface GenerateResponse {
  success: boolean;
  message: string;
  final_pdf_path?: string;
  answer_key_pdf_path?: string;
  elapsed_seconds: number;
  rag_chunk_count: number;
  errors: string[];
  questions?: ValidatedQuestion[];
  answer_key?: AnswerKeyItem[];
}

export interface PapersResponse {
  total: number;
  files: string[];
}

export interface AnalyticsResponse {
  total_papers: number;
  total_questions: number;
  average_generation_time: number;
  bloom_distribution: Record<string, number>;
  difficulty_distribution: Record<string, number>;
  recent_activity: { date: string; papers: number }[];
}

function parseApiError(data: unknown, status: number): { message: string; errors?: string[] } {
  if (!data || typeof data !== "object") {
    return { message: `Request failed (${status})` };
  }

  const body = data as Record<string, unknown>;

  if ("detail" in body) {
    const detail = body.detail;
    if (typeof detail === "string") {
      return { message: detail };
    }
    if (detail && typeof detail === "object") {
      const obj = detail as Record<string, unknown>;
      return {
        message: String(obj.message ?? "Request failed"),
        errors: Array.isArray(obj.errors) ? obj.errors.map(String) : undefined,
      };
    }
  }

  if (typeof body.message === "string") {
    return {
      message: body.message,
      errors: Array.isArray(body.errors) ? body.errors.map(String) : undefined,
    };
  }

  return { message: `Request failed (${status})` };
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new Error(
      "Cannot connect to the backend. Start it with: cd backend && python -m app.main",
    );
  }
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await apiFetch("/health");
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function getAnalytics(): Promise<AnalyticsResponse> {
  const res = await apiFetch("/analytics");
  if (!res.ok) throw new Error("Failed to fetch analytics");
  return res.json();
}

export interface GoogleItem {
  id: string;
  name: string;
  mime_type?: string;
  modified_time?: string;
  size?: number;
  kind?: string;
  supported?: boolean;
  source?: string;
}

export interface GoogleAuthResponse {
  authorization_url: string;
  session_id: string;
}

export async function startGoogleOauth(): Promise<GoogleAuthResponse> {
  const res = await apiFetch("/google/oauth/start", { method: "POST" });
  if (!res.ok) throw new Error("Google OAuth start failed");
  return res.json();
}

export async function getGoogleDriveItems(
  folderId: string,
  sessionId: string,
): Promise<GoogleItem[]> {
  const res = await apiFetch(
    `/google/drive/folders/${encodeURIComponent(folderId)}/items?session_id=${encodeURIComponent(sessionId)}`,
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to load Google Drive items");
  }
  return res.json();
}

export async function getGoogleClassroomCourses(sessionId: string): Promise<GoogleItem[]> {
  const res = await apiFetch(
    `/google/classroom/courses?session_id=${encodeURIComponent(sessionId)}`,
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to load Google Classroom courses");
  }
  return res.json();
}

export async function getGoogleClassroomCourseMaterials(
  courseId: string,
  sessionId: string,
): Promise<GoogleItem[]> {
  const res = await apiFetch(
    `/google/classroom/courses/${encodeURIComponent(courseId)}/materials?session_id=${encodeURIComponent(sessionId)}`,
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to load Classroom course materials");
  }
  return res.json();
}

export async function generatePaper(
  files: File[],
  form: Record<string, string>,
): Promise<GenerateResponse> {
  const body = new FormData();
  if (files && files.length > 0) {
    files.forEach((f) => body.append("files", f));
  }
  Object.entries(form).forEach(([k, v]) => {
    if (v !== undefined && v !== null) {
      body.append(k, v);
    }
  });

  const res = await apiFetch("/generate", { method: "POST", body });
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const { message, errors } = parseApiError(data, res.status);
    const err = new Error(message) as Error & { errors?: string[] };
    err.errors = errors;
    throw err;
  }

  return data as GenerateResponse;
}

export async function listPapers(): Promise<PapersResponse> {
  const res = await apiFetch("/papers");
  if (!res.ok) throw new Error("Failed to load papers");
  return res.json();
}

export async function getKnowledgeList(): Promise<KnowledgeListResponse> {
  const res = await apiFetch("/knowledge/list");
  if (!res.ok) throw new Error("Failed to load knowledge base catalog");
  return res.json();
}

export async function uploadKnowledge(
  subject: string,
  chapter: string,
  files: File[],
): Promise<KnowledgeUploadResponse> {
  const body = new FormData();
  body.append("subject", subject);
  body.append("chapter", chapter);
  files.forEach((f) => body.append("files", f));

  const res = await apiFetch("/knowledge/upload", { method: "POST", body });
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const { message, errors } = parseApiError(data, res.status);
    const err = new Error(message) as Error & { errors?: string[] };
    err.errors = errors;
    throw err;
  }

  return data as KnowledgeUploadResponse;
}

export async function downloadFile(filename: string): Promise<void> {
  const res = await apiFetch(`/download/${encodeURIComponent(filename)}`);
  if (!res.ok) throw new Error("Download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function basename(p: string): string {
  return p.split(/[/\\]/).pop() || p;
}

export async function printEditedPaper(
  questions: ValidatedQuestion[],
  answerKey: AnswerKeyItem[],
  paperMetadata: PaperMetadata,
): Promise<GenerateResponse> {
  const res = await apiFetch("/generate/pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      questions,
      answer_key: answerKey,
      paper_metadata: paperMetadata,
    }),
  });
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const { message, errors } = parseApiError(data, res.status);
    const err = new Error(message) as Error & { errors?: string[] };
    err.errors = errors;
    throw err;
  }

  return data as GenerateResponse;
}

export async function updateAnswerKey(
  questions: ValidatedQuestion[],
  answerKey: AnswerKeyItem[],
  modifiedQuestionIds: string[],
): Promise<GenerateResponse> {
  const res = await apiFetch("/answer-key/update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      questions,
      answer_key: answerKey,
      modified_question_ids: modifiedQuestionIds,
    }),
  });
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const { message, errors } = parseApiError(data, res.status);
    const err = new Error(message) as Error & { errors?: string[] };
    err.errors = errors;
    throw err;
  }

  return data as GenerateResponse;
}
