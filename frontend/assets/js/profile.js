// frontend/assets/js/profile.js

document.addEventListener('DOMContentLoaded', function() {
    // 1. Ambil nama dari "Saku" (LocalStorage) yang diisi pas Login
    const usernameAktif = localStorage.getItem('username');
    const token = localStorage.getItem('access_token');

    // 2. Satpam: Kalau belum login, usir ke halaman login
    if (!token) {
        window.location.href = 'login.html';
        return;
    }

    // 3. Pasang nama asli ke dalam kotak input
    const nameInput = document.getElementById('profileName');
    const emailInput = document.getElementById('profileEmail');

    if (usernameAktif) {
        nameInput.value = usernameAktif;
        // Karena email belum kita tarik dari database, kita buat tampilan sementara dulu
        emailInput.value = usernameAktif.toLowerCase() + "@mail.com";
    }
});