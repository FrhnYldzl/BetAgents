# 🏛️ v3 MİMARİ & PRODUCTION ROADMAP
## Profesyonel Ürün: GitHub + Railway + PostgreSQL + Birleşik App

**Tarih:** 2026-05-31  
**Hedef:** Yerel-PC bağımlı, kırılgan kurulumdan → 24/7 çalışan, versiyonlanmış profesyonel ürüne geçiş  
**Durum:** Plan + Faz 0 hazırlığı yapıldı (requirements.txt, .gitignore)

---

## 1. NEDEN? — Mevcut Kırılganlıklar (Kök Sebepler)

Bugüne kadar yaşadığımız her hata, mimari bir kök sebebe dayanıyor:

| Yaşanan Hata | Kök Sebep | Kalıcı Çözüm |
|---|---|---|
| Gece görevler çalışmadı | Yerel PC uyuyunca cron durur | **24/7 cloud host (Railway)** |
| Server düştü | Manuel başlatılan local process | **Cloud auto-restart** |
| Skor çekilmedi, kupon takıldı | Tek-yönlü, izlenmeyen pipeline | **Cloud cron + healthcheck** |
| Mükerrer kupon | Dedup yoktu | ✅ Düzeltildi (kod) |
| VOID muhasebe hatası | Push mantığı yoktu | ✅ Düzeltildi (kod) |
| 8503 + 8504 dağınıklık | İki ayrı app, iki ayrı DB bağlantısı | **Tek birleşik app** |
| Veri tutarsızlığı riski | SQLite tek-dosya, kilit sorunu | **PostgreSQL (managed)** |
| Geri alınamaz değişiklik | Git yok | **GitHub + version control** |
| "Hangi sürüm?" belirsizliği | Versiyonlama yok | **Semantic versioning + CHANGELOG** |

**Özet:** Kod hataları tek tek düzeltildi ama **altyapı kırılgan**. Profesyonel ürün = altyapıyı sağlamlaştırmak.

---

## 2. HEDEF MİMARİ

```
┌─────────────────────────────────────────────────────────┐
│  GitHub (kaynak kontrol + CHANGELOG + sürümler)          │
│     └── push → otomatik deploy                           │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  RAILWAY (24/7 — yerel PC'den BAĞIMSIZ)                  │
│                                                          │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ Web (Streamlit) │  │ PostgreSQL   │  │ Cron       │ │
│  │ TEK birleşik app│←→│ (managed DB) │←→│ Scheduler  │ │
│  │ Research+Trader │  │              │  │ play+settle│ │
│  └─────────────────┘  └──────────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────┘
                         ↑
              iddaa.com API'leri (data kaynağı)
```

**Yerel PC artık SADECE geliştirme için.** Üretim Railway'de 7/24 döner.

---

## 3. FAZLI PLAN

### ✅ FAZ 0 — Repo Hijyeni (HAZIRLANIYOR)
```
[x] requirements.txt    (tüm bağımlılıklar pinlendi)
[x] .gitignore          (sırlar, DB, loglar hariç)
[ ] git init + ilk commit
[ ] README.md (kurulum + mimari)
[ ] .env.example (config şablonu)
[ ] Klasör yapısı temizliği (test/audit scriptleri ayrı)
```

### FAZ 1 — İki App'i Birleştir (8503 + 8504 → tek)
```
Tek Streamlit app, iki mod (sidebar seçimi):
  📊 RESEARCH  (eski 8503: analiz, model katalog, backtest, data)
  💸 TRADER    (eski 8504: canlı kupon, journal, hedefli para yönetimi)

Ortak: DB bağlantı katmanı, header, tema.
Sonuç: tek port, tek kod tabanı, tek deploy.
```

### FAZ 2 — SQLite → PostgreSQL
```
DB sadece 0.19 MB → migrasyon DÜŞÜK riskli.
1. db.py soyutlama katmanı (SQLite/Postgres ikisini de destekler)
2. SQLAlchemy connection (DATABASE_URL env ile)
3. Migrasyon scripti: SQLite → Postgres dump/restore
4. Tüm sorgular parametreli (zaten öyle)
```

### FAZ 3 — Railway Deploy (24/7)
```
1. Railway projesi: Web + Postgres + Cron servisleri
2. Procfile / railway.json
3. Web: streamlit run app.py --server.port $PORT
4. Cron servisi:
     */90dk → auto_settle.py  (skor çek + kapat)
     09:00, 18:00 → auto_play.py (kupon oluştur)
   → PC kapalıyken bile çalışır!
5. Healthcheck endpoint
```

### FAZ 4 — Versiyonlanmış Ürün
```
Semantic versioning: v3.0.0, v3.1.0...
CHANGELOG.md: her sürümde ne değişti
3 paralel geliştirme ekseni (sürekli):
  📥 DATA   — yeni kaynaklar, enrichment, kalite
  🧠 MODEL  — yeni sinyaller, kalibrasyon, backtest
  💸 TRADE  — para yönetimi, risk, otomasyon
```

---

## 4. SÜREKLİ GELİŞTİRME — 3 EKSEN (Ürün Omurgası)

### 📥 EKSEN: DATA
| Sürüm | İçerik | Durum |
|---|---|---|
| v3.0 | iddaa canlı + 19K tarihsel + enriched (H2H/form/standings) | ✅ |
| v3.1 | iddaa statisticsv2: kadro + oyuncu gol/asist + korner geçmişi | ⏳ |
| v3.2 | BetRadar ID köprüsü → Sofascore/SportsBetData xG | 🔜 |
| v3.3 | Transfermarkt sakatlık + FotMob T1 xG | 🔜 |

### 🧠 EKSEN: MODEL
| Sürüm | İçerik | Durum |
|---|---|---|
| v3.0 | Edge65 + xG + H2H + Standings overlay (kanıtlı) | ✅ |
| v3.1 | Kapı 1: FAV → VALUE pivot | ⏳ |
| v3.2 | KG/AÜ modelleri (iddaa KG odds gelince) | 🔜 |
| v3.3 | Kadro-tabanlı feature + sakatlık entegrasyonu | 🔜 |

### 💸 EKSEN: TRADE
| Sürüm | İçerik | Durum |
|---|---|---|
| v3.0 | Hedefli dönem (+%20), stop-loss, mükerrer engeli, void-iade | ✅ |
| v3.1 | Otomatik raporlama (günlük/haftalık özet) | ⏳ |
| v3.2 | Çoklu portföy (farklı stratejiler paralel) | 🔜 |
| v3.3 | Kelly opsiyonu + dinamik stake | 🔜 |

---

## 5. API KAYIT DEFTERİ → ayrı dosya

Tüm veri kaynakları ve endpoint'ler: [`v3_API_REGISTRY.md`](./v3_API_REGISTRY.md)

---

## 6. MALİYET & KARARLAR

| Kalem | Seçenek | Maliyet |
|---|---|---|
| Cloud host | Railway Hobby | ~$5/ay (~170 TL) |
| Cloud host (alt.) | Render free / Fly.io | $0 (kısıtlı) |
| PostgreSQL | Railway managed | Hobby'ye dahil |
| GitHub | Private repo | Ücretsiz |
| Domain (ops.) | iddaa-trader.app vb. | ~$12/yıl |

**Not:** Ben (AI) hesap açamam veya ödeme giremem (güvenlik). Tüm kod/config hazırlanır; hesap kurulumu + bağlama senin tarafında.

---

## 7. RİSKLER & AZALTMA

| Risk | Azaltma |
|---|---|
| Railway maliyeti artar | Free tier ile başla, gerekirse yükselt |
| Postgres migrasyon hatası | DB küçük (0.19MB), önce snapshot al |
| iddaa API değişirse | API registry + versiyonlu adapter |
| Cloud cron kaçırırsa | Healthcheck + idempotent script (zaten void-fallback var) |

---

*Rapor: 2026-05-31 · Faz 0 hazır · Bulut kararları bekleniyor*
