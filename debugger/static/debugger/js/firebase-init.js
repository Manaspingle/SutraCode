/**
 * SutraTrace Firebase Authentication & Firestore Integration
 */

// Global state
window.currentUser = null;
window.currentUserToken = null;

// Initialize Firebase
if (window.FIREBASE_CONFIG && typeof firebase !== 'undefined') {
  try {
    firebase.initializeApp(window.FIREBASE_CONFIG);
    window.auth = firebase.auth();
    window.db = firebase.firestore();
    console.log("SutraTrace: Firebase initialized successfully.");
  } catch (e) {
    console.warn("SutraTrace: Firebase init note:", e.message);
  }
} else {
  console.warn("SutraTrace: Firebase config or SDK not available.");
}

// Auth State Observer
document.addEventListener('DOMContentLoaded', () => {
  if (!window.auth) return;

  window.auth.onAuthStateChanged(async (user) => {
    window.currentUser = user;
    const authChip = document.getElementById('authStatusChip');
    const authBtn = document.getElementById('navbarAuthBtn');

    if (user) {
      try {
        window.currentUserToken = await user.getIdToken();
      } catch (err) {
        console.error("Failed to get ID token:", err);
      }

      // Update navbar chip
      if (authChip) {
        const photo = user.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(user.displayName || user.email || 'Dev')}&background=00D2FF&color=08090C`;
        authChip.innerHTML = `
          <div class="user-chip">
            <img src="${photo}" alt="Avatar" class="user-avatar" />
            <span class="d-none d-sm-inline fw-semibold">${user.displayName || user.email.split('@')[0]}</span>
            <button class="btn btn-sm text-secondary p-0 ms-1" onclick="handleSignOut()" title="Sign Out">
              <i class="bi bi-box-arrow-right"></i>
            </button>
          </div>
        `;
        authChip.classList.remove('d-none');
      }
      if (authBtn) authBtn.classList.add('d-none');

      // Sync user profile to Firestore
      if (window.db) {
        try {
          await window.db.collection('users').doc(user.uid).set({
            uid: user.uid,
            email: user.email,
            displayName: user.displayName || user.email.split('@')[0],
            photoURL: user.photoURL || '',
            lastLogin: firebase.firestore.FieldValue.serverTimestamp(),
          }, { merge: true });
        } catch (e) {
          console.log("Firestore sync notice (security rules or offline):", e.message);
        }
      }

      // Refresh documents list for this authenticated user if in workspace
      if (typeof loadDocumentsList === 'function') {
        loadDocumentsList();
      }

    } else {
      window.currentUserToken = null;
      if (authChip) authChip.classList.add('d-none');
      if (authBtn) authBtn.classList.remove('d-none');
    }
  });
});

// Auth Handlers
async function handleGoogleSignIn() {
  if (!window.auth) return;
  const provider = new firebase.auth.GoogleAuthProvider();
  try {
    await window.auth.signInWithPopup(provider);
    closeAuthModal();
  } catch (err) {
    alert("Google Sign-In failed: " + err.message);
  }
}

async function handleEmailSignIn(e) {
  if (e) e.preventDefault();
  if (!window.auth) return;
  const email = document.getElementById('authEmail')?.value;
  const password = document.getElementById('authPassword')?.value;
  if (!email || !password) return;

  try {
    await window.auth.signInWithEmailAndPassword(email, password);
    closeAuthModal();
  } catch (err) {
    if (err.code === 'auth/user-not-found') {
      // Auto-register convenience
      try {
        await window.auth.createUserWithEmailAndPassword(email, password);
        closeAuthModal();
      } catch (regErr) {
        alert("Registration failed: " + regErr.message);
      }
    } else {
      alert("Sign-In failed: " + err.message);
    }
  }
}

async function handleSignOut() {
  if (!window.auth) return;
  try {
    await window.auth.signOut();
    window.location.reload();
  } catch (err) {
    console.error("Sign out error:", err);
  }
}

function openAuthModal() {
  const modalEl = document.getElementById('authModal');
  if (modalEl && window.bootstrap) {
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

function closeAuthModal() {
  const modalEl = document.getElementById('authModal');
  if (modalEl && window.bootstrap) {
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
  }
}

/**
 * Universal fetch wrapper that attaches Firebase ID token and CSRF header.
 */
async function sutraFetch(url, options = {}) {
  options.headers = options.headers || {};

  // Attach Firebase ID token if authenticated
  if (window.currentUser) {
    try {
      const token = await window.currentUser.getIdToken();
      options.headers['Authorization'] = `Bearer ${token}`;
    } catch (e) {
      console.warn("Could not retrieve fresh ID token", e);
    }
  }

  // Attach Django CSRF Token
  const csrfToken = getCookie('csrftoken');
  if (csrfToken && !options.headers['X-CSRFToken']) {
    options.headers['X-CSRFToken'] = csrfToken;
  }

  return fetch(url, options);
}

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
