# QUBIT Backend

An AI-powered question paper generator that automatically creates university/college-level question papers from uploaded syllabus documents, Google Drive files, and Google Classroom materials. It uses a **Multi-Agent AI architecture** built with LangGraph and powered by Gemini LLMs (with Groq fallback).

---

## Features

- **Multi-Source Ingestion:** Upload local files, or pull directly from Google Drive and Google Classroom.
- **RAG Architecture (Hybrid):** Uses local in-memory FAISS for fast ad-hoc question paper generation, and cloud-based Pinecone for permanent Knowledge Base storage to avoid vector pollution.
- **Multi-Agent Pipeline:** Syllabus Extraction → RAG Context Retrieval → Question Generation → Bloom's Taxonomy Tagging → Quality Validation → Answer Key Generation.
- **Configurable Output:** Set marks distribution (2M / 5M / 10M / 15M questions) and difficulty balancing (Easy / Medium / Hard).
- **Professionally Formatted PDFs:** Automatically generates a formatted Question Paper and a separate Answer Key PDF.
- **Frontend Dashboard:** A React-based UI for managing knowledge, selecting sources, and generating papers.

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **Frontend** | Next.js, React, TypeScript, TailwindCSS |
| **AI Orchestration** | LangGraph |
| **Vector Database (RAG)** | Pinecone (Knowledge Base) & FAISS (Local Temporary Memory) |
| **Embeddings** | HuggingFace (`all-MiniLM-L6-v2`) |
| **LLM Provider** | Google Gemini API (Primary) / Groq API (Fallback) |
| **Default Models** | `gemini-2.5-flash-lite` (Gemini), `llama-3.3-70b-versatile` (Groq) |
| **Database** | SQLite (`catalog.db`) for Frontend Knowledge Management |
| **PDF Generation** | ReportLab |
| **PDF Parsing** | pypdf |

---

## Architecture Flow

The question paper generation is orchestrated by a stateful LangGraph workflow that executes in the following sequence:

1. **Ingestion (`rag_service.py`):**
   - Files (PDF, TXT, DOCX) are chunked and embedded.
   - For ad-hoc generation, chunks are stored in a temporary, blazing-fast local FAISS index.
   - For Knowledge Base uploads, chunks are securely stored in Pinecone and registered in `catalog.db`.

2. **Syllabus Agent (`syllabus_agent.py`):**
   - Reads the documents and extracts structured syllabus units and topics.

3. **Image Descriptor Agent (`image_descriptor_agent.py`):**
   - Processes any images found in the documents using Gemini's Vision capabilities.

4. **Topic Retrieval Agent (`topic_retrieval_agent.py`):**
   - Queries the vector database to retrieve specific contextual chunks for each identified syllabus topic.

5. **Question Generator Agent (`question_generator_agent.py`):**
   - Uses the RAG context and blueprint distribution (marks/difficulty) to generate exam questions.

6. **Bloom Agent (`bloom_agent.py`):**
   - Analyzes generated questions and assigns Bloom's Taxonomy levels (Remember, Understand, Apply, etc.) along with a justification.

7. **Validation Agent (`validation_agent.py`):**
   - Reviews questions for structural quality, checking for formatting errors, missing data, and blueprint mismatch.

8. **Answer Key Agent (`answerkey_agent.py`):**
   - Generates detailed model answers and step-by-step marking schemes for all validated questions.

9. **PDF Generation (`pdf_generator.py`):**
   - Compiles the final state into two polished PDFs: the Question Paper and the Answer Key.

---

## Project Structure

```text
question-paper-generator/
│
├── frontend/                          # React + Vite web dashboard
│
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI application & API endpoints
│   │   ├── config.py                  # Centralised settings
│   │   │
│   │   ├── agents/                    # LangGraph AI Agents
│   │   │   ├── orchestrator.py        # Top-level workflow coordinator
│   │   │   ├── syllabus_agent.py      
│   │   │   ├── image_descriptor_agent.py
│   │   │   ├── topic_retrieval_agent.py
│   │   │   ├── question_generator_agent.py
│   │   │   ├── bloom_agent.py         
│   │   │   ├── validation_agent.py    
│   │   │   └── answerkey_agent.py     
│   │   │
│   │   ├── workflows/
│   │   │   └── langgraph_workflow.py  # LangGraph StateGraph definition
│   │   │
│   │   ├── services/
│   │   │   ├── llm_service.py         # LLM wrapper (Gemini + Groq)
│   │   │   ├── rag_service.py         # Ingestion orchestration
│   │   │   ├── catalog_service.py     # SQLite knowledge catalog manager
│   │   │   ├── pdf_generator.py       
│   │   │   └── logger.py              
│   │   │
│   │   ├── models/
│   │   │   └── state.py               # LangGraph TypedDict state
│   │   │
│   │   └── rag/                       # Local ingestion pipelines
│   │       ├── src/
│   │       │   ├── ingestion/embedder.py
│   │       │   └── pipeline/rag_pipeline.py
│   │       └── vectorstore/           # FAISS index storage location
│   │
│   ├── uploaded_documents/            # Temp storage for ad-hoc uploads
│   ├── generated_papers/              # Output PDFs
│   ├── catalog.db                     # SQLite database for knowledge base
│   └── requirements.txt               
```

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd question-paper-generator
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file and set your Groq API key:

```env
# Required
GROQ_API_KEY=your_groq_api_key_here

# Optional (defaults shown)
MODEL_NAME=llama-3.3-70b-versatile
TEMPERATURE=0.3
MAX_RETRIES=3
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
```

Get your free Groq API key at: https://console.groq.com

---

## Running the Server

```bash
python -m app.main
```

Or with uvicorn directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: **http://localhost:8000**

Interactive API docs: **http://localhost:8000/docs**

---

## API Reference

### `POST /generate` — Generate a Question Paper

Upload a syllabus and generate a full question paper.

**Form Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file` | File | — | Syllabus PDF or TXT (required) |
| `total_marks` | int | 100 | Total marks for the paper |
| `two_mark_questions` | int | 5 | Number of 2-mark questions |
| `five_mark_questions` | int | 4 | Number of 5-mark questions |
| `ten_mark_questions` | int | 3 | Number of 10-mark questions |
| `fifteen_mark_questions` | int | 2 | Number of 15-mark questions |
| `easy_percentage` | int | 30 | % of easy questions |
| `medium_percentage` | int | 50 | % of medium questions |
| `hard_percentage` | int | 20 | % of hard questions |
| `institution_name` | str | "University" | Institution name for PDF header |
| `course_name` | str | "Course" | Course name |
| `course_code` | str | "CS101" | Course code |
| `semester` | str | "I" | Semester |
| `exam_type` | str | "End Semester Examination" | Exam type |
| `duration` | str | "3 Hours" | Duration |
| `exam_date` | str | null | Optional exam date |

**Example using curl:**

```bash
curl -X POST http://localhost:8000/generate \
  -F "file=@syllabus.pdf" \
  -F "total_marks=100" \
  -F "two_mark_questions=10" \
  -F "five_mark_questions=4" \
  -F "ten_mark_questions=3" \
  -F "fifteen_mark_questions=2" \
  -F "easy_percentage=30" \
  -F "medium_percentage=50" \
  -F "hard_percentage=20" \
  -F "institution_name=MIT" \
  -F "course_name=Internet of Things" \
  -F "course_code=IOT501" \
  -F "semester=V" \
  -F "exam_type=End Semester Examination"
```

**Response:**

```json
{
  "success": true,
  "message": "Question paper and answer key generated successfully in 42.3s.",
  "final_pdf_path": "generated_papers/question_paper_20240611_143022.pdf",
  "answer_key_pdf_path": "generated_papers/answer_key_20240611_143022.pdf",
  "elapsed_seconds": 42.3,
  "errors": []
}
```

---

### `GET /papers` — List Generated Papers

```bash
curl http://localhost:8000/papers
```

**Response:**

```json
{
  "total": 2,
  "files": [
    "question_paper_20240611_143022.pdf",
    "answer_key_20240611_143022.pdf"
  ]
}
```

---

### `GET /download/{filename}` — Download a PDF

```bash
curl -O http://localhost:8000/download/question_paper_20240611_143022.pdf
```

---

### `GET /health` — Health Check

```bash
curl http://localhost:8000/health
```

**Response:**

```json
{
  "status": "ok",
  "version": "1.0.0",
  "model": "llama-3.3-70b-versatile"
}
```

---

## Multi-Agent Workflow

```
START
  │
  ▼
[Syllabus Agent]
  Reads:  uploaded_text
  Output: syllabus_topics (units & topics as JSON)
  │
  ▼
[Question Generator Agent]
  Reads:  syllabus_topics, question_distribution
  Output: generated_questions (id, unit, topic, marks, difficulty)
  │
  ▼
[Bloom Taxonomy Agent]
  Reads:  generated_questions
  Output: bloom_analysis (+ bloom_level, bloom_justification per question)
  │
  ▼
[Validation Agent]
  Reads:  bloom_analysis, syllabus_topics, question_distribution
  Checks: duplicates, coverage, marks distribution, Bloom balance, quality
  Output: validated_questions (corrected if needed)
  │
  ▼
[Answer Key Agent]
  Reads:  validated_questions
  Output: answer_key (model_answer, key_points, marks_breakdown)
  │
  ▼
[PDF Generator]
  Output: question_paper_*.pdf + answer_key_*.pdf
  │
  ▼
END
```

If any agent fails, the workflow stops immediately via LangGraph conditional edges.

---

## Marks Distribution Constraint

The values you pass must satisfy:

```
(two_mark_questions × 2) + (five_mark_questions × 5) +
(ten_mark_questions × 10) + (fifteen_mark_questions × 15) == total_marks

easy_percentage + medium_percentage + hard_percentage == 100
```

The Orchestrator validates this before invoking the workflow.

---

## Logs

All logs are written to `logs/application.log` with rotating file handler (10 MB max, 5 backups).

Console output is color-coded by level:

| Level | Color |
|---|---|
| DEBUG | Cyan |
| INFO | Green |
| WARNING | Yellow |
| ERROR | Red |
| CRITICAL | Magenta |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Future Enhancements

- RAG-based syllabus retrieval using vector databases
- MCQ generation support
- Multi-language question papers
- Faculty review workflow
- Adaptive difficulty based on student performance data
- Hybrid RAG with multiple document sources
