/**
 * ScholarHub — Global Configuration & Utilities
 * File ini di-include oleh semua halaman frontend.
 */

// === LOCALHOST DEV MODE ===
// HAPUS SAAT DEPLOY KE KUBERNETES: Ganti dengan URL service Kubernetes
const API_BASE = 'http://127.0.0.1:8000/api';
// === END LOCALHOST DEV MODE ===

// ==========================================
// TOKEN MANAGEMENT
// ==========================================

function getToken() {
    return localStorage.getItem('access_token');
}

function getRefreshToken() {
    return localStorage.getItem('refresh_token');
}

function getRole() {
    return localStorage.getItem('user_role');
}

function isLoggedIn() {
    const token = getToken();
    return token && token !== 'undefined' && token !== 'null';
}

function isAdmin() {
    return getRole() === 'ADMIN';
}

function saveAuthData(data) {
    localStorage.setItem('access_token', data.access);
    if (data.refresh) localStorage.setItem('refresh_token', data.refresh);
    if (data.role) localStorage.setItem('user_role', data.role);
    if (data.username) localStorage.setItem('username', data.username);
}

function logout() {
    const role = localStorage.getItem('user_role');
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('username');
    if (role === 'ADMIN') {
        window.location.href = 'admin-login.html';
    } else {
        window.location.href = 'index.html';
    }
}

function getUsername() {
    return localStorage.getItem('username') || '';
}

/**
 * Update navbar secara dinamis berdasarkan status login.
 * Panggil di DOMContentLoaded pada halaman yang butuh dynamic navbar.
 */
function updateNavbar() {
    const navActions = document.getElementById('navActions');
    if (!navActions) return;

    if (isLoggedIn()) {
        const dashLink = isAdmin() ? 'admin-dashboard.html' : 'dashboard.html';
        navActions.innerHTML = `
            <li class="nav-item"><a class="nav-link text-white" href="${dashLink}">Scholarships</a></li>
            <li class="nav-item"><a class="nav-link text-white" href="bookmarks.html">Bookmarks</a></li>
            <li class="nav-item ms-lg-4 border-start border-light ps-lg-3"><a class="nav-link text-warning fw-bold" href="promote.html"><i class="bi bi-megaphone-fill me-1"></i> For Providers: Promote</a></li>
            <li class="nav-item"><a class="nav-link text-white" href="my-promotions.html">My Promotions</a></li>
            <li class="nav-item ms-3">
                <div class="d-flex align-items-center gap-2">
                    <span class="text-white small opacity-75"><i class="bi bi-person-circle"></i> ${getUsername()}</span>
                    <button onclick="logout()" class="btn btn-outline-light btn-sm rounded-pill px-3">Logout</button>
                </div>
            </li>`;
    } else {
        navActions.innerHTML = `
            <li class="nav-item"><a class="nav-link text-white" href="dashboard.html">Scholarships</a></li>
            <li class="nav-item ms-lg-4 border-start border-light ps-lg-3"><a class="nav-link text-warning fw-bold" href="promote.html"><i class="bi bi-megaphone-fill me-1"></i> For Providers: Promote</a></li>
            <li class="nav-item"><a class="nav-link text-white" href="#faq">FAQ</a></li>
            <li class="nav-item ms-3"><a href="login.html" class="btn btn-outline-light rounded-pill px-4">Sign In</a></li>`;
    }
}

// ==========================================
// API FETCH HELPER
// ==========================================

async function apiFetch(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = options.headers || {};

    // Tambahkan Authorization header jika user login
    if (isLoggedIn() && !headers['Authorization']) {
        headers['Authorization'] = `Bearer ${getToken()}`;
    }

    // Tambahkan Content-Type jika bukan FormData
    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }

    try {
        const response = await fetch(url, { ...options, headers });

        // Token expired → coba refresh
        if (response.status === 401 && isLoggedIn()) {
            const refreshed = await tryRefreshToken();
            if (refreshed) {
                headers['Authorization'] = `Bearer ${getToken()}`;
                return fetch(url, { ...options, headers });
            } else {
                logout();
                return response;
            }
        }

        return response;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

async function tryRefreshToken() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    try {
        const response = await fetch(`${API_BASE}/auth/token/refresh/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh: refreshToken }),
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('access_token', data.access);
            return true;
        }
    } catch (e) {
        console.error('Token refresh failed:', e);
    }
    return false;
}

// ==========================================
// GUARD — Proteksi halaman
// ==========================================

function requireAuth() {
    if (!isLoggedIn()) {
        window.location.href = 'login.html';
        return false;
    }
    return true;
}

function requireAdmin() {
    if (!isLoggedIn() || !isAdmin()) {
        window.location.href = 'admin-login.html';
        return false;
    }
    return true;
}

// ==========================================
// UI HELPERS
// ==========================================

function showToast(message, type = 'success') {
    // Hapus toast lama jika ada
    const old = document.getElementById('toast-notification');
    if (old) old.remove();

    const colors = {
        success: '#059669',
        error: '#dc2626',
        warning: '#d97706',
        info: '#2563eb',
    };

    const toast = document.createElement('div');
    toast.id = 'toast-notification';
    toast.style.cssText = `
        position: fixed; top: 24px; right: 24px; z-index: 9999;
        padding: 16px 24px; border-radius: 12px; color: white;
        font-family: 'Poppins', sans-serif; font-size: 14px; font-weight: 500;
        background: ${colors[type] || colors.info};
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        transform: translateX(120%); transition: transform 0.3s ease;
        max-width: 400px;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
        toast.style.transform = 'translateX(0)';
    });

    // Auto-dismiss
    setTimeout(() => {
        toast.style.transform = 'translateX(120%)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    return d.toLocaleDateString('id-ID', { day: 'numeric', month: 'long', year: 'numeric' });
}

function truncateText(text, maxLength = 100) {
    if (!text || text.length <= maxLength) return text || '';
    return text.substring(0, maxLength) + '...';
}

function getCoverageLabel(type) {
    const labels = {
        'FULL_FUNDED': 'Full Funded',
        'PARTIAL_FUNDED': 'Partial Funded',
        'ALLOWANCE_ONLY': 'Allowance Only',
    };
    return labels[type] || type;
}

function getCoverageBadgeClass(type) {
    const classes = {
        'FULL_FUNDED': 'bg-success',
        'PARTIAL_FUNDED': 'bg-warning text-dark',
        'ALLOWANCE_ONLY': 'bg-info',
    };
    return classes[type] || 'bg-secondary';
}

function getStatusBadgeClass(status) {
    const classes = {
        'PUBLISHED': 'bg-success',
        'PENDING': 'bg-warning text-dark',
        'REJECTED': 'bg-danger',
        'DRAFT': 'bg-secondary',
    };
    return classes[status] || 'bg-secondary';
}
