"use client";

import React, { useEffect, useState, useRef, useCallback, Suspense } from "react";
import { motion, Variants } from "framer-motion";
import { 
  getKnowledgeList, 
  uploadKnowledge, 
  startGoogleOauth, 
  getGoogleDriveItems,
  getGoogleClassroomCourses,
  getGoogleClassroomCourseMaterials,
  type CatalogNode,
  type GoogleItem
} from "@/lib/api";
import Link from "next/link";
import { toast } from "sonner";
import { useSearchParams } from "next/navigation";

export interface SelectedGoogleItem {
  id: string;
  name: string;
  type: string;
  source: "drive" | "classroom";
  mime_type?: string;
  supported?: boolean;
}

function fileExt(name: string): string {
  return (name.split(".").pop() || "").toLowerCase();
}

function FileTypeIcon({ ext }: { ext: string }) {
  const colors: Record<string, string> = {
    pdf: "bg-destructive/10 text-destructive border-destructive/20",
    docx: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    txt: "bg-muted text-muted-foreground border-border",
  };
  const cls = colors[ext] ?? "bg-muted text-muted-foreground border-border";
  return (
    <span
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border text-[10px] font-bold uppercase ${cls}`}
    >
      {ext.slice(0, 4) || "file"}
    </span>
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

  const loadFolder = useCallback(
    async (folderId: string) => {
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
    },
    [sessionId, setError],
  );

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
      <nav className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground font-semibold bg-background/50 px-3 py-2 rounded-lg border border-border/40">
        {breadcrumbs.map((crumb, idx) => {
          const isLast = idx === breadcrumbs.length - 1;
          return (
            <div key={crumb.id} className="flex items-center gap-1">
              {idx > 0 && <span className="text-[10px] opacity-40">/</span>}
              <button
                type="button"
                onClick={() => onBreadcrumbClick(idx)}
                disabled={isLast}
                className={`transition-colors hover:text-foreground cursor-pointer ${
                  isLast ? "text-primary font-bold" : ""
                }`}
              >
                {crumb.name}
              </button>
            </div>
          );
        })}
      </nav>

      {/* Items list */}
      <div className="min-h-[220px] rounded-lg border border-border/60 bg-background/70 max-h-[300px] overflow-y-auto shadow-inner">
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
                  className={`flex items-center justify-between gap-4 px-4 py-2 hover:bg-muted transition-colors ${
                    isDisabled ? "opacity-40" : ""
                  }`}
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    {/* Icon */}
                    {isFolder ? (
                      <svg
                        viewBox="0 0 24 24"
                        className="h-5 w-5 shrink-0 text-amber-500"
                        fill="currentColor"
                      >
                        <path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z" />
                      </svg>
                    ) : (
                      <svg
                        viewBox="0 0 24 24"
                        className="h-5 w-5 shrink-0 text-sky-500"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
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
                      <span className="truncate text-sm font-medium text-foreground">
                        {item.name}
                      </span>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex shrink-0 items-center gap-2.5">
                    {isFolder ? (
                      <button
                        type="button"
                        onClick={() => toggleSelect(item)}
                        className={`rounded px-2.5 py-1 text-xs font-semibold transition border cursor-pointer ${
                          isSelected
                            ? "bg-amber-500/20 text-amber-500 border-amber-500/30"
                            : "bg-background text-muted-foreground border-border hover:bg-amber-500/10 hover:text-amber-500 hover:border-amber-500/30"
                        }`}
                      >
                        {isSelected ? "Folder Selected" : "Select Folder"}
                      </button>
                    ) : isDisabled ? (
                      <span className="rounded bg-muted px-2 py-0.5 text-[9px] font-semibold text-muted-foreground border border-border">
                        Unsupported
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => toggleSelect(item)}
                        className={`rounded px-2.5 py-1 text-xs font-semibold transition border cursor-pointer ${
                          isSelected
                            ? "bg-primary text-primary-foreground border-primary shadow-sm"
                            : "bg-background text-foreground border-border hover:bg-primary/[0.04] hover:border-primary/20"
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

  const loadMaterials = useCallback(
    async (courseId: string) => {
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
    },
    [sessionId, setError],
  );

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
        <div className="flex items-center gap-2 bg-background/50 px-3 py-2 rounded-lg border border-border/40">
          <button
            type="button"
            onClick={onBack}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground font-semibold cursor-pointer"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m15 18-6-6 6-6" />
            </svg>
            Back to Classes
          </button>
          <span className="text-xs text-muted-foreground opacity-40">/</span>
          <span className="text-xs font-bold text-primary truncate">{selectedCourse.name}</span>
        </div>
      )}

      {/* Classroom Container */}
      <div className="min-h-[220px] rounded-lg border border-border/60 bg-background/70 max-h-[300px] overflow-y-auto shadow-inner">
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
                  className="flex items-center justify-between gap-4 px-4 py-2.5 hover:bg-muted transition-colors"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <svg
                      viewBox="0 0 24 24"
                      className="h-5 w-5 shrink-0 text-emerald-600"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
                      <path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5" />
                    </svg>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-foreground">
                        {course.name}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => onCourseClick(course)}
                    className="shrink-0 rounded bg-background border border-border px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-muted cursor-pointer transition-colors shadow-sm"
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
                  className="flex items-center justify-between gap-4 px-4 py-2 hover:bg-muted transition-colors"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <svg
                      viewBox="0 0 24 24"
                      className="h-5 w-5 shrink-0 text-sky-500"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    <span className="truncate text-sm font-medium text-foreground">
                      {material.name}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => toggleSelect(material)}
                    className={`rounded px-2.5 py-1 text-xs font-semibold transition border cursor-pointer ${
                      isSelected
                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                        : "bg-background text-foreground border-border hover:bg-primary/[0.04] hover:border-primary/20"
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


function KnowledgeBaseManagerInner() {
  const searchParams = useSearchParams();
  const [catalog, setCatalog] = useState<Record<string, CatalogNode>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newSubject, setNewSubject] = useState("");
  const [newChapter, setNewChapter] = useState("");
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  
  // Google state
  const [googleSessionId, setGoogleSessionId] = useState<string | null>(null);
  const [googleSelections, setGoogleSelections] = useState<SelectedGoogleItem[]>([]);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [tab, setTab] = useState<"local" | "drive" | "classroom">("local");

  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const gc = searchParams.get("google_connected");
    if (gc) {
      setGoogleSessionId(gc);
      setTab("drive");
    }
  }, [searchParams]);

  const loadCatalog = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getKnowledgeList();
      if (data.success) {
        setCatalog(data.catalog);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCatalog();
  }, []);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setUploadFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setUploadFiles(Array.from(e.target.files));
    }
  };

  const onConnectGoogle = async () => {
    try {
      const auth = await startGoogleOauth();
      window.location.href = auth.authorization_url;
    } catch (e) {
      toast.error("Google connection error: " + (e as Error).message);
    }
  };

  const onUpload = async () => {
    if (!newSubject.trim() || !newChapter.trim()) {
      toast.error("Please enter a subject and chapter.");
      return;
    }
    if (uploadFiles.length === 0 && googleSelections.length === 0) {
      toast.error("Please select at least one file to upload (Local or Google).");
      return;
    }
    setUploading(true);
    try {
      const googleFileIds = googleSelections.filter((s) => s.type === "file").map((s) => s.id);
      const googleFolderIds = googleSelections.filter((s) => s.type === "folder").map((s) => s.id);
      
      await uploadKnowledge(
        newSubject, 
        newChapter, 
        uploadFiles, 
        googleSessionId, 
        googleFileIds, 
        googleFolderIds
      );
      setNewSubject("");
      setNewChapter("");
      setUploadFiles([]);
      setGoogleSelections([]);
      toast.success("Documents successfully added to the Knowledge Base!");
      await loadCatalog();
    } catch (e) {
      toast.error("Error uploading: " + (e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const removeLocalFile = (index: number) => {
    setUploadFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const removeGoogleFile = (id: string) => {
    setGoogleSelections((prev) => prev.filter((x) => x.id !== id));
  };

  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1 },
    },
  };

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } },
  };

  const totalEmbeddedChunks = Object.values(catalog).reduce((acc, subj) => {
    if (subj.children) {
      return acc + Object.values(subj.children).reduce((cAcc, chap) => cAcc + (chap.chunk_count || 0), 0);
    }
    return acc;
  }, 0);

  return (
    <div className="relative min-h-screen text-foreground">
      <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 bg-background">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/5 via-background to-background"></div>
      </div>

      <main className="relative mx-auto w-full max-w-[1440px] px-4 pt-2 pb-8 sm:px-6 lg:px-8">
        <div className="mb-10 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5 }}>
            <p className="text-sm font-medium text-primary/80 tracking-wide uppercase">RAG Engine</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight text-secondary sm:text-4xl">
              Knowledge Base Manager
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Manage your vector database. Upload course syllabi, lecture notes, and reference books here so the AI Question Generator can instantly retrieve context.
            </p>
          </motion.div>
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition-all hover:bg-primary/90"
            >
              Go to Generator
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14" />
                <path d="m12 5 7 7-7 7" />
              </svg>
            </Link>
          </motion.div>
        </div>

        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 xl:items-start">
          {/* LEFT COLUMN: Upload Zone */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }} 
            animate={{ opacity: 1, y: 0 }} 
            transition={{ duration: 0.6 }}
            className="space-y-6 lg:col-span-6"
          >
            <section className="relative overflow-hidden rounded-2xl border border-border bg-card/60 p-6 shadow-sm backdrop-blur-md transition-all sm:p-8">
              <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary/20 via-primary/60 to-primary/20" />
              <h2 className="text-lg font-semibold text-foreground mb-1">Add to Vector Store</h2>
              <p className="text-xs text-muted-foreground mb-6">Documents will be chunked, embedded, and stored for retrieval.</p>
              
              <div className="grid gap-5">
                <div className="grid gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Subject</label>
                  <input
                    type="text"
                    value={newSubject}
                    onChange={(e) => setNewSubject(e.target.value)}
                    placeholder="e.g. Data Structures"
                    className="w-full rounded-lg border border-input bg-background/50 px-4 py-2.5 text-sm text-foreground shadow-sm transition-colors focus:border-primary/50 focus:bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                
                <div className="grid gap-1.5 mb-2">
                  <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Chapter / Unit</label>
                  <input
                    type="text"
                    value={newChapter}
                    onChange={(e) => setNewChapter(e.target.value)}
                    placeholder="e.g. Trees and Graphs"
                    className="w-full rounded-lg border border-input bg-background/50 px-4 py-2.5 text-sm text-foreground shadow-sm transition-colors focus:border-primary/50 focus:bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                {/* Source Tab Selector */}
                <div className="mb-2 flex border-b border-border/40 pb-1.5 overflow-x-auto gap-2">
                  <button
                    type="button"
                    onClick={() => setTab("local")}
                    className={`flex items-center gap-2 border-b-2 pb-2 px-3 text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer ${
                      tab === "local"
                        ? "border-primary text-primary"
                        : "border-transparent text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Local Files
                  </button>
                  <button
                    type="button"
                    onClick={() => setTab("drive")}
                    className={`flex items-center gap-2 border-b-2 pb-2 px-3 text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer ${
                      tab === "drive"
                        ? "border-primary text-primary"
                        : "border-transparent text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Google Drive
                  </button>
                  <button
                    type="button"
                    onClick={() => setTab("classroom")}
                    className={`flex items-center gap-2 border-b-2 pb-2 px-3 text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer ${
                      tab === "classroom"
                        ? "border-primary text-primary"
                        : "border-transparent text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Google Classroom
                  </button>
                </div>

                {/* Local Upload */}
                {tab === "local" && (
                  <div 
                    className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-all ${dragActive ? "border-primary bg-primary/5" : "border-border/60 hover:border-primary/40 hover:bg-muted/30"}`}
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                  >
                    <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="17 8 12 3 7 8" />
                        <line x1="12" x2="12" y1="3" y2="15" />
                      </svg>
                    </div>
                    <p className="text-sm font-semibold text-foreground">
                      Drag and drop documents here
                    </p>
                    <p className="mt-2 text-xs text-muted-foreground max-w-[200px]">
                      Supported: PDF, TXT, DOCX. Max 50MB.
                    </p>
                    <button 
                      onClick={() => fileInputRef.current?.click()}
                      className="mt-6 rounded bg-background border border-border px-4 py-2 text-xs font-semibold text-foreground shadow-sm hover:bg-muted transition"
                    >
                      Browse Files
                    </button>
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      accept=".pdf,.txt,.docx,.xlsx"
                      className="hidden"
                      onChange={handleFileChange}
                    />
                  </div>
                )}

                {/* Google Connection Wrapper */}
                {(tab === "drive" || tab === "classroom") && !googleSessionId && (
                  <div className="flex flex-col items-center justify-center rounded-xl border border-primary/20 bg-primary/5 p-8 text-center shadow-sm">
                    <svg viewBox="0 0 24 24" className="mb-4 h-10 w-10 text-primary" fill="currentColor">
                      <path d="M12.545,10.239v3.821h5.445c-0.712,2.315-2.647,3.972-5.445,3.972c-3.332,0-6.033-2.701-6.033-6.032s2.701-6.032,6.033-6.032c1.498,0,2.866,0.549,3.921,1.453l2.814-2.814C17.503,2.988,15.139,2,12.545,2C7.021,2,2.543,6.477,2.543,12s4.478,10,10.002,10c8.396,0,10.249-7.85,9.426-11.761H12.545z" />
                    </svg>
                    <h4 className="mb-2 text-base font-bold text-foreground">Connect to Google Workspace</h4>
                    <p className="mb-5 max-w-sm text-sm text-muted-foreground">
                      Sign in with Google to browse and select files directly from your Drive or Classroom.
                    </p>
                    <button
                      type="button"
                      onClick={onConnectGoogle}
                      className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition hover:bg-primary/90 cursor-pointer"
                    >
                      Connect Google Account
                    </button>
                  </div>
                )}

                {/* Google Drive Tab */}
                {tab === "drive" && googleSessionId && (
                  <GoogleDriveBrowser
                    sessionId={googleSessionId}
                    selections={googleSelections}
                    setSelections={setGoogleSelections}
                    setError={setGoogleError}
                  />
                )}

                {/* Google Classroom Tab */}
                {tab === "classroom" && googleSessionId && (
                  <GoogleClassroomBrowser
                    sessionId={googleSessionId}
                    selections={googleSelections}
                    setSelections={setGoogleSelections}
                    setError={setGoogleError}
                  />
                )}
                
                {googleError && (
                  <p className="text-xs text-destructive bg-destructive/10 p-2 rounded">{googleError}</p>
                )}

                {/* Selected Queue */}
                {(uploadFiles.length > 0 || googleSelections.length > 0) && (
                  <div className="mt-4 border-t border-border/60 pt-4">
                    <p className="mb-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                      Selected Documents ({uploadFiles.length + googleSelections.length} ready)
                    </p>
                    <ul className="grid gap-2">
                      {uploadFiles.map((f, i) => {
                        const ext = fileExt(f.name);
                        return (
                          <li
                            key={`local-${f.name}-${i}`}
                            className="flex items-center gap-3 rounded-lg border border-border/70 bg-background/90 px-3 py-2.5 shadow-sm"
                          >
                            <FileTypeIcon ext={ext} />
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-xs font-semibold text-foreground" title={f.name}>
                                {f.name}
                              </p>
                              <p className="text-[10px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                                <span className="rounded bg-muted px-1 py-0.2 text-[9px] font-semibold text-muted-foreground">
                                  Local Upload
                                </span>
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => removeLocalFile(i)}
                              className="rounded px-2 py-1 text-xs font-semibold text-muted-foreground transition hover:bg-destructive/10 hover:text-destructive cursor-pointer"
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
                            className="flex items-center gap-3 rounded-lg border border-border/70 bg-background/90 px-3 py-2.5 shadow-sm"
                          >
                            {item.type === "folder" ? (
                              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-amber-500/20 bg-amber-500/10 text-[10px] font-bold text-amber-500 uppercase">
                                fldr
                              </span>
                            ) : (
                              <FileTypeIcon ext={ext} />
                            )}
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-xs font-semibold text-foreground" title={item.name}>
                                {item.name}
                              </p>
                              <p className="text-[10px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                                <span className="rounded bg-sky-500/20 px-1 py-0.2 text-[9px] font-semibold text-sky-400">
                                  {item.source === "drive" ? "Google Drive" : "Classroom"}
                                </span>
                                <span className="h-1 w-1 rounded-full bg-muted-foreground/30" />
                                <span className="capitalize text-[10px]">{item.type}</span>
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => removeGoogleFile(item.id)}
                              className="rounded px-2 py-1 text-xs font-semibold text-muted-foreground transition hover:bg-destructive/10 hover:text-destructive cursor-pointer"
                            >
                              Remove
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}

                <button
                  onClick={onUpload}
                  disabled={uploading || (uploadFiles.length === 0 && googleSelections.length === 0)}
                  className="w-full mt-2 rounded-xl bg-primary px-4 py-3.5 text-sm font-semibold text-primary-foreground shadow-md transition hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {uploading ? (
                    <>
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground" />
                      Embedding into Vector Store...
                    </>
                  ) : (
                    "Upload & Process"
                  )}
                </button>
              </div>
            </section>
            
            {/* Stats Card */}
            <section className="relative overflow-hidden rounded-2xl border border-border bg-card/60 p-6 shadow-sm backdrop-blur-md transition-all">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-4">Vector Database Stats</h3>
              <div className="flex items-center gap-4">
                 <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-secondary/10 text-secondary border border-secondary/20">
                   <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                     <ellipse cx="12" cy="5" rx="9" ry="3" />
                     <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                     <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                   </svg>
                 </div>
                 <div>
                   <p className="text-2xl font-bold text-foreground">{loading ? "-" : totalEmbeddedChunks}</p>
                   <p className="text-xs font-medium text-muted-foreground">Total Embedded Chunks</p>
                 </div>
              </div>
            </section>
          </motion.div>

          {/* RIGHT COLUMN: Interactive Catalog */}
          <motion.div 
            initial="hidden" 
            animate="show" 
            variants={containerVariants}
            className="lg:col-span-6 space-y-6"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                <svg viewBox="0 0 24 24" className="h-5 w-5 text-primary" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="m22 8-6 4 6 4V8Z" />
                  <rect width="14" height="12" x="2" y="6" rx="2" ry="2" />
                </svg>
                Indexed Catalog
              </h2>
              <button onClick={loadCatalog} className="text-xs font-medium text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1 cursor-pointer">
                <svg viewBox="0 0 24 24" className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                  <path d="M3 3v5h5" />
                </svg>
                Refresh
              </button>
            </div>

            {loading && Object.keys(catalog).length === 0 ? (
              <div className="flex h-64 flex-col items-center justify-center rounded-2xl border border-border border-dashed bg-card/30">
                <span className="h-8 w-8 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
                <p className="mt-4 text-sm text-muted-foreground">Connecting to Pinecone / Chroma...</p>
              </div>
            ) : error ? (
              <div className="flex h-64 flex-col items-center justify-center rounded-2xl border border-destructive/30 bg-destructive/5 text-destructive p-6 text-center">
                <svg viewBox="0 0 24 24" className="h-10 w-10 mb-2 opacity-80" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" x2="12" y1="8" y2="12" />
                  <line x1="12" x2="12.01" y1="16" y2="16" />
                </svg>
                <p className="font-semibold">Failed to load Knowledge Base</p>
                <p className="text-xs mt-1 opacity-80">{error}</p>
              </div>
            ) : Object.keys(catalog).length === 0 ? (
              <div className="flex h-64 flex-col items-center justify-center rounded-2xl border border-border border-dashed bg-card/30 text-center px-6">
                <div className="mb-4 rounded-full bg-muted p-4">
                  <svg viewBox="0 0 24 24" className="h-8 w-8 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" x2="8" y1="13" y2="13" />
                    <line x1="16" x2="8" y1="17" y2="17" />
                    <polyline points="10 9 9 9 8 9" />
                  </svg>
                </div>
                <p className="font-medium text-foreground">Your vector store is empty</p>
                <p className="mt-1 max-w-sm text-xs text-muted-foreground">
                  Use the uploader on the left to add your first syllabus or reference textbook.
                </p>
              </div>
            ) : (
              <div className="grid gap-4">
                {Object.entries(catalog).map(([subjKey, subjNode]) => (
                  <motion.div key={subjKey} variants={itemVariants} className="overflow-hidden rounded-xl border border-border bg-card/80 shadow-sm backdrop-blur-sm">
                    <div className="border-b border-border bg-muted/20 px-5 py-4">
                      <h3 className="font-semibold text-foreground flex items-center gap-2.5">
                        <span className="flex h-7 w-7 items-center justify-center rounded bg-primary/10 text-primary border border-primary/20 shadow-sm">
                          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z" />
                            <path d="M6 6h10" />
                            <path d="M6 10h10" />
                          </svg>
                        </span>
                        {subjNode.name}
                      </h3>
                    </div>
                    <div className="divide-y divide-border/50 px-2 py-1">
                      {subjNode.children && Object.entries(subjNode.children).map(([chapKey, chapNode]) => (
                        <div key={chapKey} className="flex items-center justify-between px-3 py-3 hover:bg-muted/40 transition-colors rounded-lg mx-1 my-1">
                          <div className="flex items-center gap-3">
                            <svg viewBox="0 0 24 24" className="h-4 w-4 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <circle cx="12" cy="12" r="10" />
                              <polyline points="12 16 16 12 12 8" />
                              <line x1="8" x2="16" y1="12" y2="12" />
                            </svg>
                            <span className="text-sm font-medium text-foreground">{chapNode.name}</span>
                          </div>
                          <span className="rounded-full bg-secondary/10 px-2.5 py-0.5 text-[10px] font-semibold tracking-wide text-secondary border border-secondary/20">
                            {chapNode.chunk_count} Chunks
                          </span>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>
        </div>
      </main>
    </div>
  );
}

export default function KnowledgeBaseManager() {
  return (
    <Suspense fallback={<div>Loading Knowledge Base...</div>}>
      <KnowledgeBaseManagerInner />
    </Suspense>
  );
}
