# 🔒 UNUTMA NOTU — 3 EKSEN GARANTİSİ

**Tarih:** 2026-05-28
**Kategori:** STRATEJİK İLKE (her sprintte tekrar bakılacak)
**Asla unutulmayacak.**

---

## 📍 KULLANICI'NIN TANIMLADIĞI 3 EKSEN

> *"Riske atmamak için söylediğim üç ekseni lütfen:
>  1. DATABASE KUR ve versiyonlayarak geliştir başka proje olur vs. önemli olacaktır SQL CSV EXCEL neyse uyumlu
>  2. GELİNEN MODELLERİN İSİMLERİNİ kullanılacak ve fayda sağlayan modelleri isimlerini amaçlarını neden ve nasıllarını kaydedelim
>  3. Proje ürün olarak TRADER'a fayda sağlamalı maç maç hafta hafta kupon yapabilecek ve belki milyon satır dataya gelen elimizdeki silahları 100+ yapacak bir vizyondan bahsediyorum ama kullanıcı dostu olmalı BORSA aracı gibi sade güvenilir ve tasarım harikası olmalı"*

---

## EKSEN 1️⃣ — DATABASE: TAŞINABİLİR + VERSİYONLU + UYUMLU

### Kritik Gereksinim
- **Taşınabilir**: SQL / CSV / Excel arasında problemsiz export-import
- **Versiyonlu**: Her snapshot zaman damgalı + git-tracked
- **Başka projelerde kullanılabilir**: Şema açık dökümante, foreign key'ler net
- **Yeniden inşa edilebilir**: Veri kaybı sıfır, replay garanti

### Mevcut Durum
- ✅ SQLite (`bahis_agent.db`) — tek dosya, taşınabilir
- ✅ Canonical schema: `matches_v2`, `signal_snapshots`, `team_aliases`, `seasons_meta`, `picks_log_v2`
- ✅ 19,198 satır temel master tablo
- ⚠️ **EKSİK: Otomatik versiyonlama yok**
- ⚠️ **EKSİK: Export adapters (CSV/Excel/Parquet) yok**
- ⚠️ **EKSİK: Schema migration log yok**

### Yapılacaklar (Sprint Veritabanı Mimarisi)
1. `db_versioning.py` — her büyük değişiklikte otomatik snapshot
2. `db_export.py` — CSV/Excel/Parquet export adapters
3. `schema_migrations/` — sıralı SQL migration dosyaları
4. `DATA_DICTIONARY.md` — her tablo + her kolon dokümantasyonu
5. `db_quality_dashboard.py` — günlük data quality KPI

### Standartlar
- Snapshot tetikleyiciler: yeni sezon, yeni model, yeni veri kaynağı
- Versiyon formatı: `v{major}.{minor}.{patch}_{YYYYMMDD}_{snapshot_id}`
- Her tablo: `created_at`, `updated_at`, `version_tag` zorunlu

---

## EKSEN 2️⃣ — MODEL REGISTRY: İSİM + AMAÇ + NEDEN + NASIL

### Kritik Gereksinim
- Üretilen her model bir **kayıt defterinde**
- Her modelin: **İsmi, amacı, ne için varılan kararı, nasıl çalıştığı**
- "Bu model neden var, ne işe yarıyor" sorusu 30 saniyede cevaplanır
- Modeller arası geçiş, karşılaştırma kolay

### Mevcut Modeller (Geçici Liste)
| Sembol | Amaç | Pazar | Lig | Durum |
|---|---|---|---|---|
| **TRIVOX** | T1 Q5+a2 sniper (selective) | 1X2 | T1 | Bonferroni %1 |
| **DUOVOX** | E0+SP1 Q5+a2 sniper | 1X2 | E0+SP1 | Bonferroni ⭐⭐⭐ |
| **TRIOVOX** | E0+SP1+D1 stabil çoklu | 1X2 | E0+SP1+D1 | Bonferroni ⭐⭐⭐ |
| **MONOVOX-E0** | Premier League tek-lig | 1X2 | E0 | Bonferroni ⭐⭐⭐ |
| **MONOVOX-SP1** | La Liga tek-lig | 1X2 | SP1 | %1 |
| **OU25-D1-Over** | Bundesliga Üst 2.5 | A/Ü | D1 | +%3.09 edge |
| **OU25-E0-Under** | Premier League Alt 2.5 | A/Ü | E0 | +%5.98 edge ⭐⭐ |
| **BTTS-D1-Var** | Bundesliga KG Var | KG | D1 | +%3.58 |
| **BTTS-SP1-Var/Yok** | La Liga KG çift yön | KG | SP1 | +%6.25/+%6.73 ⭐⭐ |
| **BTTS-I1-Yok** | Serie A KG Yok | KG | I1 | +%4.64 |

### Yapılacaklar (Sprint Model Registry)
1. `model_registry.json` — her model için tam kayıt
2. `MODEL_CATALOG.md` — insan-okur döküman
3. `model_card_{NAME}.md` — her model için "Model Card" (Google formatı)
4. Versiyonlama: `MODEL.v{major}.{minor}_{YYYYMMDD}`
5. Lifecycle: `PROTOTYPE → VALIDATED → PRODUCTION → DEPRECATED`

### Model Card Standardı (her model için)
```yaml
name: TRIVOX
version: v1.2
status: VALIDATED
created: 2026-04-15
last_updated: 2026-05-28

purpose: "Türk Süper Lig'de selective sniper bahis"
why: "T1 xG verisi yok ama anomaly + DC + form sinyalleri ortogonal"
how: "FAV_CONFIRMED filter + Q5 quintile + agree_count>=2"

input:
  - signal_snapshots tablosu
  - 4 sinyal (anomaly, model, xG, form)
sample: 905 K=1 picks
performance:
  hit_rate: 0.82
  edge_pp: 15.4
  bonferroni_p: 0.0071
caveats:
  - "T1 xG verisi yok, sample küçük (22 Q5+a2)"
  - "Sezon başı 4-5 hafta volatil"
```

---

## EKSEN 3️⃣ — TRADER ÜRÜN: BORSA-GİBİ SADE + GÜVENİLİR + TASARIM HARİKASI

### Kritik Gereksinim
- **Borsa aracı vibe'ı**: Bloomberg Terminal / TradingView / Robinhood
- **Sade**: 5 saniyede ne yapması gerektiğini söylesin
- **Güvenilir**: Risk uyarısı + transparan
- **Tasarım harikası**: Modern, premium, profesyonel
- **Ölçeklenebilir**: Milyon satır data + 100+ silah desteği

### Vizyon
- **Maç bazlı**: Her maç için tüm pazarlar tek görünüm
- **Hafta bazlı**: Pzt'den Paz'a operasyonel plan
- **Kupon mühendisi**: Otomatik A/B/C strateji önerisi
- **Risk dashboard'u**: Drawdown + Kelly + concentration anlık

### Mevcut Durum
- ✅ Streamlit MVP UI (port 8502)
- ✅ 6 ana sayfa: Dashboard, Picks, Arena, Sinyaller, Sezon&CLV, Hakkında
- ✅ Tailwind-vari koyu tema
- ⚠️ **EKSİK: Next.js production frontend**
- ⚠️ **EKSİK: Real-time WebSocket**
- ⚠️ **EKSİK: Mobile PWA**
- ⚠️ **EKSİK: Borsa-gibi candlestick / charts**

### Yapılacaklar (Sprint UI Excellence)
**Faz 1 — Streamlit Pro (1-2 hafta)** ← Mevcut MVP'yi yükselt
- Borsa terminali estetiği (koyu + neon + grid)
- Maç maç görünümü (her pazar yan yana)
- Kupon mühendisi sayfası (drag-drop seçenek)
- Risk panel sticky (bankroll + DD + concentration)

**Faz 2 — Next.js Production (4-6 hafta)** ← Sonraki kademe
- TypeScript + Tailwind + Recharts
- WebSocket real-time odds
- PWA mobile-first
- Sertifika gibi onay akış

**Faz 3 — Premium Polish (6-8 hafta)** ← Tasarım harikası
- Custom animasyonlar (framer-motion)
- Voice komut
- AI sohbet penceresi (orchestrator)
- Multi-trader auth

---

## 🎯 ÜÇ EKSEN — KESİŞİM PRENSİBİ

Her yapılan iş 3 ekseni de **tartışmaya açık olmalı**:
1. Bu iş **DATA**'yi taşınabilir+versiyonlu yapıyor mu?
2. Bu iş **MODEL**'i registry'ye ekliyor mu / güncelliyor mu?
3. Bu iş **TRADER**'a ekran/değer üretiyor mu?

**En az 2 ekseni güçlendiren işler öncelikli.**

---

## 📊 ŞU ANKİ DURUM (28 Mayıs 2026)

| Eksen | Skor | Durum | Eksik |
|---|---|---|---|
| **1️⃣ DATABASE** | 6/10 | SQLite var, versiyonlama yok | Snapshot + export + migration |
| **2️⃣ MODEL** | 5/10 | Modeller var, registry yok | Catalog + Model Cards |
| **3️⃣ TRADER ÜRÜN** | 5/10 | Streamlit MVP, sade değil | Production UI + Polish |

**Hedef:** 3 eksen de 8/10+ olana kadar diğer işlere geçilmesin.

---

## ⚖️ ÇALIŞMA İLKESİ — Her sprint başında bu doküman okunur

Bu **UNUTMA NOTU** projenin **anayasası**dır. Hiçbir karar bu 3 eksenle çelişmemelidir.

Riske atmama prensibi → her sprint sonu **3 eksen kontrol listesi**.
