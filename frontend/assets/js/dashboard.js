// dashboard.js

// Fungsi Satpam (Sudah ada di kode kamu)
document.addEventListener('DOMContentLoaded', function() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = 'login.html';
    }
});

async function saveScholarship(id) {
    const token = localStorage.getItem('access_token');
    console.log("Mencoba simpan ID:", id); // Cek di console (F12)

    try {
        const response = await fetch('http://localhost:8000/api/bookmarks/', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ scholarship: id })
        });

        if (response.ok) {
            alert("Beasiswa berhasil disimpan!");
            const btn = document.getElementById(`save-btn-${id}`);
            btn.innerText = "Saved";
            btn.disabled = true;
        } else {
            const err = await response.json();
            alert("Gagal: " + (err.detail || "Sudah disimpan atau role bukan applicant"));
        }
    } catch (e) {
        alert("Error koneksi!");
    }
}

// Fungsi Logout (Sudah ada di kode kamu)
function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('username');
    window.location.href = 'login.html';
}