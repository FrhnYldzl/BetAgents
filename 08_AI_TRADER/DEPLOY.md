# AI TRADER PRO — Deploy Rehberi

**Hedef:** Lokal Streamlit → GitHub → Railway production
**Trigger:** Kullanıcı "Ne zaman dersen taşırız" dedi, hazır olduğunda.

---

## 🎯 DEPLOY KOMUTUNU BEKLİYORUZ

Şu an **localhost:8503**'te çalışıyor. Kullanıcı izin verdiğinde:

```bash
# 1. GitHub'a push (private repo)
git init
git add .
git commit -m "AI Trader Pro v2.1"
git remote add origin git@github.com:ferhanyildizli/ai-trader-pro.git
git push -u origin main

# 2. Railway deploy
# - Yeni proje aç (https://railway.app)
# - GitHub repo bağla
# - Auto-deploy enable
# - Build command: pip install -r requirements.txt
# - Start command: streamlit run 08_AI_TRADER/app_pro.py --server.port $PORT --server.address 0.0.0.0
```

---

## 📋 PRE-DEPLOY CHECKLIST

### Kod & Yapı
- [x] `app_pro.py` syntax OK
- [x] Tüm sayfalar render ediliyor
- [x] iddia.com linkleri çalışır URL'ler
- [x] Tarih formatları kurumsal (24 May Paz)
- [ ] `requirements.txt` oluştur
- [ ] `.gitignore` (db dosyaları, snapshots gibi büyük artifact'ler)
- [ ] `.env.example` (API key placeholder'lar)
- [ ] `README.md` (proje overview)
- [ ] `Procfile` veya `railway.json` (Railway config)

### Güvenlik
- [ ] DB dosyası repo'ya girmesin (.gitignore)
- [ ] API key'ler env variable (kullanılırsa)
- [ ] Hassas log/snapshot dosyaları .gitignore
- [ ] Streamlit secrets.toml (production secrets)

### Performans
- [ ] DB upload edilecek (Railway volume veya S3)
- [ ] Cache decoratörleri (@st.cache_data) check
- [ ] Heavy query'ler optimize
- [ ] Static asset CDN (gerekirse)

### Monitoring
- [ ] Health check endpoint
- [ ] Error logging (Sentry?)
- [ ] Analytics (PostHog/Vercel Analytics?)
- [ ] Uptime monitoring (UptimeRobot?)

---

## 🚀 İLK DEPLOY ADIM ADIM

### Adım 1: requirements.txt
```txt
streamlit>=1.30.0
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.18.0
scipy>=1.11.0
openpyxl>=3.1.0  # Excel export
pyarrow>=14.0.0  # Parquet
scikit-learn>=1.3.0  # Platt calibration (opsiyonel)
```

### Adım 2: .gitignore
```
# Database
*.db
*.db-journal
*.db-wal

# Snapshots (büyük data)
02_VERI/snapshots/
02_VERI/exports/

# Python
__pycache__/
*.pyc
*.pyo
.venv/
.env

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Logs
*.log
07_LOG_VE_RAPORLAR/*.csv
```

### Adım 3: Procfile (Railway)
```
web: streamlit run 08_AI_TRADER/app_pro.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
```

### Adım 4: railway.json (opsiyonel)
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "streamlit run 08_AI_TRADER/app_pro.py --server.port $PORT --server.address 0.0.0.0",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

### Adım 5: DB Strategy
Database **büyük (8+ MB)**. Seçenekler:

**Seçenek A: DB'yi repo'da tut (Git LFS)**
```bash
git lfs install
git lfs track "*.db"
```

**Seçenek B: Railway Volume (önerilen)**
- Railway'de persistent volume oluştur
- DB'yi volume'a upload et
- Container'da volume mount

**Seçenek C: External DB (PostgreSQL)**
- SQLite → PostgreSQL migration
- Railway PostgreSQL plugin
- Daha ölçeklenebilir (>100K satır için)

### Adım 6: Auth (opsiyonel)
Multi-user için `streamlit-authenticator`:
```python
import streamlit_authenticator as stauth
authenticator = stauth.Authenticate(...)
name, auth_status, username = authenticator.login('Login', 'main')
```

---

## 🔄 SÜREKLİ DEPLOYMENT

### GitHub Actions (CI/CD)
`.github/workflows/test.yml`:
```yaml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python -c "import ast; ast.parse(open('08_AI_TRADER/app_pro.py').read())"
```

### Railway Auto-Deploy
- Branch: `main` → production
- Branch: `dev` → staging
- Pull request → preview deploy

---

## 📊 PRODUCTION KPI'LARI

Deploy sonrası takip:
- **Uptime**: Hedef %99.5+
- **Response time**: Sayfa yükleme <2s
- **DB query**: Heavy query <500ms
- **Concurrent users**: 10-50 (Railway free tier limit)
- **Memory**: <512MB (Streamlit basic)

---

## 🎯 SaaS YOL HARİTASI

```
Hafta 1-2:  Lokal polish (ŞIMDI BURADAYIZ)
            ├─ iddia.com link çalışır ✓
            ├─ Güncel takvim sayfası ✓
            └─ Kurumsal dil ✓

Hafta 3:    GitHub + Railway deploy
            ├─ requirements.txt
            ├─ Procfile
            └─ DB strategy karar

Hafta 4-6:  Production hardening
            ├─ Auth (streamlit-authenticator)
            ├─ Monitoring (Sentry + UptimeRobot)
            └─ Custom domain

Ay 2-3:     Next.js production
            ├─ TypeScript + Tailwind
            ├─ WebSocket realtime
            └─ Mobile PWA

Ay 4+:      SaaS scale
            ├─ Multi-tenant
            ├─ Subscription (Stripe)
            └─ API access (paid tier)
```

---

## ⚠️ KULLANICI DEDİ Kİ

> "Bir yere taşıma sadece SaaS mantığıyla bana ürünü sun eksiksiz kusursuz
>  404 ler var html kalmış kurumsal bir dili olsun dashboardlar panel sistemi vs.
>  Sonra github ve railway'e taşırız ne zaman dersen!"

**Anlam:** Şu an LOKAL polish'a odaklan, deploy daha sonra. ✓
