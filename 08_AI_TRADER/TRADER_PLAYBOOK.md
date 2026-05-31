# 🧠 TRADER PLAYBOOK — AI Trader Destek Sistemi
## Database Çıktıları, Modeller ve Karar Kılavuzu

**Versiyon:** v2.1 (28 Mayıs 2026)  
**Hedef Kullanıcı:** Trader (insan) + AI Agent (sistem)  
**Öz:** Bu döküman, sistemin neyi bilebileceğini, neyi üretemeyeceğini ve kararların nasıl alınacağını tanımlar.

---

## 1️⃣ VERİ ALTYAPISI — Ne Biliyoruz?

### Temel Tablo: `matches_v2`
```
19,198 settled maç  →  6 lig × 5 sezon (2020-21 → 2025-26)
30+ unsettled maç   →  iddaa.com canlı tarama
```

| Lig Kodu | Lig Adı | Sezonlar | Maç Sayısı |
|---|---|---|---|
| **T1** | Türkiye Süper Lig | 2020-26 | ~1,800 |
| **E0** | İngiltere Premier League | 2017-26 | ~3,420 |
| **D1** | Almanya Bundesliga | 2017-26 | ~2,754 |
| **SP1** | İspanya La Liga | 2017-26 | ~3,420 |
| **I1** | İtalya Serie A | 2017-26 | ~3,420 |
| **F1** | Fransa Ligue 1 | 2017-26 | ~3,042 |

### Odds Kaynakları
| Kaynak | Ne Verir | Kapsam |
|---|---|---|
| **Football-Data.co.uk** | Closing odds (1X2 + A/Ü) | Tarihsel arşiv |
| **iddaa.com** | Canlı odds (1X2 + A/Ü + KG + İY/MS + AH) | Bugün→ileri |
| **Understat** | xG (beklenen gol) per match | E0, D1, SP1, I1, F1 |

### Kalibrasyon Durumu
```
Platt calibration uygulandı:
  - KG (BTTS) modeli:  gap %14 → %3.5  ✅
  - A/Ü 2.5 modeli:    gap  %5.7 → %2.5 ✅
  - 1X2 modeli:        raw DC, henüz kalibre değil
```

---

## 2️⃣ MODEL ARSENAL — 10 Silah

### VOX Ailesi — 1X2 Seçici Keskin Nişancı

| Model | Lig | n (pick) | hit% | Bonferroni | Ne Zaman Ateş Eder |
|---|---|---|---|---|---|
| **DUOVOX** ⭐ | E0 + SP1 | 1,807 | %62 | p=0.0000 | Q5 ≥ 0.48 + Agree2+ |
| **TRIOVOX** | E0+SP1+D1 | 2,529 | %60 | p=0.0001 | Q5 ≥ 0.48 + Agree2+ |
| **MONOVOX-E0** | E0 | 881 | %65 | p=0.0017 | Q5 ≥ 0.48 + Agree2+ |
| **TRIVOX** | T1 | 22 | **%82** | p=0.0071 | Q5 ≥ 0.48 + Agree2+ |
| **MONOVOX-SP1** | SP1 | 926 | %55 | p=0.0081 | Q5 ≥ 0.48 + Agree2+ |

> **Q5:** Top quintile score_v14 (≥ 0.48)  
> **Agree2+:** En az 2 bağımsız sinyal aynı yönü işaret ediyor

### MARKET Ailesi — Multi-Market, Platt Kalibre

| Model | Lig | Yön | n | hit% | Edge |
|---|---|---|---|---|---|
| **OU25-D1-Over** ⭐ | D1 | Üst 2.5 | 178 | %59 | **+%4.18** |
| **OU25-E0-Under** | E0 | Alt 2.5 | 297 | %41 | +%3.55 |
| **OU25-T1-Under** | T1 | Alt 2.5 | 240 | %45 | +%1.60 |
| **OU25-SP1-Over** | SP1 | Üst 2.5 | 324 | %40 | +%1.54 |
| **BTTS-D1-Var** | D1 | KG Var | 497 | %64 | kalibre ✅ |
| **BTTS-T1-Var** | T1 | KG Var | 396 | %64 | kalibre ✅ |

---

## 3️⃣ SİNYAL SİSTEMİ — 9 Bağımsız Lens

Her maç için `signal_snapshots` tablosunda 9 sinyal üretilir.  
Her sinyal: **+1 (Favori tarafı destekle)** veya **-1 (Karşı git)** veya **0 (Kararsız)**

| Sinyal Kodu | İsim | Kaynak | Yöntem |
|---|---|---|---|
| `s_anomaly` | Odds Anomaly | iddaa.com odds hareketi | Closing vs Opening fark |
| `s_model` | DC Model | Dixon-Coles Poisson | Lambda_home vs Lambda_away |
| `s_xg` | xG | Understat son 5 maç | xG-based form |
| `s_form` | Form | Football-Data puan | Son 5 maç gol/puan avg |
| `s_sharp` | Sharp Money | Odds farkı | Pinnacle vs piyasa |
| `s_invvar` | Inverse Var | Odds volatilite | Market belirsizlik |
| `s_shots` | Shots | Football-Data | Isabetli şut ortalaması |
| `s_referee` | Referee | Football-Data | Hakem sarı/kırmızı profili |
| `s_cards` | Cards | Football-Data | Takım kart geçmişi |

### `score_v14` — Ana Skor
```
score_v14 = weighted average(9 sinyal)
Ağırlıklar: anomaly=0.20, model=0.20, xg=0.15, form=0.10,
             sharp=0.10, invvar=0.05, shots=0.10, referee=0.05, cards=0.05

Yorumlama:
  score ≥ 0.48  →  Q5 = "GÜÇLÜ SİNYAL" (top quintile)
  score ≥ 0.35  →  Orta sinyal
  score <  0.20  →  Zayıf, geç
```

### `agree_count` — Konsensüs Sayısı
```
agree_count = kaç sinyal aynı yönü gösteriyor

agree_count ≥ 3  →  Tier 1 (en güvenilir)
agree_count = 2  →  Tier 2 (kabul edilebilir)
agree_count = 1  →  Tier 3 (tek sinyal, riskli)
agree_count = 0  →  PAS GEÇ
```

---

## 4️⃣ KALİBRE OLASILIKLAR — Nasıl Oku?

Tablodan doğrudan okuma:

| Kolon | Ne Demek | Nasıl Kullan |
|---|---|---|
| `fp_btts_model_yes_cal` | KG Var olasılığı (kalibre) | > 0.58 → KG Var değerlendirilebilir |
| `fp_btts_model_no_cal` | KG Yok olasılığı (kalibre) | > 0.60 → KG Yok değerlendirilebilir |
| `fp_ou_model_over_cal` | Üst 2.5 olasılığı (kalibre) | > 0.58 → Üst değerlendirilebilir |
| `fp_ou_model_under_cal` | Alt 2.5 olasılığı (kalibre) | > 0.60 → Alt değerlendirilebilir |

### Piyasa Implied Probability vs Model Probability
```
EDGE = fp_model - fp_market

fp_market = (1/odd) / overround  ← piyasanın ne düşündüğü
fp_model  = kalibre model çıktısı ← bizim ne düşündüğümüz

EDGE > +0.04  →  Değer var, oyna
EDGE < +0.02  →  Değer yok, pas geç
```

---

## 5️⃣ KUPON KARAR AĞACI

```
ADIM 1: Maç Filtrele
    └─ is_settled = 0 (gelecek maç)
    └─ league_code IN ('T1','E0','D1','SP1','I1','F1')
    └─ kickoff_utc BETWEEN now AND now+72h

ADIM 2: Sinyal Kontrol
    └─ score_v14 >= 0.48  →  Q5 eşiği
    └─ agree_count >= 2   →  Konsensüs eşiği

ADIM 3: Market Seç
    ├─ 1X2 pick: dir_consensus işaret ettiği yön (1 veya 2)
    ├─ KG Var:   fp_btts_model_yes_cal > 0.58 VE s_btts_model_cal = +1
    ├─ Alt 2.5:  fp_ou_model_under_cal > 0.60 VE s_ou_model_cal = -1
    └─ Üst 2.5:  fp_ou_model_over_cal > 0.58 VE s_ou_model_cal = +1

ADIM 4: Kupon Oluştur
    ├─ K=1: Tek güvenli pick (en yüksek score)
    ├─ K=2: İki pick (farklı maçlar, farklı market)
    └─ K=3: Üç pick (ASLA aynı hafta 2 K=3 yapma)

ADIM 5: Risk Kontrol
    └─ Max bankroll %5 tek kupona
    └─ K=3 için max %2 bankroll
    └─ Haftalık kayıp %15'i aşarsa dur
```

---

## 6️⃣ KUPON TÜRÜ KARŞILAŞTIRMASI

| Tip | Katsayı Hedefi | Hit Olasılığı | Bankroll % | Ne Zaman? |
|---|---|---|---|---|
| **K=1 Tek** | 1.30–1.60 | %60–75 | max %5 | score ≥ 0.52, agree ≥ 3 |
| **K=2 Çiftli** | 1.80–2.50 | %40–55 | max %3 | score ≥ 0.48, agree ≥ 2 |
| **K=3 Üçlü** | 2.50–4.00 | %20–35 | max %2 | score ≥ 0.48, agree ≥ 2, farklı liglerden |
| **Multi-Market** | 1.60–2.20 | %35–50 | max %3 | BTTS/OU kalibre edge > %4 |

---

## 7️⃣ RİSK YÖNETİMİ — Kırmızı Çizgiler

```
⛔ ASLA YAPMA:
  - Tek kupona bankrolün %10'undan fazla yatırma
  - Haftada 2'den fazla K=3 kupon
  - score_v14 < 0.35 olan maça oynama
  - agree_count = 0 maça oynama
  - KG market: fp_btts_cal < 0.55 ise geç
  - A/Ü market: edge < %2 ise geç

✅ HER ZAMAN YAP:
  - Haftalık P&L takibi (pnl_top3_v13 kolonundan)
  - 3 ardışık kayıptan sonra 1 hafta bekle
  - K=3 kombinasyonunda min 2 farklı lig
  - Yeni sezon başında ilk 4 haftayı gözlemle, oynama
```

---

## 8️⃣ MODEL ÇEVRİMİ — Canlı Maçlarda Ne Olur?

```
1. iddaa.com scraper çalışır (fetch_iddaa_live.py)
   ↓
2. matches_v2'ye unsettled maç eklenir (is_settled=0)
   ↓
3. [⚠️ EKSİK ADIM] signal_snapshots üretimi
   → Gelecek maçlar için DC modeli çalıştırılmalı
   → Bu henüz otomatikleşmedi
   ↓
4. Kalibrasyon uygulanır (fp_*_cal kolonları)
   ↓
5. UI'da score_v14 ve pick önerisi görünür
   ↓
6. Maç bitti → is_settled=1, result_1x2 yazılır
   ↓
7. PnL güncellenir (pnl_top3_v13 kolonuna)
```

> **Kritik boşluk:** Gelecek maçlar için `signal_snapshots` üretimi henüz tam otomatik değil.  
> Bu, Ağustos 2026'da yeni sezon başlamadan önce tamamlanacak.

---

## 9️⃣ SEZONLUK TAKVİM — Ne Zaman Ne Olur?

### 2026-27 Sezonu Beklenen Fikstür Tarihleri

| Lig | Beklenen Başlangıç | İlk Maç Haftası |
|---|---|---|
| **D1** Bundesliga | ~1 Ağustos 2026 | Hft 1 |
| **F1** Ligue 1 | ~8 Ağustos 2026 | Hft 1 |
| **T1** Süper Lig | ~8-15 Ağustos 2026 | Hft 1 |
| **E0** Premier League | ~15 Ağustos 2026 | Hft 1 |
| **SP1** La Liga | ~15-22 Ağustos 2026 | Hft 1 |
| **I1** Serie A | ~22-29 Ağustos 2026 | Hft 1 |

### Yeni Sezon Protokolü
```
Hft 1-4:   GÖZLEM MODU — Oynama, veri topla
            (Dixon-Coles lambda'ları henüz kararlı değil)

Hft 5-8:   DÜŞÜK BAHIS — K=1 max, %2 bankroll
            (Form ve lambdalar oturmaya başlıyor)

Hft 9+:    NORMAL OPERASYON — Tüm kupon tipleri
            (Yeterli sezon içi veri var)

Hft 28+:   DİKKATLİ — Sezon sonu düzensizlik
            (Küme düşme/şampiyonluk stresi)
```

---

## 🔟 DATABASE SORGULARI — Trader İçin Hazır

### Bu Haftanın Picks'i
```sql
SELECT 
    m.league_code, m.matchday, m.kickoff_utc,
    m.home_team, m.away_team,
    m.closing_1, m.closing_X, m.closing_2,
    s.score_v14, s.agree_count, s.dir_consensus,
    s.fp_btts_model_yes_cal, s.fp_ou_model_over_cal
FROM matches_v2 m
JOIN signal_snapshots s ON s.iddaa_match_id = m.external_id_iddaa
WHERE m.is_settled = 0
  AND s.score_v14 >= 0.48
  AND s.agree_count >= 2
ORDER BY s.score_v14 DESC;
```

### Bu Sezon P&L Özeti
```sql
SELECT
    league_code,
    COUNT(*) as total_picks,
    SUM(CASE WHEN pnl_top3_v13 > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(AVG(pnl_top3_v13), 2) as avg_pnl,
    ROUND(SUM(pnl_top3_v13), 2) as total_pnl
FROM signal_snapshots
WHERE settled = 1 AND score_v14 >= 0.48 AND agree_count >= 2
GROUP BY league_code;
```

### KG Market Edge
```sql
SELECT
    league_code,
    COUNT(*) as n,
    ROUND(AVG(fp_btts_model_yes_cal - (1/odd_btts_yes / (1/odd_btts_yes + 1/odd_btts_no))), 4) as kg_edge
FROM signal_snapshots
WHERE odd_btts_yes IS NOT NULL AND fp_btts_model_yes_cal IS NOT NULL
GROUP BY league_code
HAVING n >= 30
ORDER BY kg_edge DESC;
```

---

## 📌 ÖZET — Tek Sayfa Hatırlatma

```
SISTEM = DATA + MODEL + EDGE

DATA:    19K tarihsel maç | 6 lig | 5 sezon | xG + odds + stats
MODEL:   DC Poisson + Platt kalibrasyon | 10 üretim modeli
EDGE:    Kalibrasyon bazlı (fp_model - fp_market > %4)

ÇALIŞTIR = score ≥ 0.48 VE agree ≥ 2 VE edge > %4
DUR      = 3 art. kayıp VE/VEYA agree = 0 VE/VEYA sezon hft 1-4
```

---

*Son güncelleme: 28 Mayıs 2026 — v2.1 (Platt + KG odds + iddaa.com scraper)*
