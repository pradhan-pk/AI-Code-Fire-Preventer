# Impact Unplugged - Team JarvisAI⚡️

**Impact Unplugged** is an AI-driven code impact analysis tool designed to help developers understand the ripple effects of their changes before they merge. By combining static analysis with Large Language Models (Google Gemini), it maps dependencies and predicts potential risks.

## 🚀 Features

- **Repository Ingestion**: Clones GitHub repositories and analyzes code structure.
- **Dependency Mapping**: Builds a graph of inter-module and inter-function dependencies using AST parsing and LLMs.
- **Impact Analysis**:
    - Fetches commit diffs via GitHub API.
    - Maps changed lines to specific functions.
    - Identifies "Ripple Effects" (callers of changed functions).
    - Generates an AI-powered **Risk Assessment Report**.
- **Interactive UI**: A Streamlit dashboard to visualize dependency graphs and view impact reports.

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
