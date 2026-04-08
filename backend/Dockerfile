# Gunakan Python versi stabil dan ringan
FROM python:3.11-slim

# Set environment variables agar Python berjalan lancar di Docker
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install library sistem yang wajib untuk koneksi Database MariaDB
# Tanpa 'default-libmysqlclient-dev', instalasi mysqlclient akan gagal
RUN apt-get update && apt-get install -y \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Buat folder kerja di dalam container
WORKDIR /app

# Copy daftar belanjaan dan install
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy sisa kode (nanti)
COPY . /app/

# Buka jalur komunikasi port 8000
EXPOSE 8000

# Perintah default saat container nyala
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "scholarhub.wsgi:application"]