"use client";

import React, { useEffect, useState, useRef } from "react";
import { motion, Variants } from "framer-motion";
import { getKnowledgeList, uploadKnowledge, startGoogleOauth, type CatalogNode } from "@/lib/api";
import Link from "next/link";
import { toast } from "sonner";

export default function KnowledgeBaseManager() {
  const [catalog, setCatalog] = useState<Record<string, CatalogNode>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newSubject, setNewSubject] = useState("");
  const [newChapter, setNewChapter] = useState("");
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const onUpload = async () => {
    if (!newSubject.trim() || !newChapter.trim() || uploadFiles.length === 0) {
      toast.error("Please enter a subject, chapter, and select files to upload.");
      return;
    }
    setUploading(true);
    try {
      await uploadKnowledge(newSubject, newChapter, uploadFiles);
      setNewSubject("");
      setNewChapter("");
      setUploadFiles([]);
      toast.success("Documents successfully added to the Knowledge Base!");
      await loadCatalog();
    } catch (e) {
      toast.error("Error uploading: " + (e as Error).message);
    } finally {
      setUploading(false);
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
    <div className="relative min-h-screen text-foreground pb-20">
      <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 bg-background">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/5 via-background to-background"></div>
      </div>

      <main className="relative mx-auto w-full max-w-[1440px] px-4 py-8 sm:px-6 lg:px-8">
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
            className="space-y-6 lg:col-span-5"
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
                
                <div className="grid gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Chapter / Unit</label>
                  <input
                    type="text"
                    value={newChapter}
                    onChange={(e) => setNewChapter(e.target.value)}
                    placeholder="e.g. Trees and Graphs"
                    className="w-full rounded-lg border border-input bg-background/50 px-4 py-2.5 text-sm text-foreground shadow-sm transition-colors focus:border-primary/50 focus:bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                <div 
                  className={`mt-2 flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-all ${dragActive ? "border-primary bg-primary/5" : "border-border/60 hover:border-primary/40 hover:bg-muted/30"}`}
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
                    {uploadFiles.length > 0 ? `${uploadFiles.length} file(s) selected` : "Drag and drop documents here"}
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground max-w-[200px]">
                    {uploadFiles.length > 0 ? uploadFiles.map(f => f.name).join(", ") : "Supported: PDF, TXT, DOCX. Max 50MB."}
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

                <button
                  onClick={onUpload}
                  disabled={uploading}
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
            
            {/* Google Workspace Block */}
            <section className="flex flex-col items-center justify-center py-10 text-center rounded-2xl border border-dashed border-border/60 bg-card/40 backdrop-blur-md shadow-sm">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary shadow-sm">
                <svg
                  viewBox="0 0 24 24"
                  className="h-6 w-6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3Z" />
                </svg>
              </div>
              <h3 className="text-sm font-bold text-foreground">Import from Google Workspace</h3>
              <p className="mt-1.5 max-w-sm px-4 text-xs text-muted-foreground leading-relaxed">
                Connect your account to index syllabus documents, notes, and worksheets directly from
                your Google Drive folders and Google Classroom classes.
              </p>
              <button
                type="button"
                onClick={onConnectGoogle}
                className="mt-5 inline-flex items-center gap-2 rounded-lg bg-[#E05F36] px-5 py-2.5 text-xs font-semibold text-white shadow-sm transition hover:bg-[#E05F36]/90 cursor-pointer"
              >
                <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12.24 10.285V13.4h6.887C18.2 15.614 15.645 18 12.24 18c-3.86 0-7-3.14-7-7s3.14-7 7-7c1.7 0 3.3.6 4.5 1.7l2.4-2.4C17.3 1.7 14.9 1 12.24 1 6.58 1 2 5.58 2 11.24s4.58 10.24 10.24 10.24c5.79 0 10.24-4.1 10.24-10.24 0-.6-.05-1.2-.15-1.75H12.24z" />
                </svg>
                Connect Google Account
              </button>
            </section>
            
            {/* Stats Card */}
            <section className="relative overflow-hidden rounded-2xl border border-border bg-card/60 p-6 shadow-sm backdrop-blur-md transition-all">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-4">Vector Database Stats</h3>
              <div className="flex items-center gap-4">
                 <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-500/10 text-blue-500 border border-blue-500/20">
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
            className="lg:col-span-7 space-y-6"
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
                          <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-semibold tracking-wide text-emerald-500 border border-emerald-500/20">
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
