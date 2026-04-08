# === ScholarHub Vault Policy ===
# Path yang dibutuhkan oleh aplikasi Django

# Dynamic database credentials (MariaDB)
path "database/creds/scholarhub-role" {
  capabilities = ["read"]
}

# Django SECRET_KEY dan konfigurasi aplikasi
path "secret/data/scholarhub/django" {
  capabilities = ["read"]
}

# JWT Signing Key (terpisah dari SECRET_KEY)
path "secret/data/scholarhub/jwt" {
  capabilities = ["read"]
}

# Redis credentials
path "secret/data/scholarhub/redis" {
  capabilities = ["read"]
}