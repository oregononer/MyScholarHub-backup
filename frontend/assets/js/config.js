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

async function logout() {
    const role         = localStorage.getItem('user_role');
    const refreshToken = localStorage.getItem('refresh_token');
    const accessToken  = localStorage.getItem('access_token');

    // --- Server-side token blacklist ---
    // Panggil endpoint logout backend agar refresh token diinvalidasi di server.
    // Ini penting: walau access token masih berlaku 60 menit, refresh token
    // yang di-blacklist tidak bisa dipakai untuk mendapat access token baru.
    if (refreshToken && accessToken) {
        try {
            await fetch(`${API_BASE}/auth/logout/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`,
                },
                body: JSON.stringify({ refresh: refreshToken }),
            });
        } catch (e) {
            // Jika gagal (misal offline), tetap lanjutkan logout lokal
            console.warn('[Logout] Server-side blacklist gagal, melanjutkan logout lokal.', e);
        }
    }

    // --- Hapus semua data dari localStorage ---
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('username');

    // --- Redirect ke halaman yang sesuai ---
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

        // Bangun navbar dengan DOM API — TIDAK pakai innerHTML untuk data user
        // ini mencegah XSS walau username mengandung karakter berbahaya
        navActions.innerHTML = `
            <li class="nav-item"><a class="nav-link text-white" href="${dashLink}">Scholarships</a></li>
            <li class="nav-item"><a class="nav-link text-white" href="bookmarks.html">Bookmarks</a></li>
            <li class="nav-item ms-lg-4 border-start border-light ps-lg-3"><a class="nav-link text-warning fw-bold" href="promote.html"><i class="bi bi-megaphone-fill me-1"></i> For Providers: Promote</a></li>
            <li class="nav-item"><a class="nav-link text-white" href="my-promotions.html">My Promotions</a></li>
            <li class="nav-item ms-3">
                <div class="d-flex align-items-center gap-2">
                    <span class="text-white small opacity-75"><i class="bi bi-person-circle"></i> <span id="navbar-username-text"></span></span>
                    <button onclick="logout()" class="btn btn-outline-light btn-sm rounded-pill px-3">Logout</button>
                </div>
            </li>`;

        // Set username dengan textContent — XSS-safe, tidak di-parse sebagai HTML
        const usernameEl = document.getElementById('navbar-username-text');
        if (usernameEl) usernameEl.textContent = getUsername();
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

// ==========================================
// i18n — LANGUAGE SWITCHER (EN ↔ ID)
// Disimpan di localStorage('sh_lang'), default 'id'
// Gunakan attribute data-i18n="key" pada elemen HTML.
// ==========================================

const I18N = {
    en: {
        'nav.dashboard':    'Dashboard',
        'nav.moderation':   'Moderation',
        'nav.users':        'Users',
        'nav.auditlog':     'Audit Log',
        'nav.backportal':   'Back to Portal',
        'nav.logout':       'Logout',
        'topbar.search':    'Search...',
        'dash.title':           'Dashboard',
        'dash.published':       'Published Scholarships',
        'dash.pending':         'Pending Review',
        'dash.applicants':      'Applicants',
        'dash.anomalies':       'Security Anomalies',
        'dash.pending_mod':     'Pending Moderation',
        'dash.recent_activity': 'Recent Activity',
        'dash.view_all':        'View All',
        'dash.no_pending':      'No pending submissions.',
        'mod.title':    'Moderation',
        'mod.approve':  'Approve',
        'mod.reject':   'Reject',
        'mod.view':     'Detail',
        'usr.title':    'Users',
        'aud.title':    'Audit Log',
        'notif.title':      'Notifications',
        'notif.empty':      'No new notifications.',
        'notif.scholarship':'New scholarship submitted',
        'notif.anomaly':    'Security anomaly detected',
        'email.title':      'Email Activity Log',
        'email.empty':      'No email events recorded.',
        'email.approved':   'Scholarship Approved',
        'email.rejected':   'Scholarship Rejected',
        'email.submitted':  'New Submission',
        'pub.scholarships': 'Scholarships',
        'pub.bookmarks':    'Bookmarks',
        'pub.promote':      'For Providers: Promote',
        'pub.promotions':   'My Promotions',
        'pub.profile':      'Profile',
        'pub.login':        'Sign In',
        'pub.logout':       'Logout',
    },
    id: {
        'nav.dashboard':    'Dashboard',
        'nav.moderation':   'Moderasi',
        'nav.users':        'Pengguna',
        'nav.auditlog':     'Log Audit',
        'nav.backportal':   'Kembali ke Portal',
        'nav.logout':       'Keluar',
        'topbar.search':    'Cari...',
        'dash.title':           'Dashboard',
        'dash.published':       'Beasiswa Terbit',
        'dash.pending':         'Menunggu Review',
        'dash.applicants':      'Pendaftar',
        'dash.anomalies':       'Anomali Keamanan',
        'dash.pending_mod':     'Moderasi Tertunda',
        'dash.recent_activity': 'Aktivitas Terkini',
        'dash.view_all':        'Lihat Semua',
        'dash.no_pending':      'Tidak ada pengajuan pending.',
        'mod.title':    'Moderasi',
        'mod.approve':  'Setujui',
        'mod.reject':   'Tolak',
        'mod.view':     'Detail',
        'usr.title':    'Pengguna',
        'aud.title':    'Log Audit',
        'notif.title':      'Notifikasi',
        'notif.empty':      'Tidak ada notifikasi baru.',
        'notif.scholarship':'Beasiswa baru diajukan',
        'notif.anomaly':    'Anomali keamanan terdeteksi',
        'email.title':      'Log Aktivitas Email',
        'email.empty':      'Belum ada catatan email.',
        'email.approved':   'Beasiswa Disetujui',
        'email.rejected':   'Beasiswa Ditolak',
        'email.submitted':  'Pengajuan Baru',
        'pub.scholarships': 'Beasiswa',
        'pub.bookmarks':    'Tersimpan',
        'pub.promote':      'Untuk Penyedia: Promosi',
        'pub.promotions':   'Promosi Saya',
        'pub.profile':      'Profil',
        'pub.login':        'Masuk',
        'pub.logout':       'Keluar',
    }
};

function getLang() {
    return localStorage.getItem('sh_lang') || 'id';
}

/** Terapkan bahasa ke semua elemen [data-i18n] — textContent only (XSS-safe) */
function applyLang(lang) {
    const dict = I18N[lang] || I18N['id'];
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (dict[key] !== undefined) el.textContent = dict[key];
    });
    document.querySelectorAll('[data-i18n-ph]').forEach(el => {
        const key = el.getAttribute('data-i18n-ph');
        if (dict[key] !== undefined) el.placeholder = dict[key];
    });
    const langLabel = document.getElementById('langLabel');
    if (langLabel) langLabel.textContent = lang === 'en' ? 'English' : 'Indonesia';
    const langFlag = document.getElementById('langFlag');
    if (langFlag) langFlag.textContent = lang === 'en' ? '\uD83C\uDDEC\uD83C\uDDE7' : '\uD83C\uDDEE\uD83C\uDDE9';
}

function toggleLang() {
    const next = getLang() === 'en' ? 'id' : 'en';
    localStorage.setItem('sh_lang', next);
    applyLang(next);
}

function initLang() { applyLang(getLang()); }


// ==========================================
// NOTIFICATION CENTER (Admin Bell)
// ==========================================

let _notifPanelEl = null;
let _emailPanelEl = null;

function initNotifications() {
    _notifPanelEl = document.getElementById('notifPanel');
    const btn = document.getElementById('notifBellBtn');
    if (!btn || !_notifPanelEl) return;

    btn.addEventListener('click', e => {
        e.stopPropagation();
        _notifPanelEl.classList.toggle('sh-panel-open');
        if (_emailPanelEl) _emailPanelEl.classList.remove('sh-panel-open');
        if (_notifPanelEl.classList.contains('sh-panel-open')) _doLoadNotifications();
    });
    document.addEventListener('click', () => _notifPanelEl && _notifPanelEl.classList.remove('sh-panel-open'));
    _notifPanelEl.addEventListener('click', e => e.stopPropagation());

    // Automatically load badges on init
    _doLoadNotifications();
}

async function _doLoadNotifications() {
    const list  = document.getElementById('notifList');
    const badge = document.getElementById('notifBadge');
    if (!list) return;

    list.innerHTML = '<p class="sh-panel-loading">Loading\u2026</p>';
    const dict = I18N[getLang()];

    try {
        const [logsResp, statsResp] = await Promise.all([
            apiFetch('/admin/audit-logs/?limit=10'),
            apiFetch('/admin/stats/'),
        ]);
        const logs  = logsResp.ok  ? (await logsResp.json())  : [];
        const stats = statsResp.ok ? (await statsResp.json()) : {};
        const items = [];

        if ((stats.total_pending || 0) > 0) {
            items.push({ icon: '\uD83D\uDCCB', color: '#f59e0b',
                title: dict['notif.scholarship'],
                sub: `${stats.total_pending} ${getLang()==='en'?'awaiting review':'menunggu review'}`,
                href: 'admin-moderation.html' });
        }
        if ((stats.recent_anomalies || 0) > 0) {
            items.push({ icon: '\uD83D\uDEA8', color: '#ef4444',
                title: dict['notif.anomaly'],
                sub: `${stats.recent_anomalies} ${getLang()==='en'?'anomalies today':'anomali hari ini'}`,
                href: 'admin-audit.html' });
        }
        const rawLogs = Array.isArray(logs) ? logs : (logs.results || []);
        rawLogs.filter(l => l.action_status === 'FAILED' || l.action_status === 'BLOCKED')
               .slice(0, 3)
               .forEach(l => items.push({
                   icon: '\u26A0\uFE0F', color: '#f97316',
                   title: _shSafe(l.action_type),
                   sub:   `${_shSafe(l.user || 'Guest')} \u00B7 ${_shRelative(l.created_at)}`,
                   href: 'admin-audit.html'
               }));

        list.innerHTML = '';
        if (items.length === 0) {
            list.appendChild(_shEmptyP(dict['notif.empty']));
            if (badge) badge.style.display = 'none';
        } else {
            items.forEach(i => list.appendChild(_buildNotifItem(i)));
            if (badge) { badge.textContent = items.length; badge.style.display = ''; }
        }
    } catch(e) {
        list.innerHTML = '';
        list.appendChild(_shEmptyP('Failed to load.'));
    }
}

function _buildNotifItem({ icon, color, title, sub, href }) {
    const a = document.createElement('a');
    a.href = href || '#';
    a.className = 'sh-notif-item';

    const ic = document.createElement('span');
    ic.className = 'sh-notif-icon';
    ic.style.background = color + '22';
    ic.textContent = icon;

    const bd = document.createElement('div');
    bd.className = 'sh-notif-body';

    const t = document.createElement('span');
    t.className = 'sh-notif-title';
    t.textContent = title;      // XSS-safe

    const s = document.createElement('span');
    s.className = 'sh-notif-sub';
    s.textContent = sub;        // XSS-safe

    bd.appendChild(t); bd.appendChild(s);
    a.appendChild(ic); a.appendChild(bd);
    return a;
}


// ==========================================
// EMAIL LOG PANEL (Opsi C — History)
// ==========================================

function initEmailLog() {
    _emailPanelEl = document.getElementById('emailLogPanel');
    const btn = document.getElementById('emailLogBtn');
    if (!btn || !_emailPanelEl) return;

    btn.addEventListener('click', e => {
        e.stopPropagation();
        _emailPanelEl.classList.toggle('sh-panel-open');
        if (_notifPanelEl) _notifPanelEl.classList.remove('sh-panel-open');
        if (_emailPanelEl.classList.contains('sh-panel-open')) _doLoadEmailLog();
    });
    document.addEventListener('click', () => _emailPanelEl && _emailPanelEl.classList.remove('sh-panel-open'));
    _emailPanelEl.addEventListener('click', e => e.stopPropagation());

    // Automatically load badges on init
    _doLoadEmailLog();
}

async function _doLoadEmailLog() {
    const list  = document.getElementById('emailLogList');
    const badge = document.getElementById('emailBadge');
    if (!list) return;

    list.innerHTML = '<p class="sh-panel-loading">Loading\u2026</p>';
    const dict = I18N[getLang()];

    try {
        const resp = await apiFetch('/admin/audit-logs/?limit=20&action_category=DATA_MUTATION');
        if (!resp.ok) throw new Error();
        const data = await resp.json();
        const logs = Array.isArray(data) ? data : (data.results || []);
        const emailEvents = logs.filter(l =>
            ['SCHOLARSHIP_APPROVED','SCHOLARSHIP_REJECTED','SCHOLARSHIP_SUBMITTED'].includes(l.action_type)
        );

        list.innerHTML = '';
        if (emailEvents.length === 0) {
            list.appendChild(_shEmptyP(dict['email.empty']));
            if (badge) badge.style.display = 'none';
        } else {
            emailEvents.forEach(ev => list.appendChild(_buildEmailItem(ev, dict)));
            if (badge) { badge.textContent = emailEvents.length; badge.style.display = ''; }
        }
    } catch(e) {
        list.innerHTML = '';
        list.appendChild(_shEmptyP('Failed to load.'));
    }
}

function _buildEmailItem(ev, dict) {
    const map = {
        'SCHOLARSHIP_APPROVED':  { icon:'\u2705', color:'#10b981', label: dict['email.approved'] },
        'SCHOLARSHIP_REJECTED':  { icon:'\u274C', color:'#ef4444', label: dict['email.rejected'] },
        'SCHOLARSHIP_SUBMITTED': { icon:'\uD83D\uDCE8', color:'#3b82f6', label: dict['email.submitted'] },
    };
    const m = map[ev.action_type] || { icon:'\uD83D\uDCE7', color:'#6b7280', label: _shSafe(ev.action_type) };

    const wrap = document.createElement('div');
    wrap.className = 'sh-notif-item';
    wrap.style.cursor = 'default';

    const ic = document.createElement('span');
    ic.className = 'sh-notif-icon';
    ic.style.background = m.color + '22';
    ic.textContent = m.icon;

    const bd = document.createElement('div');
    bd.className = 'sh-notif-body';

    const t = document.createElement('span');
    t.className = 'sh-notif-title';
    t.textContent = m.label;    // XSS-safe

    const s = document.createElement('span');
    s.className = 'sh-notif-sub';
    s.textContent = `${_shSafe(ev.user || 'System')} \u00B7 ${_shRelative(ev.created_at)}`;  // XSS-safe

    const st = document.createElement('span');
    st.className = 'sh-email-status';
    st.style.color = ev.action_status === 'SUCCESS' ? '#10b981' : '#ef4444';
    st.textContent = ev.action_status;  // hanya 'SUCCESS'|'FAILED'|'BLOCKED' dari enum

    bd.appendChild(t); bd.appendChild(s); bd.appendChild(st);
    wrap.appendChild(ic); wrap.appendChild(bd);
    return wrap;
}


// ── Shared private helpers ──────────────────────────────────────────────────
function _shSafe(str) {
    if (typeof str !== 'string') return '';
    // Encode karakter HTML berbahaya — digunakan hanya untuk textContent fallback
    return str.replace(/[<>&"']/g, c =>
        ({ '<':'<', '>':'>', '&':'&', '"':'"', "'":'&#39;' }[c]));
}

function _shRelative(dateStr) {
    if (!dateStr) return '';
    const diff = Math.floor((Date.now() - new Date(dateStr)) / 1000);
    const isEn = getLang() === 'en';
    if (diff < 60)    return isEn ? 'just now'          : 'baru saja';
    if (diff < 3600)  return `${Math.floor(diff/60)} ${isEn ? 'min ago' : 'mnt lalu'}`;
    if (diff < 86400) return `${Math.floor(diff/3600)} ${isEn ? 'hr ago' : 'jam lalu'}`;
    return formatDate(dateStr);
}

function _shEmptyP(text) {
    const p = document.createElement('p');
    p.className = 'sh-panel-empty';
    p.textContent = text;   // XSS-safe
    return p;
}
