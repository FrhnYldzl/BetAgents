# 🚂 Railway Deployment Rehberi — BetAgents

**Tarih:** 2026-05-31
**Hedef:** PC kapansa bile 7/24 çalışan sistem (web UI + otomatik kupon/settle worker), PostgreSQL veritabanı ile.

---

## Mimari (Railway'de 3 bileşen)

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  WEB servisi    │     │  WORKER servisi │     │  PostgreSQL      │
│  Streamlit      │────▶│  worker.py      │────▶│  (managed)       │
│  app_unified    │     │  auto_play +    │     │  matches_v2,     │
│  :$PORT         │     │  auto_settle    │     │  signal_snapshots│
│                 │     │  (APScheduler)  │     │  paper_* ...     │
└─────────────────┘     └─────────────────┘     └──────────────────┘
        │                       │                         ▲
        └───────────────────────┴─────── DATABASE_URL ────┘
              (ikisi de AYNI Postgres'i paylaşır)
```

Railway Volume'ü tek servise bağlanabildiği için SQLite paylaşılamazdı →
**PostgreSQL** ile web + worker aynı DB'yi temiz paylaşır.

---

## Repo tarafı (HAZIR ✅)

| Dosya | Görev |
|---|---|
| `Dockerfile` | **Build deterministik** — alt-dizindeki Streamlit'i doğru başlatır (Railpack auto-detect sorununu kökten çözer) |
| `requirements-railway.txt` | SLIM runtime (streamlit/pandas/numpy/plotly/psycopg2/APScheduler) — hızlı build |
| `.dockerignore` | Veri artefaktları imaja girmez |
| `railway.json` | Builder=DOCKERFILE + start command + healthcheck |
| `.python-version` | Python 3.12 |
| `Procfile` | `web` + `worker` süreç tanımları (yedek/dok.) |
| `worker.py` | APScheduler: auto_play (06:00/15:00 UTC) + auto_settle (90 dk) |
| `02_VERI/db.py` | DATABASE_URL'e göre SQLite/PostgreSQL otomatik seçim |
| `02_VERI/migrate_to_postgres.py` | SQLite → PostgreSQL veri taşıma (21 tablo) |
| `.streamlit/config.toml` | Headless + 0.0.0.0 + dark tema |
| `.env.example` | Değişken şablonu |

---

## ADIMLAR

### 1. Projeyi oluştur + repo bağla
1. Railway → **New Project** → **Deploy from GitHub repo**
2. `FrhnYldzl/BetAgents` seç
3. Railway `railway.json`'ı görür → **web servisi** otomatik kurulur
   (start command: `streamlit run 08_AI_TRADER/app_unified.py --server.port $PORT --server.address 0.0.0.0`)

### 2. PostgreSQL ekle
1. Aynı proje içinde → **New** → **Database** → **Add PostgreSQL**
2. Railway `Postgres` servisini ve `DATABASE_URL`'ü otomatik üretir

### 3. Web servisine DATABASE_URL bağla
1. **web** servisi → **Variables** sekmesi
2. Yeni değişken:  `DATABASE_URL` = `${{ Postgres.DATABASE_URL }}`  (referans değişken)

### 4. Veriyi taşı (YEREL'den — bir kez)
> SQLite dosyası (`bahis_agent.db`) repo'da YOK (gitignore). Bu yüzden taşıma
> **senin bilgisayarından**, Railway Postgres'in **public** adresine yapılır.

1. Railway → **Postgres** servisi → **Variables** → `DATABASE_PUBLIC_URL` değerini kopyala
2. Kendi terminalinde (şifreyi SEN giriyorsun — ben girmem):

   **Windows PowerShell:**
   ```powershell
   $env:DATABASE_URL = "postgresql://...DATABASE_PUBLIC_URL..."
   cd "...\YAZILIM\02_VERI"
   python migrate_to_postgres.py
   ```

3. Çıktıda her tablo için `src=N dst=N OK` görmelisin → `✅ TAŞIMA BAŞARILI`
4. (İsteğe bağlı doğrulama) `python migrate_to_postgres.py --verify`

### 5. Otomasyon (worker) — İKİ SEÇENEK

**A) Inline worker (VARSAYILAN — ekstra servis / login GEREKMEZ) ✅**
Web servisi `start.py` ile streamlit'i ön planda çalıştırırken **worker.py'yi arka
planda da başlatır** (auto_play 06/15 UTC + auto_settle 90dk). Yani web servisi
deploy edildiği an sistem 7/24 otonomdur — başka bir şey yapmana gerek yok.
Kapatmak istersen web servisine `INLINE_WORKER=0` ver.

**B) Adanmış worker servisi (opsiyonel — yük ayrımı istersen)**
1. Proje → **New** → **GitHub Repo** → tekrar `FrhnYldzl/BetAgents`
2. Bu servis → **Variables** → `ROLE=worker` + `DATABASE_URL` = `${{ Postgres.DATABASE_URL }}`
   (`start.py`, `ROLE=worker` görünce otomatik `worker.py` çalıştırır)
3. **ÖNEMLİ:** web servisinde `INLINE_WORKER=0` ver (çift tetikleme olmasın)

### 6. Web'e domain ver
1. **web** servisi → **Settings** → **Networking** → **Generate Domain**
2. `https://betagents-production.up.railway.app` benzeri adres alırsın → UI canlı

---

## Doğrulama (deploy sonrası)

- [ ] Web domain açılıyor, sayfalar yükleniyor (Genel Bakış, Maçlar, Veri Kalitesi…)
- [ ] **web** logs: PostgreSQL'e bağlanıyor (SQLite "no such table" hatası YOK)
- [ ] **worker** logs: `WORKER BAŞLADI` + açılış `AUTO_SETTLE tetiklendi`
- [ ] Postgres'te veri var: `matches_v2` ~19.303, `signal_snapshots` ~19.198

---

## Maliyet
Railway Hobby: ~$5/ay kredi. Web (idle çoğu zaman) + küçük worker + küçük
Postgres bu bütçeye sığar. Worker sürekli açık ama neredeyse hep uyur (sadece
06:00/15:00 UTC ve 90 dk'da bir kısa iş).

## Yerel geliştirme bozulmadı
`DATABASE_URL` yokken sistem otomatik SQLite kullanır. Hiçbir şey değişmeden
`python -m streamlit run 08_AI_TRADER/app_unified.py --server.port 8500` çalışır.

## Test
`python 02_VERI/test_db_layer.py` → 14/14 (PG çeviri + SQLite işlevsel).
