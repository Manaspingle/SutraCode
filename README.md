# SutraTrace — Evidence-Grounded AI Code Debugging Assistant

> **Tagline:** Trace the cause. Verify the fix.

SutraTrace is a production-grade, evidence-grounded programming code explainer and debugging assistant built with Django, Google Gemini, ChromaDB, PyMuPDF, Sentence Transformers, and Firebase Authentication/Firestore.

Unlike generic LLM chatbots that hallucinate plausible-sounding fixes, SutraTrace enforces a strict **Retrieval-Augmented Generation (RAG)** pipeline: it retrieves exact passages from your uploaded technical manuals (PDF/TXT) and feeds them to Google Gemini as factual evidence before any diagnosis or code diff is generated.

---

## 🌟 Key Features

1. **Context-Aware Vector Retrieval (RAG):**
   - Ingests technical documentation in PDF or TXT formats using **PyMuPDF** and UTF-8 processing.
   - Text is segmented into semantic sliding windows (700–1,000 characters with 150-char overlap).
   - Embedded into 384-dimensional dense vectors using **Sentence Transformers (`all-MiniLM-L6-v2`)** and indexed in a local, persistent **ChromaDB** vector store.
2. **Grounded AI Diagnosis via Google Gemini:**
   - Uses the official `google-genai` Python SDK with multi-model fallback resiliency (`gemini-flash-latest`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`).
   - Strict safety system prompt treats submitted code and documents as untrusted content, preventing prompt injections.
   - Emphasizes minimal, surgical corrections instead of rewriting entire programs unnecessarily.
3. **Structured Verification Output:**
   - **Diagnosis Summary & Severity Badge:** Critical, High, Medium, Low, or Informational.
   - **Root Cause Reasoning:** Separates hard facts from speculative inferences.
   - **Interactive Unified Diff:** Clear color-coded additions (`+`) and removals (`-`).
   - **Why This Fix Works:** Step-by-step logic breakdown.
   - **Suggested Regression Tests:** Copyable unit tests/assertions to run locally.
   - **Evidence Drawer:** Verbatim source passages with file names, page numbers, and cosine match scores.
   - **Limitations & Confidence:** Transparent disclosure if documentation is missing or inadequate.
4. **Firebase Authentication & Cloud Firestore Integration:**
   - Sign in with Google Popup or Email/Password.
   - Verifies Firebase ID tokens on Django backend (`Authorization: Bearer <id_token>`) to enforce per-user document and vector isolation.
   - Synchronizes user profiles and analysis history to Cloud Firestore.
5. **Zero-Execution Code Safety:**
   - The application **never executes untrusted submitted code**, eliminating sandbox escape and remote code execution vulnerabilities.

---

## 🏗️ Architecture Overview

```
                      +-----------------------------+
                      |   Developer Web Frontend    |
                      | Bootstrap 5 + Highlight.js  |
                      |  Firebase Auth & Firestore  |
                      +--------------+--------------+
                                     |
               (Authorization: Bearer <Firebase_ID_Token>)
                                     v
                      +-----------------------------+
                      |     Django 6.1 Backend      |
                      |  (REST APIs & CSRF Guards)  |
                      +--------------+--------------+
                                     |
         +---------------------------+---------------------------+
         |                                                       |
         v                                                       v
+------------------------+                             +--------------------+
|   Document Processor   |                             | Debugger Pipeline  |
|  PyMuPDF & TXT Parser  |                             | (Query Synthesis)  |
+-----------+------------+                             +---------+----------+
            |                                                    |
            v (700-1000 char chunks)                             |
+------------------------+                                       v
|  Local ChromaDB Index  | <============================ Semantic Retrieval
| (all-MiniLM-L6-v2 ONNX)|                                (Cosine Space)
+------------------------+                                       |
                                                                 v
                                                       +--------------------+
                                                       | Google Gemini SDK  |
                                                       | (google-genai)     |
                                                       +---------+----------+
                                                                 |
                                                                 v
                                                       Grounded JSON Diagnosis
                                                       (Diff, Causes, Citations)
```

---

## 🚀 Quickstart Guide (Windows PowerShell)

### 1. Prerequisites
- Python 3.12 (recommended) or Python 3.11+
- Git

### 2. Clone and Setup Environment
Open Windows PowerShell in the project directory:

```powershell
# Navigate to project
cd d:\SutraCode

# Activate existing virtual environment (or create with python -m venv .venv)
.\.venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` if not already present:

```powershell
Copy-Item .env.example .env
```

Ensure your `.env` contains:
```ini
SECRET_KEY=django-insecure-sutratrace-super-secret-key-2026-production-ready
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-flash-latest

FIREBASE_PROJECT_ID=sutracode-11188
FIREBASE_API_KEY=your-firebase-api-key-here
FIREBASE_AUTH_DOMAIN=sutracode-11188.firebaseapp.com
FIREBASE_STORAGE_BUCKET=sutracode-11188.firebasestorage.app
FIREBASE_MESSAGING_SENDER_ID=716936253835
FIREBASE_APP_ID=1:716936253835:web:57ecbea1cc85018c43df8e
FIREBASE_MEASUREMENT_ID=G-78Y7WS5W90

CHROMA_PERSIST_DIR=./data/chromadb
UPLOAD_DIR=./media/documents
MAX_UPLOAD_SIZE_MB=15
SIMILARITY_THRESHOLD=0.35
TOP_K_RESULTS=5
```

### 4. Run Migrations & System Check
```powershell
python manage.py makemigrations
python manage.py migrate
python manage.py check
```

### 5. Run Automated Tests
```powershell
python manage.py test debugger
```
*Expected: 8/8 tests pass in < 1 second.*

### 6. Start the Development Server
```powershell
python manage.py runserver 127.0.0.1:8000
```
Open your browser to: **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

---

## 🧪 Testing the Live Demo Workflow

1. Navigate to `http://127.0.0.1:8000/` and click **"Start Debugging"**.
2. In the **Documentation Vault** (left panel):
   - Click the button **`+ Requests Docs (PDF/TXT)`** to index the bundled official Python Requests documentation into ChromaDB.
   - Verify that `Official_Requests_Documentation.txt` appears with status `Indexed & Ready` and 6 chunks.
3. In the **Code Editor** (right panel):
   - Click the preset button **`Requests Timeout`** to load the known buggy snippet:
     ```python
     import requests

     def fetch_user_data(user_id):
         url = f"https://api.example.com/users/{user_id}"
         response = requests.get(url)  # Missing timeout!
         return response.json()
     ```
4. Click the primary button **"Analyze with Evidence"**.
5. Watch the 4-stage progression indicator:
   - *Stage 1:* Validating Code & Ingestion State
   - *Stage 2:* ChromaDB Vector Retrieval
   - *Stage 3:* Gemini Reasoning & Root Cause Isolation
   - *Stage 4:* Assembling Diff & Source Citations
6. Observe the results view:
   - **Severity:** HIGH
   - **Status:** Grounded with 5 Citations
   - **Corrected Code:** Minimal fix specifying `timeout=(3.05, 10)` and `response.raise_for_status()`.
   - **Unified Diff:** Shows exact lines added/removed.
   - **Evidence Drawer:** Shows verbatim quotes from `Official_Requests_Documentation.txt` (Page 1) highlighting that requests without timeout hang indefinitely.

---

## 🔒 Security Principles

- **Zero-Execution Sandbox:** User code is strictly parsed and tokenized as read-only text. At no point is `eval()`, `exec()`, or subshell invocation permitted.
- **Untrusted Content Demarcation:** System instructions explicitly order Gemini to ignore prompt-injection commands embedded inside user files or code comments.
- **Per-User Isolation:** ChromaDB vector queries filter on `where={"user_id": uid}`, guaranteeing that users cannot retrieve another developer's private documentation.
- **Clean Document Purging:** Deleting a document removes associated vectors from ChromaDB without altering other indexes.
