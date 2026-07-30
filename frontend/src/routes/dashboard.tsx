import { createFileRoute, Link } from "@tanstack/react-router";
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  basename,
  downloadFile,
  generatePaper,
  getHealth,
  startGoogleOauth,
  getGoogleDriveItems,
  getGoogleClassroomCourses,
  getGoogleClassroomCourseMaterials,
  printEditedPaper,
  updateAnswerKey,
  type GenerateResponse,
  type HealthResponse,
  type GoogleItem,
  type ValidatedQuestion,
  type AnswerKeyItem,
  type PaperMetadata,
} from "@/lib/api";

interface SelectedGoogleItem {
  id: string;
  name: string;
  type: "file" | "folder";
  source: "drive" | "classroom";
  mime_type?: string;
  supported?: boolean;
}

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Paper Studio - Question Paper Generator" },
      { name: "description", content: "AI-assisted university examination paper creation." },
    ],
  }),
  component: Dashboard,
});

const EXAM_TYPES = [
  "End Semester Examination",
  "Internal Assessment",
  "Mid Semester Examination",
  "Unit Test",
];
const DURATIONS = ["3 Hours", "2 Hours", "1.5 Hours", "1 Hour"];
const ACCEPTED = [".pdf", ".txt", ".docx", ".xlsx"];

interface FormState {
  institution_name: string;
  course_name: string;
  course_code: string;
  semester: string;
  exam_type: string;
  duration: string;
  exam_date: string;
  total_marks: number;
  two_mark_questions: number;
  five_mark_questions: number;
  ten_mark_questions: number;
  fifteen_mark_questions: number;
  easy_percentage: number;
  medium_percentage: number;
  hard_percentage: number;
}

const INITIAL: FormState = {
  institution_name: "",
  course_name: "",
  course_code: "",
  semester: "",
  exam_type: "End Semester Examination",
  duration: "3 Hours",
  exam_date: "",
  total_marks: 100,
  two_mark_questions: 5,
  five_mark_questions: 6,
  ten_mark_questions: 3,
  fifteen_mark_questions: 2,
  easy_percentage: 30,
  medium_percentage: 50,
  hard_percentage: 20,
};

function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthOk, setHealthOk] = useState<boolean>(false);
  const [files, setFiles] = useState<File[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(INITIAL);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [error, setError] = useState<{ message: string; errors?: string[] } | null>(null);

  // Human approval / Editable preview states
  const [questions, setQuestions] = useState<ValidatedQuestion[]>([]);
  const [answerKey, setAnswerKey] = useState<AnswerKeyItem[]>([]);
  const [modifiedQuestionIds, setModifiedQuestionIds] = useState<Set<string>>(new Set());
  const [pdfResult, setPdfResult] = useState<GenerateResponse | null>(null);
  const [isPrinting, setIsPrinting] = useState(false);
  const [isUpdatingAnswerKey, setIsUpdatingAnswerKey] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Google OAuth states
  const [googleSessionId, setGoogleSessionId] = useState<string | null>(null);
  const [googleSelections, setGoogleSelections] = useState<SelectedGoogleItem[]>([]);
  const [googleError, setGoogleError] = useState<string | null>(null);

  const maxMb = health?.max_upload_size_mb ?? 50;

  useEffect(() => {
    const tick = () =>
      getHealth()
        .then((h) => {
          setHealth(h);
          setHealthOk(true);
        })
        .catch(() => setHealthOk(false));
    tick();
    const id = setInterval(tick, 30000);
    return () => clearInterval(id);
  }, []);

  // Process Google OAuth Redirection Callbacks
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const conn = params.get("google_connected");
    const err = params.get("google_error");
    if (conn) {
      localStorage.setItem("google_session_id", conn);
      setGoogleSessionId(conn);
      const cleanUrl = new URL(window.location.href);
      cleanUrl.searchParams.delete("google_connected");
      window.history.replaceState({}, document.title, cleanUrl.pathname + cleanUrl.search);
    } else if (err) {
      setGoogleError(err);
      const cleanUrl = new URL(window.location.href);
      cleanUrl.searchParams.delete("google_error");
      window.history.replaceState({}, document.title, cleanUrl.pathname + cleanUrl.search);
    } else {
      const saved = localStorage.getItem("google_session_id");
      if (saved) setGoogleSessionId(saved);
    }
  }, []);

  const onConnectGoogle = async () => {
    try {
      const auth = await startGoogleOauth();
      window.location.href = auth.authorization_url;
    } catch (e) {
      setGoogleError((e as Error).message);
    }
  };

  const onDisconnectGoogle = () => {
    localStorage.removeItem("google_session_id");
    setGoogleSessionId(null);
    setGoogleSelections([]);
  };

  const update = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const computedMarks =
    2 * form.two_mark_questions +
    5 * form.five_mark_questions +
    10 * form.ten_mark_questions +
    15 * form.fifteen_mark_questions;
  const marksOk = computedMarks === form.total_marks;
  const diffSum = form.easy_percentage + form.medium_percentage + form.hard_percentage;
  const diffOk = diffSum === 100;

  const validateFiles = (list: File[]): string | null => {
    for (const f of list) {
      const ext = "." + (f.name.split(".").pop() || "").toLowerCase();
      if (!ACCEPTED.includes(ext)) return `Unsupported file type: ${f.name}`;
      if (f.size > maxMb * 1024 * 1024) return `${f.name} exceeds ${maxMb} MB limit`;
    }
    return null;
  };

  const addFiles = (incoming: FileList | File[]) => {
    const arr = Array.from(incoming);
    const merged = [...files, ...arr];
    const err = validateFiles(merged);
    setFileError(err);
    setFiles(merged);
  };

  const removeFile = (i: number) => {
    const next = files.filter((_, idx) => idx !== i);
    setFiles(next);
    setFileError(validateFiles(next));
  };

  const hasDocuments = files.length > 0 || googleSelections.length > 0;
  const canGenerate =
    healthOk && hasDocuments && !fileError && marksOk && diffOk && !loading;

  const onGenerate = async () => {
    if (!canGenerate) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const fileIds = googleSelections.filter((x) => x.type === "file").map((x) => x.id);
      const folderIds = googleSelections.filter((x) => x.type === "folder").map((x) => x.id);

      const payload: Record<string, string> = {
        total_marks: String(form.total_marks),
        two_mark_questions: String(form.two_mark_questions),
        five_mark_questions: String(form.five_mark_questions),
        ten_mark_questions: String(form.ten_mark_questions),
        fifteen_mark_questions: String(form.fifteen_mark_questions),
        easy_percentage: String(form.easy_percentage),
        medium_percentage: String(form.medium_percentage),
        hard_percentage: String(form.hard_percentage),
        institution_name: form.institution_name,
        course_name: form.course_name,
        course_code: form.course_code,
        semester: form.semester,
        exam_type: form.exam_type,
        duration: form.duration,
        exam_date: form.exam_date,
        google_session_id: googleSessionId || "",
        google_file_ids: JSON.stringify(fileIds),
        google_folder_ids: JSON.stringify(folderIds),
      };
      const res = await generatePaper(files, payload);
      setResult(res);
      setQuestions(res.questions || []);
      setAnswerKey(res.answer_key || []);
      setModifiedQuestionIds(new Set());
      setPdfResult(null);
    } catch (e) {
      const err = e as Error & { errors?: string[] };
      setError({ message: err.message, errors: err.errors });
    } finally {
      setLoading(false);
    }
  };

  const onUpdateAnswerKey = async () => {
    if (modifiedQuestionIds.size === 0) return;
    setIsUpdatingAnswerKey(true);
    setError(null);
    try {
      const res = await updateAnswerKey(questions, answerKey, [...modifiedQuestionIds]);
      setAnswerKey(res.answer_key || []);
      setModifiedQuestionIds(new Set());
      setPdfResult(null);
    } catch (e) {
      const err = e as Error & { errors?: string[] };
      setError({ message: err.message, errors: err.errors });
    } finally {
      setIsUpdatingAnswerKey(false);
    }
  };

  const onPrint = async () => {
    setIsPrinting(true);
    setError(null);
    try {
      const metadata: PaperMetadata = {
        institution_name: form.institution_name,
        course_name: form.course_name,
        course_code: form.course_code,
        semester: form.semester,
        exam_type: form.exam_type,
        duration: form.duration,
        maximum_marks: form.total_marks,
        date: form.exam_date || null,
      };
      const res = await printEditedPaper(questions, answerKey, metadata);
      setPdfResult(res);
    } catch (e) {
      const err = e as Error & { errors?: string[] };
      setError({ message: err.message, errors: err.errors });
    } finally {
      setIsPrinting(false);
    }
  };

  return (
    <div className="relative min-h-screen text-foreground pb-12">
      <BackgroundFX />
      <Header healthOk={healthOk} health={health} />
      <main className="relative mx-auto w-full max-w-[1440px] px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <p className="text-sm font-medium text-primary/80">Examination Paper Studio</p>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              Configure &amp; generate your paper
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Upload course materials, set examination parameters, and generate a structured
              question paper with an answer key.
            </p>
          </div>
          <Link
            to="/history"
            className="self-start sm:self-center inline-flex items-center gap-2 rounded-lg border border-border/80 bg-white/90 px-4 py-2.5 text-xs font-semibold text-foreground transition hover:border-primary/30 hover:bg-primary/[0.04]"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M12 8v4l3 3" /><circle cx="12" cy="12" r="10" />
            </svg>
            Browse History
          </Link>
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-12 xl:items-start">
          {result ? (
            /* STAGE 2: Review and Edit Draft */
            <>
              {/* Left Column: Editable Previews */}
              <div className="space-y-6 xl:col-span-8">
                <PreviewStudio
                  questions={questions}
                  setQuestions={setQuestions}
                  answerKey={answerKey}
                  setAnswerKey={setAnswerKey}
                  onQuestionEdited={(questionId) =>
                    setModifiedQuestionIds((previous) => new Set(previous).add(questionId))
                  }
                />
              </div>

              {/* Right Column: Print Controls Sidebar */}
              <div className="flex flex-col gap-5 xl:col-span-4 xl:sticky xl:top-[5.5rem]">
                <Card
                  title="Review & Print"
                  description="Approve the question paper layout, model answers, and grading points. Print to create official PDF copies."
                >
                  <div className="space-y-4">
                    {/* Status Badge */}
                    <div className="flex items-center justify-between text-xs border-b pb-3">
                      <span className="font-semibold text-slate-600">Draft Status:</span>
                      <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-700 font-semibold border border-amber-200">
                        Awaiting Print
                      </span>
                    </div>

                    <div className="space-y-1.5 text-xs text-muted-foreground">
                      <p>• Institution: <b>{form.institution_name || "N/A"}</b></p>
                      <p>• Course: <b>{form.course_name} ({form.course_code})</b></p>
                      <p>• Type: <b>{form.exam_type}</b></p>
                      <p>• Marks: <b>{form.total_marks}</b></p>
                    </div>

                    {pdfResult && (
                      <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-800 space-y-1">
                        <p className="font-semibold">✓ Print successful!</p>
                        <p className="text-emerald-700">Official A4 documents compiled.</p>
                      </div>
                    )}

                    {error && (
                      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-xs font-medium text-red-800">
                        <p className="font-semibold">Draft update error:</p>
                        <p className="text-red-700 mt-1">{error.message}</p>
                      </div>
                    )}

                    <div className="space-y-3 pt-2">
                      <button
                        onClick={onUpdateAnswerKey}
                        disabled={isUpdatingAnswerKey || modifiedQuestionIds.size === 0}
                        className="w-full rounded-xl border border-primary/30 bg-primary/5 px-6 py-3 text-sm font-semibold text-primary transition hover:bg-primary/10 focus:outline-none focus:ring-4 focus:ring-primary/15 disabled:cursor-not-allowed disabled:opacity-45 cursor-pointer"
                      >
                        {isUpdatingAnswerKey
                          ? "Updating Answer Key…"
                          : `Update Answer Key${modifiedQuestionIds.size ? ` (${modifiedQuestionIds.size})` : ""}`}
                      </button>
                      {modifiedQuestionIds.size > 0 && (
                        <p className="text-center text-xs text-amber-700">
                          Update the answer key before printing to refresh answers for edited questions.
                        </p>
                      )}
                      <button
                        onClick={onPrint}
                        disabled={isPrinting || isUpdatingAnswerKey || modifiedQuestionIds.size > 0}
                        className="group relative w-full overflow-hidden rounded-xl bg-primary px-6 py-3.5 text-sm font-semibold tracking-wide text-primary-foreground shadow-[0_4px_14px_-4px_oklch(0.32_0.07_257/0.45)] ring-1 ring-primary/20 transition-all duration-200 hover:bg-primary/95 hover:shadow-[0_8px_24px_-6px_oklch(0.32_0.07_257/0.5)] focus:outline-none focus:ring-4 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none cursor-pointer"
                      >
                        {isPrinting ? "Compiling PDFs…" : "Print Paper & Answer Key"}
                      </button>

                      {pdfResult && (
                        <div className="space-y-2.5 pt-2 border-t border-slate-100">
                          <DownloadButton
                            label="Download Question Paper"
                            filename={basename(pdfResult.final_pdf_path || "")}
                          />
                          <DownloadButton
                            label="Download Answer Key"
                            filename={basename(pdfResult.answer_key_pdf_path || "")}
                            variant="outline"
                          />
                        </div>
                      )}

                      <button
                        onClick={() => {
                          setResult(null);
                          setPdfResult(null);
                        }}
                        className="w-full text-center text-xs font-semibold text-muted-foreground hover:text-foreground py-2 transition-colors cursor-pointer"
                      >
                        ← Modify Parameters &amp; Regenerate
                      </button>
                    </div>
                  </div>
                </Card>
              </div>
            </>
          ) : (
            /* STAGE 1: Configuration / Upload Details */
            <>
              {/* Left Column: Input and configuration panels */}
              <div className="space-y-6 xl:col-span-8">
                <UploadCard
                  files={files}
                  fileError={fileError}
                  maxMb={maxMb}
                  onAdd={addFiles}
                  onRemove={removeFile}
                  fileInputRef={fileInputRef}
                  googleSessionId={googleSessionId}
                  googleSelections={googleSelections}
                  setGoogleSelections={setGoogleSelections}
                  googleError={googleError}
                  setGoogleError={setGoogleError}
                  onConnectGoogle={onConnectGoogle}
                  onDisconnectGoogle={onDisconnectGoogle}
                />

                <div className="grid gap-6 md:grid-cols-2">
                  <ExamDetailsCard form={form} update={update} />
                  <QuestionsCard
                    form={form}
                    update={update}
                    computed={computedMarks}
                    ok={marksOk}
                  />
                </div>

                <DifficultyCard form={form} update={update} sum={diffSum} ok={diffOk} />
              </div>

              {/* Right Column: Generation control & output panels (Sticky Sidebar) */}
              <div className="flex flex-col gap-5 xl:col-span-4 xl:sticky xl:top-[5.5rem]">
                <ResultsPanel loading={loading} result={result} error={error} />
                <button
                  onClick={onGenerate}
                  disabled={!canGenerate}
                  className="group relative w-full overflow-hidden rounded-xl bg-primary px-6 py-4 text-sm font-semibold tracking-wide text-primary-foreground shadow-[0_4px_14px_-4px_oklch(0.32_0.07_257/0.45)] ring-1 ring-primary/20 transition-all duration-200 hover:bg-primary/95 hover:shadow-[0_8px_24px_-6px_oklch(0.32_0.07_257/0.5)] focus:outline-none focus:ring-4 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none cursor-pointer"
                >
                  <span className="relative flex items-center justify-center gap-2">
                    {loading ? (
                      <>
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground" />
                        Generating question paper…
                      </>
                    ) : (
                      <>
                        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12 3v12" /><path d="m8 11 4 4 4-4" /><path d="M4 21h16" /></svg>
                        Generate Question Paper
                      </>
                    )}
                  </span>
                </button>
                {!canGenerate && !loading && (
                  <p className="text-center text-xs text-muted-foreground">
                    {!healthOk
                      ? "Start the backend to enable generation."
                      : !hasDocuments
                        ? "Upload at least one course document or select from Google Drive/Classroom."
                        : !marksOk
                          ? "Question marks must equal the total."
                          : !diffOk
                            ? "Difficulty percentages must sum to 100%."
                            : fileError
                              ? fileError
                              : null}
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      </main>
      <footer className="relative mt-16 border-t border-border/60 bg-white/40 py-5 backdrop-blur-sm">
        <p className="text-center text-xs text-muted-foreground">
          Question Paper Generator · For institutional use
        </p>
      </footer>
    </div>
  );
}

function Header({ healthOk, health }: { healthOk: boolean; health: HealthResponse | null }) {
  return (
    <header className="sticky top-0 z-30 border-b border-white/60 bg-white/75 shadow-[0_1px_0_0_oklch(0.929_0.013_255.508),0_4px_24px_-12px_oklch(0.32_0.07_257/0.08)] backdrop-blur-xl">
      <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-primary/25 to-transparent" />
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3.5">
          <div className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-[oklch(0.42_0.09_255)] text-primary-foreground shadow-[0_2px_8px_-2px_oklch(0.32_0.07_257/0.4)]">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M6 4h8l4 4v12H6z" /><path d="M14 4v4h4" /><path d="M8 13h8" /><path d="M8 17h6" /></svg>
          </div>
          <div>
            <h1 className="text-base font-semibold tracking-tight text-foreground sm:text-lg">
              Question Paper Generator
            </h1>
            <p className="text-xs text-muted-foreground sm:text-[13px]">
              AI-assisted examination paper creation
            </p>
          </div>
        </div>

        <nav className="hidden md:flex items-center gap-6 text-sm font-medium">
          <Link
            to="/"
            className="text-muted-foreground hover:text-foreground transition-colors [&.active]:text-primary [&.active]:font-semibold"
          >
            Home
          </Link>
          <Link
            to="/dashboard"
            className="text-muted-foreground hover:text-foreground transition-colors [&.active]:text-primary [&.active]:font-semibold"
          >
            Studio
          </Link>
          <Link
            to="/history"
            className="text-muted-foreground hover:text-foreground transition-colors [&.active]:text-primary [&.active]:font-semibold"
          >
            History
          </Link>
        </nav>

        <div className="flex items-center gap-3">
          {healthOk && health && (
            <span className="hidden text-[11px] text-muted-foreground sm:inline">
              {health.model.split("-").slice(0, 2).join("-")}
            </span>
          )}
          <div
            className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium shadow-sm ${healthOk
                ? "border-emerald-200/80 bg-emerald-50/90 text-emerald-800"
                : "border-red-200/80 bg-red-50/90 text-red-800"
              }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${healthOk ? "bg-emerald-500" : "bg-red-500"}`}
              aria-hidden
            />
            {healthOk ? "System online" : "System offline"}
          </div>
        </div>
      </div>
    </header>
  );
}

function BackgroundFX() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10">
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(165deg, oklch(0.97 0.012 240) 0%, oklch(0.955 0.018 235) 35%, oklch(0.975 0.008 250) 65%, oklch(0.988 0.006 255) 100%)",
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.55]"
        style={{
          backgroundImage:
            "radial-gradient(ellipse 90% 60% at 10% -10%, oklch(0.88 0.04 240 / 0.35), transparent 55%), radial-gradient(ellipse 70% 50% at 95% 20%, oklch(0.9 0.035 230 / 0.25), transparent 50%), radial-gradient(ellipse 60% 40% at 50% 100%, oklch(0.92 0.025 250 / 0.2), transparent 45%)",
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.4]"
        style={{
          backgroundImage:
            "linear-gradient(oklch(0.32 0.07 257 / 0.04) 1px, transparent 1px), linear-gradient(90deg, oklch(0.32 0.07 257 / 0.04) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "linear-gradient(to bottom, black 0%, transparent 85%)",
          WebkitMaskImage: "linear-gradient(to bottom, black 0%, transparent 85%)",
        }}
      />
    </div>
  );
}

function Card({
  title,
  description,
  step,
  children,
  className = "",
}: {
  title: string;
  description?: string;
  step?: number;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`scroll-reveal relative overflow-hidden rounded-xl border border-white/80 bg-white/85 p-6 shadow-[0_1px_2px_oklch(0.32_0.07_257/0.04),0_8px_32px_-12px_oklch(0.32_0.07_257/0.1)] backdrop-blur-sm sm:p-7 transition-all duration-700 ease-out hover:-translate-y-1 hover:shadow-[0_4px_12px_oklch(0.32_0.07_257/0.05),0_16px_48px_-10px_oklch(0.32_0.07_257/0.15)] hover:border-primary/20 hover:bg-white/90 ${className}`}
    >
      <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-primary/20 via-primary/50 to-primary/20" />
      <header className="relative mb-5 flex items-start gap-3">
        {step != null && (
          <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-primary/10 text-[11px] font-bold text-primary">
            {step}
          </span>
        )}
        <div className="min-w-0 flex-1">
          <h2 className="text-[15px] font-semibold text-foreground">{title}</h2>
          {description && (
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{description}</p>
          )}
        </div>
      </header>
      <div className="relative">{children}</div>
    </section>
  );
}

function Field({
  label,
  required,
  children,
  hint,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
        {required && <span className="ml-1 text-red-600">*</span>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted-foreground">{hint}</span>}
    </label>
  );
}

const inputCls =
  "w-full rounded-lg border border-input/80 bg-white/90 px-3.5 py-2.5 text-sm text-foreground shadow-[inset_0_1px_2px_oklch(0.32_0.07_257/0.04)] transition-colors placeholder:text-muted-foreground/50 hover:border-primary/30 focus:border-primary/50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary/10";

function fileExt(name: string): string {
  return (name.split(".").pop() || "").toLowerCase();
}

function FileTypeIcon({ ext }: { ext: string }) {
  const colors: Record<string, string> = {
    pdf: "bg-red-50 text-red-700 border-red-100",
    docx: "bg-blue-50 text-blue-700 border-blue-100",
    txt: "bg-slate-100 text-slate-700 border-slate-200",
  };
  const cls = colors[ext] ?? "bg-muted text-muted-foreground border-border";
  return (
    <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border text-[10px] font-bold uppercase ${cls}`}>
      {ext.slice(0, 4) || "file"}
    </span>
  );
}

function UploadCard({
  files,
  fileError,
  maxMb,
  onAdd,
  onRemove,
  fileInputRef,
  googleSessionId,
  googleSelections,
  setGoogleSelections,
  googleError,
  setGoogleError,
  onConnectGoogle,
  onDisconnectGoogle,
}: {
  files: File[];
  fileError: string | null;
  maxMb: number;
  onAdd: (f: FileList | File[]) => void;
  onRemove: (i: number) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  googleSessionId: string | null;
  googleSelections: SelectedGoogleItem[];
  setGoogleSelections: React.Dispatch<React.SetStateAction<SelectedGoogleItem[]>>;
  googleError: string | null;
  setGoogleError: (err: string | null) => void;
  onConnectGoogle: () => void;
  onDisconnectGoogle: () => void;
}) {
  const [drag, setDrag] = useState(false);
  const [tab, setTab] = useState<"local" | "drive" | "classroom">("local");

  return (
    <Card
      step={1}
      title="Syllabus & Course Documents Source"
      description="Provide the reference materials for generating the question paper. You can upload local files or select documents directly from Google Drive and Google Classroom."
      className="border-primary/10 bg-gradient-to-br from-white/95 to-[oklch(0.97_0.015_240/0.6)]"
    >
      {/* Source Tab Selector */}
      <div className="mb-5 flex border-b border-border/40 pb-1.5 overflow-x-auto gap-2">
        <button
          type="button"
          onClick={() => setTab("local")}
          className={`flex items-center gap-2 border-b-2 pb-2 px-3 text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer ${tab === "local"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.2">
            <rect width="20" height="14" x="2" y="3" rx="2" /><line x1="8" x2="16" y1="21" y2="21" /><line x1="12" x2="12" y1="17" y2="21" />
          </svg>
          Local Files
        </button>
        <button
          type="button"
          onClick={() => setTab("drive")}
          className={`flex items-center gap-2 border-b-2 pb-2 px-3 text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer ${tab === "drive"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M22 19L17 5H7L2 19H22Z" /><path d="M12 5V19" />
          </svg>
          Google Drive
        </button>
        <button
          type="button"
          onClick={() => setTab("classroom")}
          className={`flex items-center gap-2 border-b-2 pb-2 px-3 text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer ${tab === "classroom"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z" /><path d="M6 6h10" /><path d="M6 10h10" />
          </svg>
          Classroom
        </button>
      </div>

      {/* Google Session Connection Status bar */}
      {tab !== "local" && googleSessionId && (
        <div className="mb-4 flex items-center justify-between rounded-lg border border-sky-100 bg-sky-50/50 px-3 py-2 text-xs">
          <div className="flex items-center gap-2 text-sky-800 font-medium">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Connected to Google Workspace
          </div>
          <button
            type="button"
            onClick={onDisconnectGoogle}
            className="rounded bg-white border border-red-200 px-2.5 py-1 font-semibold text-red-700 hover:bg-red-50 hover:border-red-300 transition-colors"
          >
            Disconnect Account
          </button>
        </div>
      )}

      {/* Browser sections content */}
      <div className="relative">
        {tab === "local" && (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              if (e.dataTransfer.files) onAdd(e.dataTransfer.files);
            }}
            className={`relative overflow-hidden rounded-xl border-2 border-dashed transition-all duration-200 ${drag
                ? "border-primary bg-primary/[0.06] shadow-[inset_0_0_0_1px_oklch(0.32_0.07_257/0.15)]"
                : "border-[oklch(0.85_0.03_240)] bg-[oklch(0.975_0.012_245/0.5)] hover:border-primary/35 hover:bg-[oklch(0.97_0.015_240/0.7)]"
              }`}
          >
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 opacity-[0.35]"
              style={{
                backgroundImage:
                  "radial-gradient(circle at 1px 1px, oklch(0.32 0.07 257 / 0.06) 1px, transparent 0)",
                backgroundSize: "20px 20px",
              }}
            />
            <div className="relative flex flex-col items-center px-6 py-10 text-center sm:flex-row sm:items-center sm:gap-8 sm:text-left">
              <div className="mb-5 flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl border border-primary/15 bg-white shadow-[0_4px_16px_-6px_oklch(0.32_0.07_257/0.15)] sm:mb-0">
                <svg viewBox="0 0 24 24" className="h-7 w-7 text-primary" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M12 16V4" /><path d="m7 10 5-5 5 5" /><path d="M4 20h16" />
                </svg>
              </div>
              <div className="flex-1">
                <p className="text-base font-semibold text-foreground">
                  {drag ? "Drop files to upload" : "Drag & drop your syllabus here"}
                </p>
                <p className="mt-1.5 text-sm text-muted-foreground">
                  or browse from your computer · up to {maxMb} MB per file
                </p>
                <div className="mt-4 flex flex-wrap items-center justify-center gap-2 sm:justify-start">
                  {["PDF", "TXT", "DOCX", "XLSX"].map((fmt) => (
                    <span
                      key={fmt}
                      className="rounded-md border border-primary/10 bg-white/80 px-2.5 py-1 text-[11px] font-semibold tracking-wide text-primary/80"
                    >
                      {fmt}
                    </span>
                  ))}
                </div>
              </div>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="mt-5 shrink-0 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition hover:bg-primary/90 sm:mt-0 cursor-pointer"
              >
                Browse files
              </button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.txt,.docx,.xlsx"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) onAdd(e.target.files);
                  e.target.value = "";
                }}
              />
            </div>
          </div>
        )}

        {tab !== "local" && !googleSessionId && (
          <div className="flex flex-col items-center justify-center py-10 text-center rounded-xl border border-dashed border-[oklch(0.85_0.03_240)] bg-[oklch(0.975_0.012_245/0.5)]">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-sky-100 bg-sky-50 text-sky-600 shadow-sm">
              <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3Z" />
              </svg>
            </div>
            <h3 className="text-sm font-bold text-foreground">Import from Google Workspace</h3>
            <p className="mt-1.5 max-w-sm px-4 text-xs text-muted-foreground leading-relaxed">
              Connect your account to index syllabus documents, notes, and worksheets directly from your Google Drive folders and Google Classroom classes.
            </p>
            <button
              type="button"
              onClick={onConnectGoogle}
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-sky-600 px-5 py-2.5 text-xs font-semibold text-white shadow-sm transition hover:bg-sky-500 cursor-pointer"
            >
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12.24 10.285V13.4h6.887C18.2 15.614 15.645 18 12.24 18c-3.86 0-7-3.14-7-7s3.14-7 7-7c1.7 0 3.3.6 4.5 1.7l2.4-2.4C17.3 1.7 14.9 1 12.24 1 6.58 1 2 5.58 2 11.24s4.58 10.24 10.24 10.24c5.79 0 10.24-4.1 10.24-10.24 0-.6-.05-1.2-.15-1.75H12.24z" />
              </svg>
              Connect Google Account
            </button>
            {googleError && (
              <p className="mt-3 text-xs font-medium text-red-600">
                Connection error: {googleError}
              </p>
            )}
          </div>
        )}

        {tab === "drive" && googleSessionId && (
          <GoogleDriveBrowser
            sessionId={googleSessionId}
            selections={googleSelections}
            setSelections={setGoogleSelections}
            setError={setGoogleError}
          />
        )}

        {tab === "classroom" && googleSessionId && (
          <GoogleClassroomBrowser
            sessionId={googleSessionId}
            selections={googleSelections}
            setSelections={setGoogleSelections}
            setError={setGoogleError}
          />
        )}
      </div>

      {/* Unified Sources Queue */}
      {(files.length > 0 || googleSelections.length > 0) && (
        <div className="mt-6 border-t border-border/60 pt-5">
          <p className="mb-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
            Selected Documents ({files.length + googleSelections.length} ready)
          </p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {files.map((f, i) => {
              const ext = fileExt(f.name);
              const sizeMb = f.size / 1024 / 1024;
              return (
                <li
                  key={`local-${f.name}-${i}`}
                  className="flex items-center gap-3 rounded-lg border border-border/70 bg-white/90 px-3 py-2.5 shadow-sm"
                >
                  <FileTypeIcon ext={ext} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-foreground" title={f.name}>{f.name}</p>
                    <p className="text-[10px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                      <span>{sizeMb >= 1 ? `${sizeMb.toFixed(2)} MB` : `${(f.size / 1024).toFixed(1)} KB`}</span>
                      <span className="h-1 w-1 rounded-full bg-muted-foreground/30" />
                      <span className="rounded bg-slate-100 px-1 py-0.2 text-[9px] font-semibold text-slate-600">Local Upload</span>
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onRemove(i)}
                    className="rounded px-2 py-1 text-xs font-semibold text-muted-foreground transition hover:bg-red-50 hover:text-red-700 cursor-pointer"
                  >
                    Remove
                  </button>
                </li>
              );
            })}

            {googleSelections.map((item, idx) => {
              const ext = item.type === "folder" ? "folder" : fileExt(item.name);
              return (
                <li
                  key={`google-${item.id}-${idx}`}
                  className="flex items-center gap-3 rounded-lg border border-border/70 bg-white/90 px-3 py-2.5 shadow-sm"
                >
                  {item.type === "folder" ? (
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-amber-100 bg-amber-50 text-[10px] font-bold text-amber-700 uppercase">
                      fldr
                    </span>
                  ) : (
                    <FileTypeIcon ext={ext} />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-foreground" title={item.name}>{item.name}</p>
                    <p className="text-[10px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                      <span className="rounded bg-sky-100 px-1 py-0.2 text-[9px] font-semibold text-sky-700">
                        {item.source === "drive" ? "Google Drive" : "Classroom"}
                      </span>
                      <span className="h-1 w-1 rounded-full bg-muted-foreground/30" />
                      <span className="capitalize text-[10px]">{item.type}</span>
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setGoogleSelections((prev) => prev.filter((x) => x.id !== item.id));
                    }}
                    className="rounded px-2 py-1 text-xs font-semibold text-muted-foreground transition hover:bg-red-50 hover:text-red-700 cursor-pointer"
                  >
                    Remove
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {fileError && (
        <p className="mt-4 rounded-lg border border-red-200 bg-red-50/90 px-4 py-2.5 text-sm text-red-800">
          {fileError}
        </p>
      )}
    </Card>
  );
}

function GoogleDriveBrowser({
  sessionId,
  selections,
  setSelections,
  setError,
}: {
  sessionId: string;
  selections: SelectedGoogleItem[];
  setSelections: React.Dispatch<React.SetStateAction<SelectedGoogleItem[]>>;
  setError: (err: string | null) => void;
}) {
  const [breadcrumbs, setBreadcrumbs] = useState<{ id: string; name: string }[]>([
    { id: "root", name: "Google Drive" },
  ]);
  const [items, setItems] = useState<GoogleItem[]>([]);
  const [loading, setLoading] = useState(false);

  const currentFolderId = breadcrumbs[breadcrumbs.length - 1].id;

  const loadFolder = useCallback(async (folderId: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getGoogleDriveItems(folderId, sessionId);
      setItems(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [sessionId, setError]);

  useEffect(() => {
    loadFolder(currentFolderId);
  }, [currentFolderId, loadFolder]);

  const onNavigate = (id: string, name: string) => {
    setBreadcrumbs((prev) => [...prev, { id, name }]);
  };

  const onBreadcrumbClick = (idx: number) => {
    setBreadcrumbs((prev) => prev.slice(0, idx + 1));
  };

  const toggleSelect = (item: GoogleItem) => {
    const isSel = selections.some((x) => x.id === item.id);
    if (isSel) {
      setSelections((prev) => prev.filter((x) => x.id !== item.id));
    } else {
      setSelections((prev) => [
        ...prev,
        {
          id: item.id,
          name: item.name,
          type: item.kind === "folder" ? "folder" : "file",
          source: "drive",
          mime_type: item.mime_type || undefined,
          supported: item.supported || undefined,
        },
      ]);
    }
  };

  return (
    <div className="space-y-4">
      {/* Breadcrumbs */}
      <nav className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground font-semibold bg-white/50 px-3 py-2 rounded-lg border border-border/40">
        {breadcrumbs.map((crumb, idx) => {
          const isLast = idx === breadcrumbs.length - 1;
          return (
            <div key={crumb.id} className="flex items-center gap-1">
              {idx > 0 && <span className="text-[10px] opacity-40">/</span>}
              <button
                type="button"
                onClick={() => onBreadcrumbClick(idx)}
                disabled={isLast}
                className={`transition-colors hover:text-foreground cursor-pointer ${isLast ? "text-primary font-bold" : ""
                  }`}
              >
                {crumb.name}
              </button>
            </div>
          );
        })}
      </nav>

      {/* Items list */}
      <div className="min-h-[220px] rounded-lg border border-border/60 bg-white/70 max-h-[300px] overflow-y-auto shadow-inner">
        {loading ? (
          <div className="flex h-[200px] flex-col items-center justify-center text-muted-foreground">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
            <p className="mt-2 text-xs">Loading items…</p>
          </div>
        ) : items.length === 0 ? (
          <div className="flex h-[200px] flex-col items-center justify-center text-xs text-muted-foreground">
            No files or folders found here.
          </div>
        ) : (
          <ul className="divide-y divide-border/40">
            {items.map((item) => {
              const isFolder = item.kind === "folder";
              const isSelected = selections.some((x) => x.id === item.id);
              const isDisabled = !isFolder && !item.supported;

              return (
                <li
                  key={item.id}
                  className={`flex items-center justify-between gap-4 px-4 py-2 hover:bg-slate-50 transition-colors ${isDisabled ? "opacity-40" : ""
                    }`}
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    {/* Icon */}
                    {isFolder ? (
                      <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0 text-amber-500" fill="currentColor">
                        <path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z" />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0 text-sky-500" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                      </svg>
                    )}

                    {/* Name */}
                    {isFolder ? (
                      <button
                        type="button"
                        onClick={() => onNavigate(item.id, item.name)}
                        className="truncate text-left text-sm font-semibold text-foreground hover:text-primary transition-colors cursor-pointer"
                      >
                        {item.name}
                      </button>
                    ) : (
                      <span className="truncate text-sm font-medium text-foreground">{item.name}</span>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex shrink-0 items-center gap-2.5">
                    {isFolder ? (
                      <button
                        type="button"
                        onClick={() => toggleSelect(item)}
                        className={`rounded px-2.5 py-1 text-xs font-semibold transition border cursor-pointer ${isSelected
                            ? "bg-amber-100 text-amber-800 border-amber-300"
                            : "bg-white text-muted-foreground border-border hover:bg-amber-50 hover:text-amber-800 hover:border-amber-300"
                          }`}
                      >
                        {isSelected ? "Folder Selected" : "Select Folder"}
                      </button>
                    ) : isDisabled ? (
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-[9px] font-semibold text-slate-500 border border-slate-200">
                        Unsupported
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => toggleSelect(item)}
                        className={`rounded px-2.5 py-1 text-xs font-semibold transition border cursor-pointer ${isSelected
                            ? "bg-primary text-primary-foreground border-primary shadow-sm"
                            : "bg-white text-foreground border-border hover:bg-primary/[0.04] hover:border-primary/20"
                          }`}
                      >
                        {isSelected ? "Selected" : "Select"}
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

function GoogleClassroomBrowser({
  sessionId,
  selections,
  setSelections,
  setError,
}: {
  sessionId: string;
  selections: SelectedGoogleItem[];
  setSelections: React.Dispatch<React.SetStateAction<SelectedGoogleItem[]>>;
  setError: (err: string | null) => void;
}) {
  const [courses, setCourses] = useState<GoogleItem[]>([]);
  const [materials, setMaterials] = useState<GoogleItem[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<GoogleItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<"courses" | "materials">("courses");

  const loadCourses = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getGoogleClassroomCourses(sessionId);
      setCourses(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [sessionId, setError]);

  const loadMaterials = useCallback(async (courseId: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getGoogleClassroomCourseMaterials(courseId, sessionId);
      setMaterials(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [sessionId, setError]);

  useEffect(() => {
    if (view === "courses") {
      loadCourses();
    }
  }, [view, loadCourses]);

  const onCourseClick = (course: GoogleItem) => {
    setSelectedCourse(course);
    setView("materials");
    loadMaterials(course.id);
  };

  const onBack = () => {
    setView("courses");
    setSelectedCourse(null);
    setMaterials([]);
  };

  const toggleSelect = (item: GoogleItem) => {
    const isSel = selections.some((x) => x.id === item.id);
    if (isSel) {
      setSelections((prev) => prev.filter((x) => x.id !== item.id));
    } else {
      setSelections((prev) => [
        ...prev,
        {
          id: item.id,
          name: item.name,
          type: "file",
          source: "classroom",
          supported: true,
        },
      ]);
    }
  };

  return (
    <div className="space-y-4">
      {/* View Header */}
      {view === "materials" && selectedCourse && (
        <div className="flex items-center gap-2 bg-white/50 px-3 py-2 rounded-lg border border-border/40">
          <button
            type="button"
            onClick={onBack}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground font-semibold cursor-pointer"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="m15 18-6-6 6-6" />
            </svg>
            Back to Classes
          </button>
          <span className="text-xs text-muted-foreground opacity-40">/</span>
          <span className="text-xs font-bold text-primary truncate">{selectedCourse.name}</span>
        </div>
      )}

      {/* Classroom Container */}
      <div className="min-h-[220px] rounded-lg border border-border/60 bg-white/70 max-h-[300px] overflow-y-auto shadow-inner">
        {loading ? (
          <div className="flex h-[200px] flex-col items-center justify-center text-muted-foreground">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
            <p className="mt-2 text-xs">Loading classroom data…</p>
          </div>
        ) : view === "courses" ? (
          courses.length === 0 ? (
            <div className="flex h-[200px] flex-col items-center justify-center text-xs text-muted-foreground">
              No active Classroom classes found.
            </div>
          ) : (
            <ul className="divide-y divide-border/40">
              {courses.map((course) => (
                <li
                  key={course.id}
                  className="flex items-center justify-between gap-4 px-4 py-2.5 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0 text-emerald-600" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
                      <path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5" />
                    </svg>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-foreground">{course.name}</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => onCourseClick(course)}
                    className="shrink-0 rounded bg-white border border-border px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-slate-50 cursor-pointer transition-colors shadow-sm"
                  >
                    View Materials
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : materials.length === 0 ? (
          <div className="flex h-[200px] flex-col items-center justify-center text-xs text-muted-foreground">
            No materials with attached Drive files found.
          </div>
        ) : (
          <ul className="divide-y divide-border/40">
            {materials.map((material) => {
              const isSelected = selections.some((x) => x.id === material.id);
              return (
                <li
                  key={material.id}
                  className="flex items-center justify-between gap-4 px-4 py-2 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0 text-sky-500" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    <span className="truncate text-sm font-medium text-foreground">{material.name}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => toggleSelect(material)}
                    className={`rounded px-2.5 py-1 text-xs font-semibold transition border cursor-pointer ${isSelected
                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                        : "bg-white text-foreground border-border hover:bg-primary/[0.04] hover:border-primary/20"
                      }`}
                  >
                    {isSelected ? "Selected" : "Select"}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

function ExamDetailsCard({
  form,
  update,
}: {
  form: FormState;
  update: <K extends keyof FormState>(k: K, v: FormState[K]) => void;
}) {
  return (
    <Card step={2} title="Examination Details">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Institution Name" required>
          <input
            className={inputCls}
            placeholder="e.g. Example University"
            value={form.institution_name}
            onChange={(e) => update("institution_name", e.target.value)}
          />
        </Field>
        <Field label="Course Name" required>
          <input
            className={inputCls}
            placeholder="e.g. Computer Networks"
            value={form.course_name}
            onChange={(e) => update("course_name", e.target.value)}
          />
        </Field>
        <Field label="Course Code" required>
          <input
            className={inputCls}
            placeholder="e.g. CSE401"
            value={form.course_code}
            onChange={(e) => update("course_code", e.target.value)}
          />
        </Field>
        <Field label="Semester" required hint="e.g. I, II, III, IV, V">
          <input
            className={inputCls}
            placeholder="e.g. V"
            value={form.semester}
            onChange={(e) => update("semester", e.target.value)}
          />
        </Field>
        <Field label="Exam Type" required>
          <select
            className={inputCls}
            value={form.exam_type}
            onChange={(e) => update("exam_type", e.target.value)}
          >
            {EXAM_TYPES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </Field>
        <Field label="Duration" required>
          <select
            className={inputCls}
            value={form.duration}
            onChange={(e) => update("duration", e.target.value)}
          >
            {DURATIONS.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </Field>
        <div className="sm:col-span-2">
          <Field label="Exam Date">
            <input
              className={inputCls}
              placeholder="e.g. June 2026"
              value={form.exam_date}
              onChange={(e) => update("exam_date", e.target.value)}
            />
          </Field>
        </div>
      </div>
    </Card>
  );
}

function NumField({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (n: number) => void;
}) {
  return (
    <Field label={label} required>
      <input
        type="number"
        className={inputCls}
        min={min}
        max={max}
        step={step}
        value={Number.isFinite(value) ? value : 0}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </Field>
  );
}

function QuestionsCard({
  form,
  update,
  computed,
  ok,
}: {
  form: FormState;
  update: <K extends keyof FormState>(k: K, v: FormState[K]) => void;
  computed: number;
  ok: boolean;
}) {
  return (
    <Card step={3} title="Question Paper Structure">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <NumField
          label="Total Marks"
          value={form.total_marks}
          min={10}
          max={200}
          step={5}
          onChange={(n) => update("total_marks", n)}
        />
        <NumField
          label="2 Mark Questions"
          value={form.two_mark_questions}
          min={0}
          max={20}
          onChange={(n) => update("two_mark_questions", n)}
        />
        <NumField
          label="5 Mark Questions"
          value={form.five_mark_questions}
          min={0}
          max={20}
          onChange={(n) => update("five_mark_questions", n)}
        />
        <NumField
          label="10 Mark Questions"
          value={form.ten_mark_questions}
          min={0}
          max={10}
          onChange={(n) => update("ten_mark_questions", n)}
        />
        <NumField
          label="15 Mark Questions"
          value={form.fifteen_mark_questions}
          min={0}
          max={10}
          onChange={(n) => update("fifteen_mark_questions", n)}
        />
      </div>
      <div
        className={`mt-4 flex items-center justify-between rounded-md border px-4 py-2.5 text-sm ${ok
            ? "border-emerald-200 bg-emerald-50 text-emerald-800"
            : "border-amber-200 bg-amber-50 text-amber-800"
          }`}
      >
        <span className="font-medium">Calculated marks</span>
        <span>
          {computed} / {form.total_marks}
          {!ok && " — must match total"}
        </span>
      </div>
    </Card>
  );
}

function DifficultyCard({
  form,
  update,
  sum,
  ok,
}: {
  form: FormState;
  update: <K extends keyof FormState>(k: K, v: FormState[K]) => void;
  sum: number;
  ok: boolean;
}) {
  const items: { key: keyof FormState; label: string }[] = [
    { key: "easy_percentage", label: "Easy" },
    { key: "medium_percentage", label: "Medium" },
    { key: "hard_percentage", label: "Hard" },
  ];
  return (
    <Card step={4} title="Difficulty Distribution">
      <div className="space-y-5">
        {items.map(({ key, label }) => {
          const value = form[key] as number;
          return (
            <div key={key}>
              <div className="mb-1.5 flex items-center justify-between text-sm">
                <span className="font-medium text-foreground">{label}</span>
                <span className="text-muted-foreground">{value}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={value}
                onChange={(e) => update(key, Number(e.target.value) as never)}
                className="w-full accent-primary cursor-pointer"
              />
              <div className="relative mt-1.5 px-[6px] flex justify-between pointer-events-none">
                {[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map((tick) => (
                  <span
                    key={tick}
                    className="w-1.5 h-1.5 rounded-full bg-slate-300/80 shadow-[inset_0_1px_1px_rgba(0,0,0,0.05)] border border-white/60"
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <div
        className={`mt-4 flex items-center justify-between rounded-md border px-4 py-2.5 text-sm ${ok
            ? "border-emerald-200 bg-emerald-50 text-emerald-800"
            : "border-amber-200 bg-amber-50 text-amber-800"
          }`}
      >
        <span className="font-medium">Total</span>
        <span>
          {sum}%{!ok && " — must equal 100%"}
        </span>
      </div>
    </Card>
  );
}

function ResultsPanel({
  loading,
  result,
  error,
}: {
  loading: boolean;
  result: GenerateResponse | null;
  error: { message: string; errors?: string[] } | null;
}) {
  return (
    <Card step={5} title="Generation Status">
      {loading ? (
        <div className="space-y-5">
          <div className="flex items-center gap-3 rounded-lg bg-primary/[0.06] px-4 py-3">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
            <p className="text-sm font-medium text-foreground">Generating question paper…</p>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            This may take 1–2 minutes. Please keep this tab open while the pipeline runs.
          </p>
          <ol className="space-y-2 border-l-2 border-primary/15 pl-4 text-sm text-muted-foreground">
            <li>Processing documents</li>
            <li>Analyzing syllabus</li>
            <li>Generating questions</li>
            <li>Preparing PDFs</li>
          </ol>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-200 bg-red-50/80 p-4">
          <h3 className="text-sm font-semibold text-red-800">Generation failed</h3>
          <p className="mt-2 text-sm text-red-900/90">{error.message}</p>
          {error.errors && error.errors.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-red-800/80">
              {error.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      ) : result ? (
        <div className="space-y-4">
          <div className="rounded-lg border border-emerald-200 bg-emerald-50/90 px-4 py-3 text-sm text-emerald-900">
            {result.message}
          </div>
          <p className="text-xs text-muted-foreground">
            Completed in {result.elapsed_seconds.toFixed(1)} seconds
          </p>
          <div className="space-y-2.5">
            <DownloadButton
              label="Download Question Paper"
              filename={basename(result.final_pdf_path || "")}
            />
            <DownloadButton
              label="Download Answer Key"
              filename={basename(result.answer_key_pdf_path || "")}
              variant="outline"
            />
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border/80 bg-[oklch(0.975_0.012_245/0.4)] px-4 py-8 text-center">
          <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden><path d="M6 4h8l4 4v12H6z" /><path d="M14 4v4h4" /></svg>
          </div>
          <p className="text-sm font-medium text-foreground">Ready to generate</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Your question paper and answer key will appear here after generation.
          </p>
        </div>
      )}
    </Card>
  );
}

function DownloadButton({
  label,
  filename,
  variant = "primary",
}: {
  label: string;
  filename: string;
  variant?: "primary" | "outline";
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const cls =
    variant === "primary"
      ? "w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition hover:bg-primary/90 disabled:opacity-50"
      : "w-full rounded-lg border border-border/80 bg-white/90 px-4 py-2.5 text-sm font-semibold text-foreground transition hover:border-primary/30 hover:bg-primary/[0.04] disabled:opacity-50";
  return (
    <div>
      <button
        className={cls}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setErr(null);
          try {
            await downloadFile(filename);
          } catch (e) {
            setErr((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Downloading…" : label}
      </button>
      {err && <p className="mt-1 text-xs text-red-700">{err}</p>}
    </div>
  );
}

interface PreviewStudioProps {
  questions: ValidatedQuestion[];
  setQuestions: React.Dispatch<React.SetStateAction<ValidatedQuestion[]>>;
  answerKey: AnswerKeyItem[];
  setAnswerKey: React.Dispatch<React.SetStateAction<AnswerKeyItem[]>>;
  onQuestionEdited: (questionId: string) => void;
}

function PreviewStudio({
  questions,
  setQuestions,
  answerKey,
  setAnswerKey,
  onQuestionEdited,
}: PreviewStudioProps) {
  const [activeTab, setActiveTab] = useState<"questions" | "answers">("questions");

  const sections = [
    { marks: 2, label: "Section A — Short Answer Questions (2 Marks each)" },
    { marks: 5, label: "Section B — Brief Answer Questions (5 Marks each)" },
    { marks: 10, label: "Section C — Long Answer Questions (10 Marks each)" },
    { marks: 15, label: "Section D — Essay / Case Study Questions (15 Marks each)" },
  ];

  return (
    <div className="space-y-6">
      {/* Studio Header Tabs */}
      <div className="flex items-center justify-between border-b border-border bg-white/70 px-4 py-1.5 rounded-xl backdrop-blur-sm">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("questions")}
            className={`px-4 py-2 text-xs font-semibold uppercase tracking-wider border-b-2 transition-all cursor-pointer ${
              activeTab === "questions"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Question Paper Preview
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("answers")}
            className={`px-4 py-2 text-xs font-semibold uppercase tracking-wider border-b-2 transition-all cursor-pointer ${
              activeTab === "answers"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Answer Key Preview
          </button>
        </div>
        <span className="text-xs text-muted-foreground font-medium px-2.5 py-1 rounded-md bg-slate-100/80 border border-slate-200">
          Editable Draft Mode
        </span>
      </div>

      {activeTab === "questions" ? (
        <Card title="Draft Question Paper" description="Review and edit the wording of questions. Content will update in the printed PDF.">
          <div className="space-y-8">
            {sections.map((sec) => {
              const secQs = questions.filter((q) => q.marks === sec.marks);
              if (secQs.length === 0) return null;
              return (
                <div key={sec.marks} className="space-y-4">
                  <div className="border-b pb-2 flex items-center justify-between">
                    <h3 className="text-sm font-bold text-slate-800">{sec.label}</h3>
                    <span className="text-xs font-semibold text-muted-foreground bg-slate-100 px-2 py-0.5 rounded">
                      {secQs.length} question{secQs.length > 1 ? "s" : ""}
                    </span>
                  </div>
                  <div className="space-y-5">
                    {secQs.map((q, idx) => (
                      <div key={q.id} className="relative flex gap-4 p-4 rounded-lg bg-slate-50 border border-slate-100 hover:border-slate-200 transition-colors">
                        <div className="text-sm font-bold text-slate-400 mt-2 shrink-0">
                          Q{idx + 1}.
                        </div>
                        <div className="flex-1 space-y-2">
                          <textarea
                            value={q.question}
                            onChange={(e) => {
                              const val = e.target.value;
                              setQuestions((prev) =>
                                prev.map((item) =>
                                  item.id === q.id ? { ...item, question: val } : item
                                )
                              );
                              // Sync answer key question too
                              setAnswerKey((prev) =>
                                prev.map((item) =>
                                  item.id === q.id ? { ...item, question: val } : item
                                )
                              );
                              onQuestionEdited(q.id);
                            }}
                            rows={3}
                            className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm leading-relaxed text-foreground shadow-sm focus:border-primary/30 focus:outline-none focus:ring-1 focus:ring-primary/20 resize-y"
                            placeholder="Enter question text..."
                          />
                          <div className="flex flex-wrap gap-2 text-[10px]">
                            <span className="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 font-medium text-slate-600 border border-slate-200">
                              Unit: {q.unit}
                            </span>
                            <span className="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 font-medium text-slate-600 border border-slate-200">
                              Topic: {q.topic}
                            </span>
                            <span className="inline-flex items-center rounded bg-sky-50 px-1.5 py-0.5 font-medium text-sky-700 border border-sky-100">
                              Bloom: {q.bloom_level}
                            </span>
                            <span className="inline-flex items-center rounded bg-purple-50 px-1.5 py-0.5 font-medium text-purple-700 border border-purple-100">
                              Difficulty: {q.difficulty}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      ) : (
        <Card title="Draft Answer Key &amp; Scheme" description="Tweak model answers, key scoring points, and marks breakdown for grading.">
          <div className="space-y-6">
            {answerKey.map((a, idx) => (
              <div key={a.id} className="p-5 rounded-xl bg-slate-50 border border-slate-100 space-y-4">
                <div className="flex items-start justify-between border-b pb-2">
                  <h4 className="text-sm font-bold text-slate-800">
                    Question {idx + 1} ({a.marks} Marks)
                  </h4>
                  <span className="text-[11px] text-muted-foreground truncate max-w-xs italic">
                    "{a.question.substring(0, 45)}..."
                  </span>
                </div>

                <div className="space-y-3">
                  {/* Model Answer */}
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      Model Answer
                    </label>
                    <textarea
                      value={a.model_answer}
                      onChange={(e) => {
                        const val = e.target.value;
                        setAnswerKey((prev) =>
                          prev.map((item) =>
                            item.id === a.id ? { ...item, model_answer: val } : item
                          )
                        );
                      }}
                      rows={4}
                      className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm leading-relaxed text-foreground focus:border-primary/30 focus:outline-none focus:ring-1 focus:ring-primary/20"
                      placeholder="Provide the model answer..."
                    />
                  </div>

                  {/* Key Points */}
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      Key Grading Points (one per line)
                    </label>
                    <textarea
                      value={a.key_points.join("\n")}
                      onChange={(e) => {
                        const lines = e.target.value.split("\n");
                        setAnswerKey((prev) =>
                          prev.map((item) =>
                            item.id === a.id ? { ...item, key_points: lines } : item
                          )
                        );
                      }}
                      rows={3}
                      className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm leading-relaxed text-foreground focus:border-primary/30 focus:outline-none focus:ring-1 focus:ring-primary/20"
                      placeholder="Add key grading points (one per line)..."
                    />
                  </div>

                  {/* Marks Breakdown */}
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      Marks Breakdown Explanation
                    </label>
                    <input
                      type="text"
                      value={a.marks_breakdown}
                      onChange={(e) => {
                        const val = e.target.value;
                        setAnswerKey((prev) =>
                          prev.map((item) =>
                            item.id === a.id ? { ...item, marks_breakdown: val } : item
                          )
                        );
                      }}
                      className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm text-foreground focus:border-primary/30 focus:outline-none focus:ring-1 focus:ring-primary/20"
                      placeholder="e.g. 2 marks for definition, 3 marks for diagram"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
