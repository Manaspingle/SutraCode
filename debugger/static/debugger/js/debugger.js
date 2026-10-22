/**
 * SutraTrace Streamlined Debugger Client
 */

const SAMPLE_BUGS = {
  requests_timeout: {
    language: 'python',
    code: `import requests\n\ndef fetch_user_data(user_id):\n    # Fetches user details from external service\n    url = f"https://api.example.com/users/{user_id}"\n    response = requests.get(url)\n    return response.json()`,
    problem: 'Under high network latency or firewall drops, background worker threads hang indefinitely, exhausting thread pool connections.',
    expected: 'Requests must specify explicit timeout (e.g. 5 seconds) and fail fast.'
  },
  mutable_defaults: {
    language: 'python',
    code: `def append_audit_log(event_name, audit_trail=[]):\n    # Records an event in the audit list\n    audit_trail.append(event_name)\n    return audit_trail\n\n# Test cases\nprint(append_audit_log("login"))\nprint(append_audit_log("logout"))`,
    problem: 'The second call returns ["login", "logout"] instead of ["logout"]. State persists across independent invocations.',
    expected: 'Each function call should start with a clean empty list.'
  }
};

document.addEventListener('DOMContentLoaded', () => {
  initDropzone();
  loadDocumentsList();
  initCharCounter();
});

function initCharCounter() {
  const codeArea = document.getElementById('submittedCode');
  const counter = document.getElementById('charCounter');
  if (codeArea && counter) {
    codeArea.addEventListener('input', () => {
      counter.textContent = `${codeArea.value.length} chars`;
    });
  }
}

function loadSampleBug(presetKey) {
  const bug = SAMPLE_BUGS[presetKey];
  if (!bug) return;

  const langSelect = document.getElementById('languageSelector');
  const codeArea = document.getElementById('submittedCode');
  const probArea = document.getElementById('problemDescription');
  const expArea = document.getElementById('expectedBehavior');
  const counter = document.getElementById('charCounter');

  if (langSelect) langSelect.value = bug.language;
  if (codeArea) {
    codeArea.value = bug.code;
    if (counter) counter.textContent = `${bug.code.length} chars`;
  }
  if (probArea) probArea.value = bug.problem;
  if (expArea) expArea.value = bug.expected;

  showToast(`Loaded ${presetKey.replace('_', ' ')} demo bug`, 'info');
}

function clearCodeEditor() {
  const codeArea = document.getElementById('submittedCode');
  if (codeArea) codeArea.value = '';
  const probArea = document.getElementById('problemDescription');
  if (probArea) probArea.value = '';
  const expArea = document.getElementById('expectedBehavior');
  if (expArea) expArea.value = '';
  const counter = document.getElementById('charCounter');
  if (counter) counter.textContent = '0 chars';
  const resContainer = document.getElementById('resultsContainer');
  if (resContainer) resContainer.classList.add('d-none');
}

// Dropzone & File Ingestion
function initDropzone() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('documentFileInput');
  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-over');
  });

  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  });
}

async function handleFileUpload(file) {
  const allowed = ['.pdf', '.txt'];
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
  if (!allowed.includes(ext)) {
    showToast(`Invalid file type (${ext}). Only PDF and TXT documents are supported.`, 'danger');
    return;
  }

  if (file.size > 15 * 1024 * 1024) {
    showToast("File exceeds 15MB limit.", 'danger');
    return;
  }

  const formData = new FormData();
  formData.append('document', file);

  const statusEl = document.getElementById('uploadProgressStatus');
  if (statusEl) {
    statusEl.innerHTML = `<span class="spinner-border spinner-border-sm text-warning me-1"></span> Vectorizing ${file.name}...`;
    statusEl.classList.remove('d-none');
  }

  try {
    const res = await sutraFetch('/api/upload-document/', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (data.success) {
      showToast(`Document "${data.document.filename}" indexed (${data.document.chunk_count} chunks)`, 'success');
      loadDocumentsList();
    } else {
      showToast(data.error || 'Ingestion failed.', 'warning');
    }
  } catch (err) {
    showToast("Upload error: " + err.message, 'danger');
  } finally {
    if (statusEl) statusEl.classList.add('d-none');
    const fileInput = document.getElementById('documentFileInput');
    if (fileInput) fileInput.value = '';
  }
}

async function loadSampleDoc(sampleType) {
  const statusEl = document.getElementById('uploadProgressStatus');
  if (statusEl) {
    statusEl.innerHTML = `<span class="spinner-border spinner-border-sm text-warning me-1"></span> Ingesting official ${sampleType} manual...`;
    statusEl.classList.remove('d-none');
  }

  const formData = new FormData();
  formData.append('sample_type', sampleType);

  try {
    const res = await sutraFetch('/api/load-sample-doc/', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, 'success');
      loadDocumentsList();
    } else {
      showToast(data.error, 'danger');
    }
  } catch (err) {
    showToast("Error loading sample doc: " + err.message, 'danger');
  } finally {
    if (statusEl) statusEl.classList.add('d-none');
  }
}

async function loadDocumentsList() {
  const listEl = document.getElementById('documentsList');
  const countBadge = document.getElementById('docCountBadge');
  if (!listEl) return;

  try {
    const res = await sutraFetch('/api/documents/');
    const data = await res.json();

    if (data.success) {
      const docs = data.documents;
      if (countBadge) countBadge.textContent = `${docs.length} Manual${docs.length === 1 ? '' : 's'}`;

      if (docs.length === 0) {
        listEl.innerHTML = `
          <div class="text-center py-4 text-muted">
            <i class="bi bi-file-earmark-code fs-3 d-block mb-1 opacity-40"></i>
            <span class="small">No documentation attached yet.</span>
          </div>
        `;
        return;
      }

      listEl.innerHTML = docs.map(doc => `
        <div class="doc-pill w-100 justify-content-between mb-2">
          <div class="d-flex align-items-center gap-2 text-truncate">
            <i class="bi bi-${doc.file_type === 'pdf' ? 'file-pdf text-danger' : 'file-text text-warning'}"></i>
            <span class="text-truncate fw-medium small" style="max-width: 220px;" title="${doc.filename}">${doc.filename}</span>
            <span class="badge bg-dark text-muted" style="font-size: 0.68rem;">${doc.chunk_count} chunks</span>
          </div>
          <button class="btn btn-sm text-secondary p-0 hover-danger" onclick="deleteDocument('${doc.id}')" title="Delete">
            <i class="bi bi-x-lg" style="font-size: 0.75rem;"></i>
          </button>
        </div>
      `).join('');
    }
  } catch (err) {
    console.error("Failed to load documents:", err);
  }
}

async function deleteDocument(docId) {
  try {
    const res = await sutraFetch(`/api/documents/${docId}/delete/`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast("Document removed.", 'info');
      loadDocumentsList();
    } else {
      showToast(data.error, 'danger');
    }
  } catch (err) {
    showToast("Delete failed: " + err.message, 'danger');
  }
}

// Analysis Execution
async function handleAnalyzeClick() {
  const code = document.getElementById('submittedCode').value.trim();
  const problem = document.getElementById('problemDescription').value.trim();

  if (!code) {
    showToast("Please enter the code to debug.", 'warning');
    return;
  }
  if (!problem) {
    showToast("Please describe the bug or unexpected behavior.", 'warning');
    return;
  }

  const payload = {
    language: document.getElementById('languageSelector').value,
    submitted_code: code,
    problem_description: problem,
    expected_behavior: document.getElementById('expectedBehavior')?.value.trim() || ''
  };

  const submitBtn = document.getElementById('analyzeBtn');
  const progressModalEl = document.getElementById('analysisProgressModal');
  const progressModal = progressModalEl ? bootstrap.Modal.getOrCreateInstance(progressModalEl) : null;

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Analyzing...';
  }

  if (progressModal) {
    resetProgressStages();
    progressModal.show();
  }

  updateStage(1, 'active');
  const s2 = setTimeout(() => { updateStage(1, 'completed'); updateStage(2, 'active'); }, 500);
  const s3 = setTimeout(() => { updateStage(2, 'completed'); updateStage(3, 'active'); }, 1400);

  try {
    const res = await sutraFetch('/api/analyze/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    clearTimeout(s2);
    clearTimeout(s3);
    updateStage(1, 'completed');
    updateStage(2, 'completed');
    updateStage(3, 'completed');
    updateStage(4, 'active');

    const data = await res.json();

    if (data.success) {
      setTimeout(() => {
        if (progressModal) progressModal.hide();
        renderMinimalistResults(payload.submitted_code, data.diagnosis);
      }, 400);
    } else {
      if (progressModal) progressModal.hide();
      showToast(`Error: ${data.error}`, 'danger');
    }
  } catch (err) {
    if (progressModal) progressModal.hide();
    showToast(`Request failed: ${err.message}`, 'danger');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>Analyze with Evidence</span> <i class="bi bi-arrow-right"></i>';
    }
  }
}

function updateStage(num, state) {
  const el = document.getElementById(`stage-${num}`);
  if (!el) return;
  el.className = `stage-item ${state}`;
  const icon = el.querySelector('i');
  if (icon) {
    if (state === 'active') icon.className = 'spinner-border spinner-border-sm text-warning me-2';
    else if (state === 'completed') icon.className = 'bi bi-check-circle-fill text-success me-2';
    else icon.className = 'bi bi-circle text-muted me-2';
  }
}

function resetProgressStages() {
  for (let i = 1; i <= 4; i++) {
    updateStage(i, 'pending');
  }
}

// Render Minimalist, High-Signal Results View
function renderMinimalistResults(originalCode, diagnosis) {
  const container = document.getElementById('resultsContainer');
  if (!container) return;

  container.classList.remove('d-none');

  // Severity Badge
  const sevEl = document.getElementById('resSeverity');
  if (sevEl) {
    sevEl.className = `badge badge-severity badge-${diagnosis.severity || 'medium'}`;
    sevEl.textContent = (diagnosis.severity || 'Medium').toUpperCase();
  }

  // Title / Summary
  document.getElementById('resSummaryTitle').textContent = diagnosis.summary || 'Root Cause Isolated';

  // Grounding Status Badge
  const badge = document.getElementById('resEvidenceBadge');
  if (badge) {
    if (diagnosis.is_evidence_backed) {
      badge.className = 'badge bg-success bg-opacity-20 text-success border border-success border-opacity-40 px-2 py-1';
      badge.innerHTML = `<i class="bi bi-check-circle me-1"></i> Grounded with ${diagnosis.evidence?.length || 0} Citations`;
    } else {
      badge.className = 'badge bg-warning bg-opacity-20 text-warning border border-warning border-opacity-40 px-2 py-1';
      badge.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i> Hypothesis (No Doc Match)`;
    }
  }

  // Root Cause Explanation (Consolidated, no fluff)
  const rootCauses = diagnosis.root_causes && diagnosis.root_causes.length > 0 
    ? diagnosis.root_causes.join(' ') 
    : diagnosis.change_explanation || 'Core defect identified in function parameters or state handling.';
  document.getElementById('resRootCauseText').textContent = rootCauses;

  // Corrected Code
  const codeBlock = document.getElementById('resCorrectedCode');
  if (codeBlock) {
    codeBlock.textContent = diagnosis.corrected_code || '// No correction needed';
    if (window.hljs) hljs.highlightElement(codeBlock);
  }

  // Diff Rendering
  renderUnifiedDiff(originalCode, diagnosis.corrected_code || '');

  // Citations / Evidence
  renderCitations(diagnosis.retrieved_passages || diagnosis.evidence || []);

  // Suggested Test
  const testBox = document.getElementById('resTestBox');
  const testContent = document.getElementById('resTestContent');
  if (diagnosis.suggested_tests && diagnosis.suggested_tests.length > 0) {
    testContent.textContent = diagnosis.suggested_tests[0];
    testBox.classList.remove('d-none');
  } else {
    testBox.classList.add('d-none');
  }

  // Scroll to results
  container.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderUnifiedDiff(original, corrected) {
  const diffContainer = document.getElementById('resDiffContainer');
  if (!diffContainer) return;

  const origLines = original.split('\n');
  const corrLines = corrected.split('\n');
  let html = '';
  const maxLines = Math.max(origLines.length, corrLines.length);

  for (let i = 0; i < maxLines; i++) {
    const o = origLines[i];
    const c = corrLines[i];

    if (o !== undefined && c !== undefined && o === c) {
      html += `<div class="diff-line text-muted"><span class="user-select-none opacity-40" style="width:25px;">${i+1}</span><span>${escapeHtml(o)}</span></div>`;
    } else {
      if (o !== undefined) {
        html += `<div class="diff-line removed"><span class="user-select-none" style="width:25px;">-</span><span>${escapeHtml(o)}</span></div>`;
      }
      if (c !== undefined) {
        html += `<div class="diff-line added"><span class="user-select-none" style="width:25px;">+</span><span>${escapeHtml(c)}</span></div>`;
      }
    }
  }

  diffContainer.innerHTML = html;
}

function renderCitations(passages) {
  const container = document.getElementById('resEvidenceList');
  if (!container) return;

  if (!passages || passages.length === 0) {
    container.innerHTML = `
      <div class="small text-muted font-mono p-2 rounded bg-black bg-opacity-30">
        Notice: No documentation matched this query. Diagnosis is a code-based hypothesis.
      </div>
    `;
    return;
  }

  // Show top 2 most relevant citations to avoid visual overload
  const topCitations = passages.slice(0, 2);
  container.innerHTML = topCitations.map((p, idx) => `
    <div class="citation-box">
      <div class="d-flex justify-content-between align-items-center mb-1">
        <span class="small fw-semibold text-warning">
          <i class="bi bi-file-text me-1"></i> ${escapeHtml(p.filename || 'Documentation')} ${p.page_number ? `(Page ${p.page_number})` : ''}
        </span>
        ${p.relevance_score ? `<span class="badge bg-dark text-muted" style="font-size: 0.68rem;">${Math.round(p.relevance_score * 100)}% match</span>` : ''}
      </div>
      <div class="citation-text">${escapeHtml((p.content || p.citation_excerpt || '').substring(0, 320))}...</div>
    </div>
  `).join('');
}

function copyCorrectedCode() {
  const code = document.getElementById('resCorrectedCode')?.textContent;
  if (!code) return;
  navigator.clipboard.writeText(code).then(() => {
    showToast("Corrected code copied!", 'success');
  }).catch(() => {
    showToast("Copy failed.", 'warning');
  });
}

function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function showToast(message, type = 'info') {
  const toastContainer = document.getElementById('toastContainer');
  if (!toastContainer) return;

  const toastEl = document.createElement('div');
  toastEl.className = `toast align-items-center text-bg-${type === 'danger' ? 'danger' : type === 'warning' ? 'warning' : type === 'success' ? 'success' : 'dark'} border-0 mb-2`;
  toastEl.setAttribute('role', 'alert');
  toastEl.setAttribute('aria-live', 'assertive');
  toastEl.setAttribute('aria-atomic', 'true');
  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body small fw-medium text-white">${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>
  `;

  toastContainer.appendChild(toastEl);
  const bsToast = new bootstrap.Toast(toastEl, { delay: 3500 });
  bsToast.show();
  toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}
