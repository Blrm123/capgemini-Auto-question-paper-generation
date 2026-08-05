# Backend Architecture & Flow Explanation

This document provides a detailed breakdown of the backend system for the Agentic Question Paper Generator. The system is built using **FastAPI** for the web framework, **LangGraph** for agentic orchestration, and a **Hybrid RAG** (Retrieval-Augmented Generation) pipeline for document context.

---

## 1. High-Level Flow (End-to-End)

The entry point for generating a question paper is the `POST /generate` endpoint in [`main.py`](file:///e:/PROJECTS/karthik-capgemini/QP-generator-with-frontend/backend/app/main.py). Here is the lifecycle of a request:

1. **Request Intake (`main.py`)**: The user uploads one or more syllabus/document files (PDF, TXT, DOCX, etc.) along with parameters like paper metadata, marks distribution, and difficulty levels.
2. **Orchestrator Setup (`orchestrator.py`)**: The request is handed to the `Orchestrator`, which manages the overall lifecycle.
3. **RAG Ingestion (`rag_service.py`)**: The uploaded files are passed to the `RAGService`. It chunks the text, computes embeddings, and stores them in a hybrid vector store.
4. **LangGraph Workflow (`langgraph_workflow.py`)**: The orchestrator initializes an `AgentState` and triggers the LangGraph state machine, executing a sequence of specialized AI agents.
5. **PDF Generation (`pdf_generator.py`)**: After all agents succeed, the final validated questions and answer key are converted into structured PDF documents.
6. **Response**: The API returns the paths to the generated PDFs to the frontend.

---

## 2. Models Used

The system primarily relies on **Google Gemini** models via API, defined in [`config.py`](file:///e:/PROJECTS/karthik-capgemini/QP-generator-with-frontend/backend/app/config.py). Different models are mapped to specific agents for optimal cost-performance:

- **`gemini-3.5-flash-lite`**: Used for `PDFParser`, `ImageDescriptorAgent`, `SyllabusAgent`, `QuestionGeneratorAgent`, and `AnswerKeyAgent`.
- **`gemini-3.1-flash-lite`**: Used for `BloomAgent`, `ValidationAgent`, `DifficultyClassifier`, and `DuplicateDetector`.
- **Fallback (Groq)**: The system also has fallback logic utilizing `llama-3.3-70b-versatile` via Groq in case primary LLM calls fail.

---

## 3. RAG Pipeline (Retrieval-Augmented Generation)

Located in [`app/services/rag_service.py`](file:///e:/PROJECTS/karthik-capgemini/QP-generator-with-frontend/backend/app/services/rag_service.py). This is not just a simple semantic search; it's a **Hybrid RAG pipeline**.

**Flow:**
1. **Ingestion**: Documents are chunked into smaller segments.
2. **Indexing**: Chunks are embedded and stored in a vector database. The system connects to **Pinecone** if `PINECONE_API_KEY` is configured in the environment. If not, it falls back to a local **FAISS** index. (It also maintains a local **BM25** index for sparse keyword search).
3. **Retrieval**: 
   - A query searches the vector store (Pinecone or FAISS) and the sparse index (BM25, if available locally).
   - The results are combined using **Reciprocal Rank Fusion (RRF)**.
   - The top combined results are re-evaluated using a **Cross-Encoder Reranker** to ensure maximum relevance before being sent to the LLM.

---

## 4. The Agentic Workflow (LangGraph)

The core logic of generating the question paper is handled by a multi-agent system orchestrated by LangGraph in [`app/workflows/langgraph_workflow.py`](file:///e:/PROJECTS/karthik-capgemini/QP-generator-with-frontend/backend/app/workflows/langgraph_workflow.py). 

The agents execute strictly in the following sequential order. If any agent fails, the state transitions to `END` and aborts.

### Step 1: `SyllabusAgent`
- **Role**: Parses the initially retrieved chunks to extract a structured list of syllabus topics, units, and learning objectives.
- **Why first?**: It defines the "real" topics of the course so subsequent agents know exactly what to target.

### Step 2: `ImageDescriptorAgent`
- **Role**: Uses Gemini Vision models to analyze any images/diagrams present in the syllabus documents.
- **Action**: It maps these image descriptions to the structured topics extracted in Step 1.

### Step 3: `TopicRetrievalAgent`
- **Role**: Refreshes the RAG context.
- **Action**: Instead of a generic query, it queries the `RAGService` *specifically* for each topic extracted by the `SyllabusAgent`. This provides highly focused, deduplicated evidence chunks for the next step.

### Step 4: `QuestionGeneratorAgent`
- **Role**: The heavy lifter. It generates the actual exam questions.
- **Action**: Uses the topic-specific RAG context, image descriptions, and user-defined distribution (marks, counts) to formulate questions that strictly adhere to the source material.

### Step 5: `BloomAgent`
- **Role**: Educational analysis.
- **Action**: Evaluates the generated questions and tags them according to Bloom's Taxonomy levels (e.g., Knowledge, Comprehension, Application, Analysis).

### Step 6: `ValidationAgent`
- **Role**: Quality Assurance.
- **Action**: Verifies structural quality, checks for formatting errors, ensures marks add up, and confirms that the questions meet the specified blueprint constraints.

### Step 7: `AnswerKeyAgent`
- **Role**: Finalizes output.
- **Action**: Generates a comprehensive answer key or grading rubric for the validated set of questions.

---

## 5. Summary of Key Modules

- **`app/main.py`**: FastAPI routing, middleware (CORS), and application lifespan management.
- **`app/config.py`**: Environment variables, LLM configs, model assignments, and path management.
- **`app/agents/orchestrator.py`**: The central coordinator connecting FastAPI inputs to the LangGraph workflow and final PDF output.
- **`app/workflows/langgraph_workflow.py`**: Defines the nodes (agents) and edges (routing) of the StateGraph.
- **`app/models/state.py`**: Defines the `AgentState` object that gets passed from agent to agent, holding all intermediate data (chunks, topics, questions).
- **`app/services/rag_service.py`**: Bridge to the FAISS/BM25/Reranker indexing and retrieval system.
- **`app/services/pdf_generator.py`**: Converts the final JSON/Dict representations of questions and answers into formatted PDF files using a templating or drawing library.
