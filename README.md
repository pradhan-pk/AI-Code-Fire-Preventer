# Impact Unplugged - Team JarvisAI⚡️

**AI-Powered Multi-Repository Code Impact & Breaking Change Analyzer**

Detect cascading effects of code changes across **multiple microservices**, **monorepos**, or **independent repositories** — before they break production.

Supports **Python + Java** (mixed environments), detects **direct/indirect/cascading impacts**, **breaking changes**, **OpenAPI drift**, and generates **AI-powered remediation & test recommendations** using **Gemini 2.5 Flash**, **Llama Scout**, or **Mistral**.

Live demo: [http://127.0.0.1:8000](http://127.0.0.1:8000)  
Streamlit UI: [http://127.0.0.1:8501](http://127.0.0.1:8501)

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
- **Multi-Repo Support**: Analyze multiple repositories simultaneously.
- **Cross-Language**: Python and Java parsing with tree-sitter.
- **AI Fallbacks**: Switches to Mistral or Llama Scout on rate limits.

---

## 🛠️ Tech Stack

- **Backend**: FastAPI, Python 3.10+
- **AI/LLM**: Google Gemini 2.5 Flash (`google-generativeai`), Mistral, Llama Scout (OpenRouter)
- **Vector DB**: ChromaDB (for semantic code search)
- **Graph**: NetworkX (for dependency modeling)
- **Frontend**: Streamlit, Streamlit Agraph
- **Parsing**: Tree-sitter (bundled languages), AST
- **Utils**: GitPython, Pydantic, Requests

---

## 📦 Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/AI-Code-Fire-Preventer.git
   cd AI-Code-Fire-Preventer

2. **Set up Environment**:
    Create a .env file in the root directory:
    GOOGLE_API_KEY=your_gemini_api_key_here
    # Optional: For LLM fallbacks
    OPENROUTER_API_KEY=your_openrouter_key_here
    MISTRAL_API_KEY=your_mistral_key_here

3. **Install Dependencies**
    pip install -r requirements.txt


🏃‍♂️ Usage
1. Start the Backend
Run the FastAPI server: uvicorn main:app --reload
The API will be available at http://127.0.0.1:8000.

2. Start the Frontend
Run the Streamlit app: streamlit run streamlit_app.py
The UI will open in your browser at http://localhost:8501.

3. Workflow
Analyze Repos: In the "Repository Setup" tab, add GitHub URLs and start analysis.
Wait for Completion: Status updates automatically.
Analyze Impact: In the "Impact Analysis" tab, select a repo, enter commit SHA, and analyze.
View Results: See impacts, breaking changes, AI report, and graph.


📂 Project Structure

AI-Code-Fire-Preventer/
├── analyses/                    # Example analysis outputs
├── app/
│   ├── __pycache__/
│   ├── models/
│   │   └── impact_node.py       # Pydantic/Node models
│   ├── services/
│   │   ├── dependency_resolver.py
│   │   ├── enhanced_analysis.py # Core impact engine
│   │   ├── github_service.py
│   │   ├── multi_repo_manager.py
│   │   ├── vector_store.py
│   │   └── __init__.py
│   └── config.py                # Settings & .env loading
├── chroma_db/                   # Persistent Chroma vector store
├── llm_cache/                   # Optional LLM response cache
├── repos/                       # Cloned repositories (persistent)
├── utils/
├── .env                         # Your API keys
├── .gitignore                                      
├── main.py                      # FastAPI entrypoint
├── README.md
├── requirements.txt
├── streamlit_app.py             # Interactive frontend


## Contributing
Contributions are  welcome!

## License
MIT © 2025 Team JarvisAI@Impact Unplugged

You now have one of the most advanced open-source code impact analyzers available.
Go break things safely.
Made with ❤️ by developers who hate surprise production incidents