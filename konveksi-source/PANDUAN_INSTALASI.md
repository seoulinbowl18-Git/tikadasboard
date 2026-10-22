# Aplikasi Manajemen Konveksi — Panduan Menjalankan

Modul: Dashboard, Faris Matesih (pengiriman & status), Mas Eko Kalijambe (motif masuk), Konveksi Irawan (ongkos jahit).

## Kebutuhan
- Python 3.10+
- Node.js 18+ dan Yarn (`npm install -g yarn`)
- MongoDB (lokal atau MongoDB Atlas)

## 1. Backend (FastAPI)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # lalu isi nilai di .env
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```
Saat pertama kali jalan, akun admin (dari ADMIN_EMAIL / ADMIN_PASSWORD) dan data demo otomatis dibuat.

> Catatan: jika `pip install` gagal pada paket `emergentintegrations`, hapus baris tersebut dari requirements.txt (tidak dipakai aplikasi ini).

## 2. Frontend (React)
```bash
cd frontend
yarn install
cp .env.example .env             # REACT_APP_BACKEND_URL=http://localhost:8001
yarn start
```
Buka http://localhost:3000 lalu login dengan email & password admin dari `backend/.env`.

## Struktur
```
backend/server.py     API (auth, dashboard, faris, eko, irawan)
frontend/src/App.js   Seluruh tampilan, grafik, ekspor Excel/PDF
```
