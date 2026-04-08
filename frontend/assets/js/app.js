// frontend/assets/js/app.js

// ==========================================
// 1. LOGIKA UNTUK HALAMAN REGISTER
// ==========================================
const registerForm = document.getElementById('registerForm');

// Cek apakah kita sedang berada di halaman register
if (registerForm) {
    registerForm.addEventListener('submit', async function(e) {
        e.preventDefault(); // Mencegah halaman me-refresh otomatis saat tombol diklik

        // Ambil data yang diketik pengguna
        const username = document.getElementById('regUsername').value;
        const email = document.getElementById('regEmail').value;
        const password = document.getElementById('regPassword').value;

        try {
            // Tembakkan ke API Register Backend Anda
            const response = await fetch('http://127.0.0.1:8000/api/register/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username: username,
                    email: email,
                    password: password,
                    role: 'applicant' // Otomatis mendaftar sebagai pelamar
                })
            });

            const data = await response.json();

            if (response.ok) {
                alert('Registrasi Berhasil! Silakan Login.');
                window.location.href = 'login.html'; // Tendang pengguna ke halaman login
            } else {
                // Jika gagal (misal username sudah ada)
                alert('Gagal: ' + JSON.stringify(data));
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Tidak dapat menghubungi server. Pastikan Backend menyala!');
        }
    });
}

// ==========================================
// 2. LOGIKA UNTUK HALAMAN LOGIN
// ==========================================
const loginForm = document.getElementById('loginForm');

// Cek apakah kita sedang berada di halaman login
if (loginForm) {
    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        // Ambil data dari form login
        const username = document.getElementById('loginUsername').value;
        const password = document.getElementById('loginPassword').value;

        try {
            // Tembakkan ke API Login Backend Anda 
            // (Catatan: Jika di urls.py Anda namanya /api/token/, silakan ganti url di bawah ini)
            const response = await fetch('http://127.0.0.1:8000/api/login/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username: username,
                    password: password
                })
            });

            const data = await response.json();

            if (response.ok) {
                // Jika sukses, SIMPAN TOKEN JWT ke "Saku" Browser (Local Storage)
                localStorage.setItem('access_token', data.access); 
                if (data.refresh) {
                    localStorage.setItem('refresh_token', data.refresh);
                }

                localStorage.setItem('username', username);

                alert('Login Berhasil, Selamat Datang!');
                
                // Bawa pengguna ke halaman Dashboard
                window.location.replace('dashboard.html'); 
            } else {
                alert('Login Gagal: Username atau Password salah!');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Tidak dapat menghubungi server. Pastikan terowongan Kubernetes Anda terbuka!');
        }
    });
}