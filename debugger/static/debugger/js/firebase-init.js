/**
 * SutraTrace Firebase Authentication & Session Syncing
 */

window.currentUser = null;
window.currentUserToken = null;

if (window.FIREBASE_CONFIG && typeof firebase !== 'undefined') {
  try {
    firebase.initializeApp(window.FIREBASE_CONFIG);
    window.auth = firebase.auth();
    window.db = firebase.firestore();
    console.log("SutraTrace: Firebase initialized.");
  } catch (e) {
    console.warn("SutraTrace: Firebase init note:", e.message);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (!window.auth) return;

  window.auth.onAuthStateChanged(async (user) => {
    window.currentUser = user;
    const authChip = document.getElementById('authStatusChip');
    const authBtn = document.getElementById('navbarAuthBtn');

    if (user) {
      try {
        window.currentUserToken = await user.getIdToken();
        // Background session sync to keep Django backend session authenticated
        fetch('/api/auth/session-login/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken') || ''
          },
          body: JSON.stringify({ id_token: window.currentUserToken })
        }).catch(err => console.debug("Session sync notice:", err));
      } catch (err) {
        console.error("Failed to get ID token:", err);
      }

      if (authChip) {
        const photo = user.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(user.displayName || user.email || 'Dev')}&background=F59E0B&color=08090C`;
        authChip.innerHTML = `
          <div class="user-chip">
            <img src="${photo}" alt="Avatar" class="user-avatar" />
            <span class="d-none d-sm-inline fw-semibold">${user.displayName || user.email.split('@')[0]}</span>
            <button class="btn btn-sm text-secondary p-0 ms-1 hover-amber" onclick="handleSignOut()" title="Sign Out">
              <i class="bi bi-box-arrow-right"></i>
            </button>
          </div>
        `;
        authChip.classList.remove('d-none');
      }
      if (authBtn) authBtn.classList.add('d-none');

      // Sync Firestore profile
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
          console.debug("Firestore sync:", e.message);
        }
      }

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

async function handleSignOut() {
  if (!window.auth) return;
  try {
    await window.auth.signOut();
    await fetch('/api/auth/session-logout/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') || '' }
    });
    window.location.href = '/';
  } catch (err) {
    console.error("Sign out error:", err);
  }
}

function openAuthModal() {
  window.location.href = '/login/';
}

async function sutraFetch(url, options = {}) {
  options.headers = options.headers || {};

  if (window.currentUser) {
    try {
      const token = await window.currentUser.getIdToken();
      options.headers['Authorization'] = `Bearer ${token}`;
    } catch (e) {
      console.warn("Could not retrieve fresh ID token", e);
    }
  }

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
