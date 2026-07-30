# Auto Question Paper Generation

A full-stack application that leverages Agentic RAG and Large Language Models to automatically generate university-grade question papers, answer keys, and marking schemes from uploaded syllabus documents and course materials.

## Project Structure

This repository is structured as a monorepo containing both the frontend and backend applications:

- **`frontend/`**: The user interface built with React, Vite, and modern web technologies.
- **`backend/`**: The FastAPI server that handles document ingestion, Agentic RAG pipelines, LLM orchestration, and PDF generation.

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js & npm/bun
- An API Key for your configured LLM (e.g., Gemini, Groq)

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up environment variables:
   Copy `.env.example` to `.env` and fill in your API keys and configuration.
5. Run the server:
   ```bash
   python -m app.main 
   or
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   The backend API will run on `http://localhost:8000`.

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   # or bun install
   ```
3. Run the development server:
   ```bash
   npm run dev
   # or bun run dev
   ```
   The UI will be available at `http://localhost:5173`.

## Architecture Overview
The system uses an advanced agentic workflow (powered by LangGraph) to ensure high-quality question papers. The pipeline includes:
- **Image Extraction & Processing**: Filters out decorative elements and strictly isolates academic figures.
- **Syllabus Parsing Agent**: Structures the uploaded documents.
- **Question Generation Agent**: Uses selective image generation constraints and Bloom's taxonomy distributions.
- **Validation Agent**: Ensures generated questions strictly adhere to constraints.
- **Answer Key Agent**: Generates robust model answers and marking schemes.
- **PDF Generation**: Outputs production-ready examination papers.
