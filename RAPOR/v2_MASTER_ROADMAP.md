# MASTER ROADMAP v0.2 — AI TRADER DESTEK / DIGITAL TWIN TRADER

**Tarih:** 2026-05-28
**Versiyon:** v0.2 (UI eklendi, multi-agent + data edge entegre)
**Hedef:** Dünyanın en zeki + pratik + kazançlı TRADER AI sistemi
**Sezon:** 2026-27 lig fixture'larında canlı

---

## 1) SİSTEM MİMARİSİ — Yüksek Seviye

```
┌─────────────────────────────────────────────────────────────────┐
│                      TRADER (insan)                              │
│   Web / Mobile / Telegram / Voice ile etkileşim                  │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│            FRONTEND — UI/UX KATMANI                              │
│   Next.js + PWA + Telegram Bot + Voice                           │
│   5 ana ekran: Hafta / Pick Detay / Strateji / Sezon / Geçmiş    │
└────────────────────────┬────────────────────────────────────────┘
                         ↓ (FastAPI REST + WebSocket)
┌─────────────────────────────────────────────────────────────────┐
│         ORCHESTRATOR — Ana AI Trader (Claude/GPT)                │
│   Niyet anlama → agent çağrı → sentez → çıktı                   │
└────────────────────────┬────────────────────────────────────────┘
                         ↓ (parallel + sequential calls)
┌─────────────────────────────────────────────────────────────────┐
│            10 SPECIALIST AGENT × 79 SKILL                        │
│  ┌───────────┬───────────┬───────────┬───────────┐               │
│  │ Data      │ Team      │ Player    │ Market    │               │
│  │ Hunter    │ Analyst   │ Analyst   │ Analyst   │               │
│  ├───────────┼───────────┼───────────┼───────────┤               │
│  │ Match     │ Model     │ Strategy  │ Risk      │               │
│  │ Context   │ Ensemble  │ Optimizer │ Guardian  │               │
│  ├───────────┴───────────┴───────────┴───────────┤               │
│  │     Learning Agent  ←→  Explainer Agent       │               │
│  └────────────────────────────────────────────────┘               │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│              DATA LAYER — Sürekli besleyen                       │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  12+ KAYNAK:                                            │     │
│  │   FD / Understat / FotMob / Transfermarkt / Sofascore   │     │
│  │   FBRef / Pinnacle / Twitter / OpenWeather / iddaa /    │     │
│  │   Reddit / UEFA fixture                                  │     │
│  │                                                          │     │
│  │  CANONICAL: matches_v2 (PostgreSQL — scale)              │     │
│  │  CACHE: Redis (live odds, prediction)                    │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2) MEVCUT DURUM (Kapı 0 Sonrası)

### ✅ Veri Tabanı
- matches_v2: 19,198 satır (9 sezon × 6 lig)
- Quality gate: %94.4
- 0 duplicate, 0 leakage (T03)
- Multi-market coverage: 1X2 + A/Ü 2.5

### ✅ Model Foundation
- 5 model (TRIVOX, MONOVOX-E0, DUOVOX, TRIOVOX, MONOVOX-SP1)
- 15 model arena testi (T12) — K=1 mantığı kanıtlandı
- Q5+a2 selective sniper paradigması doğrulandı
- TRIVOX K=1 +%2 ROI (Bonferroni sınırda geçti)
- Q5+a2 hit %67-84 (5 model 5 sezonda stabil)

### ✅ Strateji Dokümanları (10 doküman)
1. `v2_MASTER_ROADMAP.md` — **Bu doküman (ana yol haritası)**
2. `v2_HEDEF_DIGITAL_TWIN_TRADER.md` — Vizyon
3. `v2_MULTI_AGENT_MIMARI.md` — 10 agent + 79 skill
4. `v2_DATA_EDGE_STRATEJISI.md` — 12 veri kaynağı
5. `v2_IDDIA_KURALLARI_KUPON_TEKNIKLERI.md` — İddia mekaniği
6. `v2_MULTIMARKET_MODEL_TASARIMI.md` — 5 pazar
7. `v2_UI_UX_MIMARISI.md` — **YENİ — Trader yüzü**
8. `v2_TRADER_HAFTALIK_MANUEL.md` — Operasyonel akış
9. `v2_TRADER_PLAYBOOK_v0_1.md` — Q5+agree2 sniper
10. `v2_KAPI_0_OZET_RAPOR.md` — Komite cevabı

---

## 3) 4-KATMANLI DEVELOPMENT (Backend + Frontend + Agent + Data)

Her sprint **4 paralel iş kolu** içerir:

```
DATA LAYER       MODEL LAYER      AGENT LAYER     UI LAYER
──────────       ───────────      ───────────     ────────
yeni kaynak  →   model improve →  agent build →   ekran inşa
ingest                              skill ekle
quality
```

---

## 4) 12 AY ROADMAP — Quarter-by-Quarter

```
══════════════════════════════════════════════════════════════════════
QUARTER 1 (HAZİRAN-AĞUSTOS 2026)
══════════════════════════════════════════════════════════════════════
TEMA: Foundation + AI Trader v0.1 MVP

  HAFTA 1-2 (HEMEN BAŞLAYACAK):
    ┌─ DATA   : Yeni 19K Kapı 0 smoke test (T01-T12 yeniden)
    ├─ MODEL  : Yönetici özeti v2 (komite cevabı)
    ├─ AGENT  : —
    └─ UI     : —

  HAFTA 3-4:
    ┌─ DATA   : FotMob T1 xG scraper (DATA HUNTER skill)
    ├─ MODEL  : matches_v2 üzerinde TRIVOX/DUOVOX retrain (19K sample)
    ├─ AGENT  : Model Ensemble Agent (Python class wrap)
    └─ UI     : Streamlit MVP — Hafta dashboard ekranı

  HAFTA 5-6:
    ┌─ DATA   : Transfermarkt sakatlık scraper
    ├─ MODEL  : Multi-market A/Ü 2.5 (DC Poisson projector)
    ├─ AGENT  : Strategy Optimizer Agent + Explainer Agent
    └─ UI     : Pick detay ekranı + "Neden bu pick?" açıklaması

  HAFTA 7-8:
    ┌─ DATA   : iddaa multi-snapshot scraper
    ├─ MODEL  : Risk Guardian temel (drawdown + concentration)
    ├─ AGENT  : Risk Guardian Agent
    └─ UI     : Telegram bot temel bildirim

  HAFTA 9-10:
    ┌─ DATA   : api-football premium tier value check
    ├─ MODEL  : CLV pipeline live (her hafta picks için)
    ├─ AGENT  : Learning Agent v0.1 (basit log)
    └─ UI     : Sezon planı ekranı

  HAFTA 11-12:
    ┌─ DATA   : Pinnacle premium API trial (opsiyonel)
    ├─ MODEL  : Live shadow run başlat (Ağustos 2026)
    ├─ AGENT  : Orchestrator (basit niyet sınıflandırma)
    └─ UI     : "AI Trader v0.1 BETA — kapalı kullanıcı sen"

  Q1 ÇIKIŞ: AI Trader v0.1 — Telegram'da haftalık öneri,
            web'de detay ekranı, 5 model çalışır, 2 pazar (MS + A/Ü)

══════════════════════════════════════════════════════════════════════
QUARTER 2 (EYLÜL-KASIM 2026) — 2026-27 sezon başlar!
══════════════════════════════════════════════════════════════════════
TEMA: Veri zenginleşme + Sezon canlı

  HAFTA 13-14: 2026-27 SEZON BAŞLADI
    ┌─ DATA   : Sofascore oyuncu rating ingest
    ├─ MODEL  : İlk gerçek hafta picks (live shadow → canlı)
    ├─ AGENT  : Team Analyst Agent + Match Context Agent
    └─ UI     : Mobile PWA (responsive)

  HAFTA 15-16:
    ┌─ DATA   : FBRef gelişmiş metrics
    ├─ MODEL  : 3. pazar — KG (Karşılıklı Gol) ekle
    ├─ AGENT  : Team Analyst — predict_lineup skill
    └─ UI     : AI Trader sohbet penceresi (Claude API)

  HAFTA 17-18:
    ┌─ DATA   : OpenWeather entegrasyonu
    ├─ MODEL  : 4. pazar — İY (İlk Yarı)
    ├─ AGENT  : Market Analyst (CLV tracker live)
    └─ UI     : Geçmiş + öğrenme ekranı

  HAFTA 19-20:
    ┌─ DATA   : Twitter sentiment trial
    ├─ MODEL  : 5. pazar — AH (Handikap)
    ├─ AGENT  : Match Context — weather + travel
    └─ UI     : Onboarding flow + profile setup

  HAFTA 21-22:
    ┌─ DATA   : Korelasyon matrix tüm 5 pazar
    ├─ MODEL  : Multi-market kombo öneri sistemi
    ├─ AGENT  : Strategy Optimizer — sistem bet öneri
    └─ UI     : Strateji A/B/C karşılaştırma ekranı

  HAFTA 23-24:
    ┌─ DATA   : İlk sezon-içi audit (4 ay sonra)
    ├─ MODEL  : Hit rate vs beklenti karşılaştırma
    ├─ AGENT  : Learning Agent v0.2 (calibration update)
    └─ UI     : Aylık raporda micro-interaction

  Q2 ÇIKIŞ: 5 pazar canlı, 4 ay live shadow tamamlandı,
            FotMob+Transfermarkt+Sofascore+FBRef entegre,
            Aylık ROI ölçüldü (gerçek)

══════════════════════════════════════════════════════════════════════
QUARTER 3 (ARALIK 2026-ŞUBAT 2027) — Devre arası + Derinleşme
══════════════════════════════════════════════════════════════════════
TEMA: Learning Loop + Player Analysis

  HAFTA 25-26: Devre arası (Hafta 10-18 dönemi)
    ┌─ DATA   : Sezon-ortası retrain için data hazır
    ├─ MODEL  : Devre arası kuralı doğrulandı mı? Audit
    ├─ AGENT  : Player Analyst Agent başla
    └─ UI     : Devre arası uyarı bannerı

  HAFTA 27-28:
    ┌─ DATA   : Transfer dönemi etkisi tracking
    ├─ MODEL  : Ocak transferleri sonrası retrain
    ├─ AGENT  : Player Analyst — fatigue + transfer impact
    └─ UI     : Star player impact göstergesi

  HAFTA 29-30:
    ┌─ DATA   : Reddit/forum community signals (deneme)
    ├─ MODEL  : Mikro-edge birikimi ölçümü
    ├─ AGENT  : Learning Agent — pattern recognition
    └─ UI     : Voice komut prototipi

  HAFTA 31-32:
    ┌─ DATA   : —
    ├─ MODEL  : Bayesian ensemble blend
    ├─ AGENT  : Risk Guardian — dynamic Kelly
    └─ UI     : Animasyonlar + micro-interactions

  HAFTA 33-34:
    ┌─ DATA   : Aylık otomatik retrain pipeline
    ├─ MODEL  : Kombo joint probability (kopula)
    ├─ AGENT  : Strategy Optimizer — multi-market kombo
    └─ UI     : Karşılaştırma araçları

  HAFTA 35-36:
    ┌─ DATA   : Veri lineage + reproducibility
    ├─ MODEL  : Sezon ortası audit raporu
    ├─ AGENT  : Explainer Agent — natural language v2
    └─ UI     : Sezon ortası dashboard

  Q3 ÇIKIŞ: Devre arası kuralı doğrulandı, Player Analyst aktif,
            Learning Loop çalışır, Dynamic Kelly canlı

══════════════════════════════════════════════════════════════════════
QUARTER 4 (MART-MAYIS 2027) — Sezon kapanış + V1.0
══════════════════════════════════════════════════════════════════════
TEMA: Production + Multi-User

  HAFTA 37-38:
    ┌─ DATA   : Sezon sonu data full
    ├─ MODEL  : Final sezon raporu
    ├─ AGENT  : —
    └─ UI     : Production polish

  HAFTA 39-40:
    ┌─ DATA   : —
    ├─ MODEL  : Multi-user için model isolation
    ├─ AGENT  : Profile-aware Orchestrator
    └─ UI     : Multi-user auth + onboarding

  HAFTA 41-42:
    ┌─ DATA   : —
    ├─ MODEL  : V1.0 final calibration
    ├─ AGENT  : Full skill catalog stabilization
    └─ UI     : Beta test geri bildirim entegre

  HAFTA 43-44:
    ┌─ DATA   : —
    ├─ MODEL  : Post-mortem 2026-27 sezon
    ├─ AGENT  : V1.0 release prep
    └─ UI     : Production deploy (Vercel + Railway)

  HAFTA 45-46:
    ┌─ DATA   : V2 sezon hazırlığı başlat
    ├─ MODEL  : Lessons learned dokümante
    ├─ AGENT  : Monitoring + alerting
    └─ UI     : User documentation

  HAFTA 47-48:
    ┌─ DATA   : Sezon planı 2027-28 fixture analizi
    ├─ MODEL  : V1.0 STABLE
    ├─ AGENT  : —
    └─ UI     : V1.0 LAUNCH — kapalı çevre (5-10 trader)

  Q4 ÇIKIŞ: AI Trader V1.0 — Production, multi-user,
            voice, Telegram, mobile PWA, 10 agent canlı,
            12 veri kaynağı, 5 pazar, 5 model
```

---

## 5) AY-AY KRİTİK MİLESTONELAR

| Ay | Milestone | Başarı Kriteri | Risk |
|---|---|---|---|
| **HAZ 2026** | Yeni 19K Kapı 0 smoke test | Tüm modeller 19K'da çalışır, V2 retrain meşru | Eski paradigma sonuçlarıyla uyumsuzluk |
| **TEM** | AI Trader v0.1 MVP | Telegram bildirim + web dashboard | Eski Streamlit'in upgrade'i zaman alır |
| **AĞU** | Multi-market A/Ü 2.5 canlı | DC Poisson projector hit >%60 Q5 | Multi-market ilk implement, debug |
| **EYL** | **2026-27 SEZON BAŞLADI** + ilk picks | Live shadow başlar | Sezon başı 4-5 hafta hatalı olabilir |
| **EKİ** | FotMob T1 xG entegre | T1 picks doğruluğu artar | Scraping kırılma riski |
| **KAS** | Multi-market tam — 5 pazar | Aylık 15-25 Q5 pick, hit %65+ | Korelasyon bug'ı |
| **ARA** | Learning Agent v1 | Trader feedback model günceller | Feedback işleme karmaşık |
| **OCA 2027** | Devre arası audit + retrain | Sezon-içi model güncel | Devre arası kuralı yanlış olabilir |
| **ŞUB** | Multi-user beta | 2-3 trader paralel kullanım | Trader profile isolation karmaşık |
| **MAR** | Voice + Player Analyst | Trader telefon ile konuşur | Voice API kalitesi |
| **NIS** | Sezon sonu raporu | Yıllık ROI live (gerçek) | Realize ROI < %3 olursa pivot |
| **MAY** | V1.0 launch | 5-10 trader kapalı çevre | Production stability |

---

## 6) BAŞARI METRİKLERİ — YIL SONU

### Operasyonel (TRADER için)
- ✅ **Aylık ROI:** %3-7 net ortalama (canlı, in-sample değil)
- ✅ **Hit rate (Q5+a2):** %65+ live
- ✅ **Drawdown:** <%20 max
- ✅ **Sample (live):** 50+ pick (12 ay)
- ✅ **CLV ortalama:** > 0 (long-term hedef, ilk yıl -%1 OK)

### Teknik (SİSTEM için)
- ✅ **5 agent canlı** (Orchestrator + Data Hunter + Model Ensemble + Strategy + Risk)
- ✅ **30+ skill aktif**
- ✅ **12 veri kaynağı entegre**
- ✅ **5 pazar canlı** (MS, İY, AH, A/Ü, KG)
- ✅ **Aylık retrain pipeline çalışır**
- ✅ **PSI/drift detection canlı**

### UI (KULLANICI için)
- ✅ **Web + Mobile PWA + Telegram + Voice**
- ✅ **<3 saniye karar süresi** (Pick'i görüntüleme)
- ✅ **Trader memnuniyeti:** 8/10+
- ✅ **Atlanan pick → sonuç compare** ekranı

---

## 7) İŞ HİYERARŞİSİ — Şu An Ne Yapacağız?

```
1. ▶ ŞU AN — Yeni 19K Kapı 0 smoke test (1-2 gün)
   ↓
2. Yönetici özeti v2 (komite cevabı + multi-agent vizyon) (1 gün)
   ↓
3. AI Trader v0.1 MVP iskeleti (1-2 hafta)
   ├─ Model Ensemble Agent
   ├─ Strategy Optimizer Agent
   ├─ Explainer Agent
   └─ Telegram bot
   ↓
4. UI Faz 1 — Streamlit Hafta Dashboard (3-5 gün)
   ↓
5. Multi-market V2 — A/Ü 2.5 (1 hafta)
   ↓
6. FotMob T1 xG scraper (3-5 gün)
   ↓
7. Live shadow run başlat (Ağustos 2026 öncesi)
   ↓
8. 2026-27 SEZON BAŞLA → canlı
   ↓
9. Sürekli iyileştirme döngüsü (sezon boyunca)
```

---

## 8) BU HAFTA BAŞLIYORUZ

### Hemen şimdi (1-2 gün)
**ADIM 1: Yeni 19K Kapı 0 smoke test**
- T01 K=1 baseline (19K üzerinde)
- T02 Walk-forward proxy
- T03 Timing leakage audit
- T04+T05 Kalibrasyon
- T07 Sezon-içi patern
- T08 Avrupa model search
- T09 Trader quintile
- T10 Q5 sezonsal stabilite
- T11b Market baseline
- T12 Historical model arena
- → **Resmi yönetici özeti v2**

### Sonra (2-3 hafta)
**ADIM 2: AI Trader v0.1 MVP iskeleti**
- Python paket yapısı (`ai_trader/`)
- Model Ensemble Agent (mevcut TRIVOX/DUOVOX wrap)
- Strategy Optimizer Agent (Q5+a2 + sistem önerisi)
- Explainer Agent (natural language)
- Telegram bot

**ADIM 3: UI Faz 1 — Streamlit Hafta Dashboard**
- Mevcut Streamlit upgrade
- Modern UI: Tailwind benzeri custom CSS
- Hafta dashboard ekranı (mockup yukarıda)
- Pick detay ekranı

---

## 9) FELSEFE — Tek Cümle Özet

> **"Sürekli besleyen veri + sürekli iyileşen model + sürekli öğrenen agent ekosistemi + trader'ın yanında olan UI = Dünyanın en zeki + pratik + kazançlı TRADER AI."**

Komitenin "Bonferroni 0/19" eleştirisi tek-model paradigmasında doğruydu. Cevabımız:
- **Tek bir test değil** → mikro-edge birikimi
- **Tek bir model değil** → 5 model ensemble
- **Tek bir veri kaynağı değil** → 12 kaynak ortogonal
- **Tek bir karar değil** → sezon boyunca süreç
- **Tek bir kullanıcı değil** → Digital Twin profile-aware

---

## 10) START — ŞIMDI BAŞLIYORUZ

**Komut:** Yeni 19K matches_v2 üzerinde Kapı 0 smoke test (T01-T12) çalıştır. Bu, "yeni paradigma + tüm modeller + yeni veri seti" üçlüsünün ispatı.

**Sonra:** AI Trader v0.1 MVP iskeleti.
**Sonra:** UI Faz 1.
**Sonra:** Multi-market + Veri zenginleşme.
**Sonra:** 2026-27 sezon canlı.

**Bu inşa edilebilir. Şu an başlıyoruz.**
