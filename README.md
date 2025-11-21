# Impact Unplugged - Team JarvisAI⚡️

**Impact Unplugged** is an AI-driven code impact analysis tool designed to help developers understand the ripple effects of their changes before they merge. By combining static analysis with Large Language Models (Google Gemini), it maps dependencies and predicts potential risks.

> **Stop fighting fires. Prevent them.**
> An AI-powered Code Impact Analysis Engine that predicts the ripple effects of your commits *before* you merge.

---

## 🚀 Project Overview

In modern software development, **velocity is king**, but **regression is the killer**. A simple one-line change in a utility function can silently break a critical payment flow five layers deep. Developers waste hours manually tracing dependencies or, worse, debugging production incidents.

**Impact Unplugged** solves this by treating your codebase as a **connected knowledge graph**. It combines **Static Analysis (AST)** with **Semantic Search (RAG)** and **Large Language Models (Gemini 2.5 Flash)** to provide a deterministic yet intelligent impact assessment.

**Key Capabilities:**
- **🔍 Deep Dependency Mapping**: Goes beyond regex. We build a directed graph of your entire codebase, linking functions, classes, and modules.
- **🌊 Ripple Effect Detection**: Identifies not just what you changed, but *who calls what you changed*, recursively.
- **🤖 AI Risk Oracle**: Uses GenAI to analyze the *semantic intent* of the change against the *usage context* of dependent functions to predict bugs and suggest test cases.
- **⚡️ Zero-Config**: Just paste a GitHub URL. No complex CI/CD integration required for the demo.

---

## 🏗️ System Architecture

Impact Unplugged is built on a **modular, service-oriented architecture** designed for scalability and precision.

### 1. The Ingestion Engine 📥
- **Repo Manager**: Clones repositories to a persistent local store (`/repos`), ensuring stable file access.
- **Vector Store (ChromaDB)**: Chunks code into function-level blocks using AST parsing. These chunks are embedded (using `all-MiniLM-L6-v2`) and stored for semantic retrieval.

### 2. The Dependency Graph 🕸️
- **Static + Semantic Analysis**: We don't just guess. We parse the code to find imports and function definitions.
- **NetworkX Core**: The entire codebase is modeled as a directed graph (`G`). Nodes are functions/files; Edges are relationships (`calls`, `imports`, `defines`).
- **Persistence**: The graph is serialized to JSON, allowing for instant re-loading without re-analysis.

### 3. The Impact Engine 💥
- **Diff Parsing**: Integrates with GitHub API to fetch raw commit diffs.
- **Smart Mapping**: Maps changed lines from the diff to specific nodes in the Dependency Graph.
- **Graph Traversal**: Performs a reverse BFS (Breadth-First Search) to identify all upstream dependents (the "Ripple Effect").

### 4. The Intelligence Layer 🧠
- **Context Assembly**: Aggregates the *full source code* of the changed function AND the *relevant snippets* of affected callers.
- **LLM Reasoning (Gemini 2.5 Flash)**: The context is fed into Google's Gemini model with a specialized prompt to generate a **Risk Assessment Report**, highlighting potential logic errors and functional breaks.

### 5. The Interface 💻
- **FastAPI Backend**: Exposes RESTful endpoints for analysis and graph retrieval.
- **Streamlit Frontend**: A reactive dashboard for interactive graph visualization (`streamlit-agraph`) and report viewing.

---

## 🚀 Features

- **Repository Ingestion**: Clones GitHub repositories and analyzes code structure.
- **Dependency Mapping**: Builds a graph of inter-module and inter-function dependencies using AST parsing and LLMs.
- **Impact Analysis**:
    - Fetches commit diffs via GitHub API.
    - Maps changed lines to specific functions.
    - Identifies "Ripple Effects" (callers of changed functions).
    - Generates an AI-powered **Risk Assessment Report**.
- **Interactive UI**: A Streamlit dashboard to visualize dependency graphs and view impact reports.


---

## 🛠️ Tech Stack

- **Backend**: FastAPI, Python 3.12
- **AI/LLM**: Google Gemini 2.5 Flash (`google-generativeai`)
- **Vector DB**: ChromaDB (for semantic code search)
- **Graph**: NetworkX (for dependency modeling)
- **Frontend**: Streamlit, Streamlit Agraph
- **Utils**: GitPython, Pydantic

## 📦 Installation

1.  **Clone the Repository**:
    ```bash
    git clone <your-repo-url>
    cd code-fire-preventer
    ```

2.  **Set up Environment**:
    Create a `.env` file in the root directory:
    ```ini
    GOOGLE_API_KEY=your_google_api_key
    CHROMA_DB_DIR=./chroma_db
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## 🏃‍♂️ Usage

### 1. Start the Backend
Run the FastAPI server:
```bash
uvicorn main:app --reload
```
The API will be available at `http://127.0.0.1:8000`.

### 2. Start the Frontend
Run the Streamlit app:
```bash
streamlit run streamlit_app.py
```
The UI will open in your browser at `http://localhost:8501`.

### 3. Workflow
1.  **Analyze Repo**: Go to the "Repository Analysis" tab, enter a GitHub URL (e.g., `https://github.com/psf/requests`), and click "Analyze". This builds the dependency graph.
2.  **View Graph**: Once analyzed, click "Load Graph" to visualize the module connections.
3.  **Check Impact**: Switch to the "Impact Analysis" tab. Enter the same Repo URL and a specific **Commit SHA**.
4.  **Get Report**: The tool will show you:
    - **Directly Affected Functions**
    - **Ripple Effects** (who calls them)
    - **AI Risk Analysis** (bugs, functional impact, test cases)

## 📂 Project Structure

```
.
├── app/
│   ├── services/
│   │   ├── analyzer.py       # Dependency analysis & Impact logic
│   │   ├── github_service.py # GitHub API integration
│   │   ├── repo_manager.py   # Cloning & file management
│   │   └── vector_store.py   # ChromaDB & Chunking
│   └── config.py             # Settings
├── main.py                   # FastAPI entrypoint
├── streamlit_app.py          # Frontend
├── requirements.txt          # Dependencies
└── README.md                 # Documentation
```

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## 📄 License

MIT License
