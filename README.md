# 📊 FinHelper - Personal Finance Dashboard

FinHelper adalah aplikasi **manajemen keuangan pribadi** berbasis web yang membantu melacak pemasukan, pengeluaran, anggaran, dan menampilkan laporan finansial secara interaktif.

![Dashboard Preview](./FinHelper%20-%20Personal%20Finance%20Dashboard.png)

---

## 🚀 Fitur Utama

- **Ringkasan Keuangan**  
  - Total Balance  
  - Monthly Income  
  - Monthly Expenses  
  - Monthly Savings  

- **Visualisasi**  
  - Pie chart: Expenses by Category  
  - Line chart: Monthly Cashflow  

- **Budgeting**  
  - Status anggaran bulanan  
  - Pengingat untuk membuat budget baru  

- **Manajemen Transaksi**  
  - Recent Transactions dengan kategori (Education, Food & Dining, dsb)  
  - Tambah transaksi baru  

- **Integrasi & Export**  
  - Sync ke Google Sheets  
  - Export laporan keuangan  

---

## 🛠️ Tech Stack

- **Backend**: Python (FastAPI)  
- **Frontend**: Jinja2 + HTML + CSS + JS  
- **Database**: SQLite  
- **Deployment**: Docker + GitHub Actions (CI/CD)  
- **Visualisasi**: Chart.js  

---

## 📦 Instalasi & Menjalankan Aplikasi

### 1. Clone Repository
```bash
git clone https://github.com/FaturRachmann/FinHelper.git
cd FinHelper
2. Buat Virtual Environment & Install Dependencies
bash
python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows

pip install -r requirements.txt
3. Jalankan Aplikasi
bash
uvicorn app.main:app --reload
Buka di browser: http://localhost:8000

4. Menjalankan via Docker
bash
docker build -t finhelper-app .
docker run -d -p 8000:8000 finhelper-app
⚙️ CI/CD
Repo ini sudah terintegrasi dengan GitHub Actions:

Lint & Test
Build Docker Image
Push ke Docker Hub

📌 Roadmap
 Autentikasi User
 Multi-user & multi-wallet
 Support PostgreSQL
 Export PDF/Excel report
 Notifikasi pengingat budget

🤝 Kontribusi
Pull request sangat diterima!
Untuk perubahan besar, mohon buka issue terlebih dahulu untuk mendiskusikan apa yang ingin diubah.

📜 License
MIT License © 2025 - Fatur Rachman
