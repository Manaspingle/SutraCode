/**
 * SutraTrace Debugger Workspace Logic
 */

// Sample Bug Presets
const SAMPLE_BUGS = {
  requests_timeout: {
    language: 'python',
    code: `import requests\n\ndef fetch_user_data(user_id):\n    # Fetches user details from external service\n    url = f"https://api.example.com/users/{user_id}"\n    response = requests.get(url)\n    return response.json()`,
    problem: 'Under high network latency or firewall drops, background worker threads hang indefinitely, exhausting thread pool connections.',
    error: 'Connection hanging forever without terminating or raising socket error.',
    expected: 'HTTP requests must specify explicit connection and read timeouts (e.g. 5 seconds) and handle exceptions safely.',
    question: 'Why does requests.get hang forever if no timeout is passed?'
  },
  mutable_defaults: {
    language: 'python',
    code: `def append_audit_log(event_name, audit_trail=[]):\n    # Records an event in the audit list\n    audit_trail.append(event_name)\n    return audit_trail\n\n# Test cases\nprint(append_audit_log("login"))\nprint(append_audit_log("logout"))`,
    problem: 'The second call to append_audit_log returns ["login", "logout"] instead of just ["logout"]. State is unintentionally preserved across calls.',
    error: 'Unexpected state accumulation across independent invocations.',
    expected: 'Each call without an explicit audit_trail parameter should start with a clean, empty list.',
    question: 'How should mutable default arguments be safely specified in Python?'
  },
  js_async_foreach: {
    language: 'javascript',
    code: `async function fetchAllUserData(userIds) {\n    const results = [];\n    userIds.forEach(async (id) => {\n        const data = await fetchUser(id);\n        results.push(data);\n    });\n    return results;\n}`,
    problem: 'fetchAllUserData returns an empty array [] immediately before any of the async API calls complete.',
    error: 'Results array is empty on return.',
    expected: 'All user promises should resolve concurrently before the function returns the populated results array.',
    question: 'Why does Array.prototype.forEach fail with async/await?'
  }
};

document.addEventListener('DOMContentLoaded', () => {
  initDropzone();
  loadDocumentsList();
  initFormHandlers();
});

// Load Presets
function loadSampleBug(presetKey) {
  const bug = SAMPLE_BUGS[presetKey];
  if (!bug) return;

  const langSelect = document.getElementById('languageSelector');
  const codeArea = document.getElementById('submittedCode');
  const probArea = document.getElementById('problemDescription');
  const errArea = document.getElementById('errorMessage');
  const expArea = document.getElementById('expectedBehavior');
  const qArea = document.getElementById('userQuestion');

  if (langSelect) langSelect.value = bug.language;
  if (codeArea) codeArea.value = bug.code;
  if (probArea) probArea.value = bug.problem;
  if (errArea) errArea.value = bug.error;
  if (expArea) expArea.value = bug.expected;
  if (qArea) qArea.value = bug.question;

  showToast(`Loaded sample bug: ${presetKey.replace('_', ' ')}`, 'info');
}

function clearCodeEditor() {
  document.getElementById('submittedCode').value = '';
  document.getElementById('problemDescription').value = '';
  document.getElementById('errorMessage').value = '';
  document.getElementById('expectedBehavior').value = '';
  document.getElementById('userQuestion').value = '';
  document.getElementById('resultsContainer').classList.add('d-none');
}

// Dropzone & Document Upload
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
    showToast(`Invalid file type (${ext}). Only PDF and TXT documents are allowed.`, 'danger');
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
    statusEl.innerHTML = `<span class="spinner-border spinner-border-sm text-info me-1"></span> Ingesting and vectorizing ${file.name}...`;
    statusEl.classList.remove('d-none');
  }

  try {
    const res = await sutraFetch('/api/upload-document/', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (data.success) {
      showToast(`Document "${data.document.filename}" indexed into ChromaDB (${data.document.chunk_count} chunks)!`, 'success');
      loadDocumentsList();
    } else {
      showToast(`Ingestion notice: ${data.error}`, 'warning');
    }
  } catch (err) {
    showToast("Upload failed: " + err.message, 'danger');
  } finally {
    if (statusEl) statusEl.classList.add('d-none');
    const fileInput = document.getElementById('documentFileInput');
    if (fileInput) fileInput.value = '';
  }
}

async function loadSampleDoc(sampleType) {
  const statusEl = document.getElementById('uploadProgressStatus');
  if (statusEl) {
    statusEl.innerHTML = `<span class="spinner-border spinner-border-sm text-info me-1"></span> Indexing official ${sampleType} documentation...`;
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
    showToast("Failed to load sample doc: " + err.message, 'danger');
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
      if (countBadge) countBadge.textContent = `${docs.length} Active`;

      if (docs.length === 0) {
        listEl.innerHTML = `
          <div class="text-center py-4 text-muted">
            <i class="bi bi-file-earmark-text fs-2 d-block mb-2 opacity-50"></i>
            <p class="small mb-1">No documentation uploaded yet.</p>
            <p class="small text-secondary">Upload a PDF or TXT to ground debugging in verified evidence.</p>
          </div>
        `;
        return;
      }

      listEl.innerHTML = docs.map(doc => `
        <div class="doc-item" id="doc-${doc.id}">
          <div class="d-flex align-items-center gap-2 overflow-hidden">
            <i class="bi bi-${doc.file_type === 'pdf' ? 'file-earmark-pdf text-danger' : 'file-earmark-text text-info'} fs-5"></i>
            <div class="text-truncate">
              <div class="fw-semibold text-truncate small text-light" title="${doc.filename}">${doc.filename}</div>
              <div class="text-muted" style="font-size: 0.72rem;">
                ${doc.file_size} • ${doc.chunk_count} chunks ${doc.page_count > 1 ? `• ${doc.page_count} pages` : ''}
              </div>
            </div>
          </div>
          <div class="d-flex align-items-center gap-2">
            <span class="doc-badge">${doc.status}</span>
            <button class="btn btn-sm text-secondary p-1 hover-danger" onclick="deleteDocument('${doc.id}')" title="Delete Document">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        </div>
      `).join('');
    }
  } catch (err) {
    console.error("Failed to load documents:", err);
  }
}

async function deleteDocument(docId) {
  if (!confirm("Remove this document and all its indexed vector chunks?")) return;

  try {
    const res = await sutraFetch(`/api/documents/${docId}/delete/`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast("Document removed from index.", 'info');
      loadDocumentsList();
    } else {
      showToast(data.error, 'danger');
    }
  } catch (err) {
    showToast("Delete failed: " + err.message, 'danger');
  }
}

// Form Handlers & Analysis
function initFormHandlers() {
  const form = document.getElementById('debugAnalysisForm');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const code = document.getElementById('submittedCode').value.trim();
    const problem = document.getElementById('problemDescription').value.trim();
    if (!code) {
      showToast("Please provide the code snippet to analyze.", 'warning');
      return;
    }
    if (!problem) {
      showToast("Please describe the observed error or behavior.", 'warning');
      return;
    }

    const payload = {
      language: document.getElementById('languageSelector').value,
      submitted_code: code,
      problem_description: problem,
      error_message: document.getElementById('errorMessage').value.trim(),
      expected_behavior: document.getElementById('expectedBehavior').value.trim(),
      user_question: document.getElementById('userQuestion').value.trim(),
    };

    startAnalysis(payload);
  });
}

async function startAnalysis(payload) {
  const submitBtn = document.getElementById('analyzeBtn');
  const progressModalEl = document.getElementById('analysisProgressModal');
  const progressModal = progressModalEl ? bootstrap.Modal.getOrCreateInstance(progressModalEl) : null;

  // Prevent duplicate submissions
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span> Analyzing...`;
  }

  // Show progress modal
  if (progressModal) {
    resetProgressStages();
    progressModal.show();
  }

  // Simulated stage transitions for clear transparency
  updateStage(1, 'active');
  const s2Timer = setTimeout(() => { updateStage(1, 'completed'); updateStage(2, 'active'); }, 700);
  const s3Timer = setTimeout(() => { updateStage(2, 'completed'); updateStage(3, 'active'); }, 1800);

  try {
    const res = await sutraFetch('/api/analyze/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    clearTimeout(s2Timer);
    clearTimeout(s3Timer);
    updateStage(1, 'completed');
    updateStage(2, 'completed');
    updateStage(3, 'completed');
    updateStage(4, 'active');

    const data = await res.json();

    if (data.success) {
      setTimeout(() => {
        if (progressModal) progressModal.hide();
        renderAnalysisResults(payload.submitted_code, data.diagnosis);
      }, 500);
    } else {
      if (progressModal) progressModal.hide();
      showToast(`Analysis Error: ${data.error}`, 'danger');
    }
  } catch (err) {
    if (progressModal) progressModal.hide();
    showToast(`Request failed: ${err.message}`, 'danger');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<i class="bi bi-cpu fs-5"></i> Analyze with Evidence`;
    }
  }
}

function updateStage(num, state) {
  const el = document.getElementById(`stage-${num}`);
  if (!el) return;
  el.className = `stage-item ${state}`;
  const icon = el.querySelector('i');
  if (icon) {
    if (state === 'active') icon.className = 'spinner-border spinner-border-sm text-info me-2';
    else if (state === 'completed') icon.className = 'bi bi-check-circle-fill text-success me-2';
    else icon.className = 'bi bi-circle text-muted me-2';
  }
}

function resetProgressStages() {
  for (let i = 1; i <= 4; i++) {
    updateStage(i, 'pending');
  }
}

// Render Results View
function renderAnalysisResults(originalCode, diagnosis) {
  const container = document.getElementById('resultsContainer');
  if (!container) return;

  container.classList.remove('d-none');

  // Severity & Evidence Badges
  const severityEl = document.getElementById('resSeverity');
  if (severityEl) {
    severityEl.className = `badge badge-severity badge-${diagnosis.severity || 'medium'}`;
    severityEl.textContent = (diagnosis.severity || 'Medium').toUpperCase();
  }

  const evidenceStatusEl = document.getElementById('resEvidenceStatus');
  if (evidenceStatusEl) {
    if (diagnosis.is_evidence_backed) {
      evidenceStatusEl.className = 'badge bg-success bg-opacity-25 text-success border border-success border-opacity-50 px-3 py-2 rounded-pill';
      evidenceStatusEl.innerHTML = `<i class="bi bi-shield-check me-1"></i> Grounded with ${diagnosis.evidence?.length || 0} Citations`;
    } else {
      evidenceStatusEl.className = 'badge bg-warning bg-opacity-25 text-warning border border-warning border-opacity-50 px-3 py-2 rounded-pill';
      evidenceStatusEl.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i> Unverified Hypothesis (No Doc Match)`;
    }
  }

  // Summary
  document.getElementById('resSummary').textContent = diagnosis.summary || 'Analysis complete.';

  // Code Observations
  const obsList = document.getElementById('resObservations');
  if (obsList) {
    obsList.innerHTML = (diagnosis.code_observations || []).map(obs => `
      <li class="mb-1 text-light"><i class="bi bi-arrow-right text-info me-2"></i>${escapeHtml(obs)}</li>
    `).join('') || '<li class="text-muted">No specific code anomalies identified.</li>';
  }

  // Root Causes
  const rootCausesList = document.getElementById('resRootCauses');
  if (rootCausesList) {
    rootCausesList.innerHTML = (diagnosis.root_causes || []).map(rc => `
      <div class="p-3 mb-2 rounded bg-secondary bg-opacity-10 border border-secondary border-opacity-25">
        <div class="fw-semibold text-warning mb-1"><i class="bi bi-exclamation-diamond me-2"></i>Root Cause</div>
        <div class="text-light small">${escapeHtml(rc)}</div>
      </div>
    `).join('') || '<div class="text-muted">No root cause identified.</div>';
  }

  // Corrected Code
  const codeBlock = document.getElementById('resCorrectedCode');
  if (codeBlock) {
    codeBlock.textContent = diagnosis.corrected_code || '// No code correction needed';
    if (window.hljs) hljs.highlightElement(codeBlock);
  }

  // Diff Rendering
  renderUnifiedDiff(originalCode, diagnosis.corrected_code || '');

  // Explanation
  document.getElementById('resExplanation').textContent = diagnosis.change_explanation || 'No change explanation provided.';

  // Suggested Tests
  const testsList = document.getElementById('resTests');
  if (testsList) {
    testsList.innerHTML = (diagnosis.suggested_tests || []).map(t => `
      <div class="font-mono small p-2 mb-1 bg-black bg-opacity-50 rounded border border-dark text-info">
        <i class="bi bi-check2-circle text-success me-2"></i>${escapeHtml(t)}
      </div>
    `).join('') || '<div class="text-muted small">Run manual unit tests in your local environment.</div>';
  }

  // Evidence Drawer
  renderEvidenceDrawer(diagnosis.retrieved_passages || diagnosis.evidence || []);

  // Limitations
  document.getElementById('resLimitations').textContent = diagnosis.limitations || 'None declared.';

  // Scroll to results
  container.scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Sync to Firestore if authenticated
  if (window.currentUser && window.db && diagnosis.analysis_id) {
    try {
      window.db.collection('users').doc(window.currentUser.uid)
        .collection('analyses').doc(diagnosis.analysis_id)
        .set({
          id: diagnosis.analysis_id,
          summary: diagnosis.summary,
          severity: diagnosis.severity,
          is_evidence_backed: diagnosis.is_evidence_backed,
          created_at: firebase.firestore.FieldValue.serverTimestamp()
        }, { merge: true });
    } catch (e) {
      console.log("Firestore analysis record notice:", e.message);
    }
  }
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
      html += `<div class="diff-line text-muted"><span class="user-select-none opacity-50" style="width:30px;">${i+1}</span> <span>${escapeHtml(o)}</span></div>`;
    } else {
      if (o !== undefined) {
        html += `<div class="diff-line removed"><span class="user-select-none" style="width:30px;">-</span> <span>${escapeHtml(o)}</span></div>`;
      }
      if (c !== undefined) {
        html += `<div class="diff-line added"><span class="user-select-none" style="width:30px;">+</span> <span>${escapeHtml(c)}</span></div>`;
      }
    }
  }

  diffContainer.innerHTML = html;
}

function renderEvidenceDrawer(passages) {
  const container = document.getElementById('resEvidenceList');
  if (!container) return;

  if (!passages || passages.length === 0) {
    container.innerHTML = `
      <div class="alert alert-dark border-secondary small text-muted">
        <i class="bi bi-info-circle me-1"></i> No matching passages were retrieved from the current documentation collection.
      </div>
    `;
    return;
  }

  container.innerHTML = passages.map((p, idx) => `
    <div class="evidence-card">
      <div class="d-flex justify-content-between align-items-center mb-1">
        <span class="fw-semibold text-info small">
          <i class="bi bi-file-earmark-check me-1"></i> [Citation #${idx+1}] ${escapeHtml(p.filename || 'Documentation')}
          ${p.page_number ? `<span class="badge bg-secondary ms-1">Page ${p.page_number}</span>` : ''}
        </span>
        ${p.relevance_score ? `<span class="badge bg-dark text-secondary border border-secondary">${Math.round(p.relevance_score * 100)}% Match</span>` : ''}
      </div>
      ${p.relevance_explanation ? `<p class="small text-secondary mb-1"><em>${escapeHtml(p.relevance_explanation)}</em></p>` : ''}
      <div class="evidence-quote">${escapeHtml(p.content || p.citation_excerpt || '')}</div>
    </div>
  `).join('');
}

function copyCorrectedCode() {
  const code = document.getElementById('resCorrectedCode')?.textContent;
  if (!code) return;
  navigator.clipboard.writeText(code).then(() => {
    showToast("Corrected code copied to clipboard!", 'success');
  }).catch(() => {
    showToast("Copy failed, please copy manually.", 'warning');
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

  const toastId = 'toast-' + Math.random().toString(36).substr(2, 9);
  const toastEl = document.createElement('div');
  toastEl.className = `toast align-items-center text-bg-${type === 'danger' ? 'danger' : type === 'warning' ? 'warning' : type === 'success' ? 'success' : 'dark'} border-0 mb-2`;
  toastEl.id = toastId;
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
  const bsToast = new bootstrap.Toast(toastEl, { delay: 4000 });
  bsToast.show();
  toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}
