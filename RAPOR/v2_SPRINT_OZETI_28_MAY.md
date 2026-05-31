# 🚀 SPRINT ÖZETİ — 28 MAYIS 2026

**Sprint Süresi:** ~1 gün
**Tamamlanan:** 4 büyük adım
**Status:** Üç Eksen %85+ tamamlandı

---

## ✅ TAMAMLANAN İŞLER (Bu Sprintte)

### 1️⃣ EKSEN 1 — DATABASE (TAŞINABİLİR + VERSİYONLU)
- **db_versioning.py** — snapshot/restore/list/auto sistemi
- **db_export.py** — CSV/Excel/Parquet adapters
- **DATA_DICTIONARY.md** — 16 tablo, tüm kolonlar dokümante
- 2 snapshot alındı: `v2.0_20260528_1624` + `v2.1_20260528_1654`
- İlk export: 16 tablo, 67K satır CSV → `exports/csv_*/`

### 2️⃣ EKSEN 2 — MODEL REGISTRY
- **model_registry.json** — 13 model (JSON) + 2 family
- **MODEL_CATALOG.md** — insan-okur katalog
- Lifecycle: 5 VALIDATED, 5 PROTOTYPE, 3 DEPRECATED
- Her model: isim+amaç+neden+nasıl+performance+caveats

### 3️⃣ EKSEN 3 — TRADER UI (BORSA-GRADE)
- **app_pro.py** — Bloomberg/TradingView estetiği
- 6 sayfa: Trading Desk / Coupon Eng / Models / Analytics / Data / Risk
- **iddia.com link entegrasyonu** — her pick'te "▶ İDDAA'ya GİT" butonu
- **Tarih formatı** — "24 May Paz" şeklinde
- Custom CSS (~200 satır) terminal vibesi
- http://localhost:8503 canlı

### 4️⃣ V2 PLATT KALIBRASYON
- KG ve A/Ü 2.5 modelleri kalibre edildi (per-lig)
- KG: gap %14 → %3.5 (kalibre)
- A/Ü: gap %5.7 → %2.5 (kalibre)
- Yeni kolonlar: `fp_*_cal`, `s_*_cal`, `dir_*_cal`

---

## 📊 ÜRÜN AİLESİ — GÜNCEL 10 SİLAH

### VOX Family (1X2 selective sniper)
| Silah | Lig | n | hit% | Bonferroni |
|---|---|---|---|---|
| **DUOVOX** ⭐ | E0+SP1 | 1,807 | %62 | p=0.0000 |
| **TRIOVOX** | E0+SP1+D1 | 2,529 | %60 | p=0.0001 |
| **MONOVOX-E0** | E0 | 881 | %65 | p=0.0017 |
| **TRIVOX** | T1 | 22 (Q5+a2) | **%82** | p=0.0071 |
| **MONOVOX-SP1** | SP1 | 926 | %55 | p=0.0081 |

### MARKET Family (Multi-market, Platt kalibre)
| Silah | Lig | Yön | n | hit% | edge |
|---|---|---|---|---|---|
| **OU25-D1-Over** | D1 | Over | 178 | %59 | **+%4.18** ⭐ |
| **OU25-E0-Under** | E0 | Under | 297 | %41 | +%3.55 |
| **OU25-T1-Under** | T1 | Under | 240 | %45 | +%1.60 |
| **OU25-SP1-Over** | SP1 | Over | 324 | %40 | +%1.54 |
| **BTTS-D1-Var** | D1 | Var | 497 | %64 | (kalibre sonrası iyileşti) |
| **BTTS-T1-Var** | T1 | Var | 396 | %64 | yeni model |

---

## 📈 ÜÇLÜ EKSEN — FINAL SKOR

| Eksen | Önce (sabah) | Sonra (akşam) | Hedef |
|---|---|---|---|
| **1️⃣ DATABASE** | 6/10 | **9/10** ✅ | 9/10 |
| **2️⃣ MODEL REGISTRY** | 5/10 | **8/10** ✅ | 9/10 |
| **3️⃣ TRADER UI** | 5/10 | **8/10** ✅ | 9/10 |

**Genel:** 16/30 → **25/30** (+9 puan / +30 puanlık ilerleme)

---

## 🎯 BUGÜNÜN HİKAYESİ

```
Sabah:
  - 2025-26 sezon uyumsuzluk fark edildi (anomaly %50)
  - PSCH (Pinnacle) %44 dolu sorunu

Öğle:
  - Fallback chain: PSCH → AvgH → B365CH eklendi
  - 2025-26 → %100 coverage
  - Veri snapshot alındı (v2.0)

Öğleden sonra:
  - Üç eksen (DATABASE + MODEL + TRADER) tanımlandı
  - Versioning + export + data dictionary
  - Model registry JSON + Catalog md

Akşam:
  - app_pro.py — Bloomberg terminal estetiği
  - iddia.com link entegrasyonu (trader bahis koyabilsin)
  - Platt kalibrasyon (KG + A/Ü) ile model gap %14 → %3.5
  - v2.1 snapshot
```

---

## 🎁 KULLANICI İÇİN YENİ ÖZELLİKLER

### Pick Card'larda
- ▶ **İDDAA'ya GİT** butonu (yeşil, prominent) → lig-spesifik iddia.com URL
- 🔍 **Maç Detay** butonu → Google search "iddaa [HOME] [AWAY]"
- Tarih formatı: "24 May Paz" (Türkçe haftalı)

### Lig-spesifik iddia.com URL'leri
- T1: `iddaa.com/program/futbol/turkiye-trendyol-super-lig`
- E0: `iddaa.com/program/futbol/ingiltere-premier-league`
- SP1: `iddaa.com/program/futbol/ispanya-la-liga`
- D1: `iddaa.com/program/futbol/almanya-bundesliga`
- I1: `iddaa.com/program/futbol/italya-serie-a`
- F1: `iddaa.com/program/futbol/fransa-ligue-1`

### Data Excellency
- Snapshot list otomatik UI'da (Data sayfası)
- Coverage heatmap (lig × sezon)
- KPI dashboard

### Model Registry
- 13 model card grid
- Status filter (VALIDATED/PROTOTYPE/DEPRECATED)
- Bonferroni status pills (⭐⭐⭐)

---

## 🚀 SIRADAKİ ŞANSLAR (Tartışılacak)

1. **SaaS Aşaması** — Multi-user auth + Next.js production (kullanıcı işaret etti)
2. **CLV Live Tracking** — Her pick için canlı CLV
3. **FotMob T1 xG scraper** — TRIVOX'un xG açığı
4. **Walk-forward proper DC** — Komite A2 cevabı
5. **iddaa.com KG odds scraper** — KG pazarında market_p yok
6. **Telegram bot** — opsiyonel (kullanıcı zaten cowork master ile halletti)

Öncelik kullanıcıya açık.

---

## 📁 BU SPRINTTE OLUŞAN DOSYALAR

```
RAPOR/
  v2_UNUTMA_NOTU_3_EKSEN.md
  v2_UCUNCU_PILLAR_EXCELLENCY.md
  v2_SPRINT_OZETI_28_MAY.md ← bu

02_VERI/
  db_versioning.py
  db_export.py
  generate_data_dictionary.py
  DATA_DICTIONARY.md
  refresh_2526_full.py
  audit_2526_uniformity.py
  apply_platt_calibration.py
  snapshots/
    v2.0_20260528_1624/
    v2.1_20260528_1654/
  exports/
    csv_20260528_1625/

03_MODELLER/MODEL_REGISTRY/
  model_registry.json
  MODEL_CATALOG.md

08_AI_TRADER/
  app_pro.py (Bloomberg estetik UI)
  app.py (eski MVP)
```

---

## ✨ TEK CÜMLE ÖZET

> **3 eksen mimarisi kuruldu, 10 silah katalogu hazır, borsa-grade UI canlı, kalibrasyon ile model gerçeklere oturdu.**

**Devam ediyoruz. SaaS'a doğru.**
