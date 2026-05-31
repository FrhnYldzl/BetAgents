# BAHIS AGENT — ÜÇLÜ EXCELLENCY MİMARİSİ

**Tarih:** 2026-05-28
**Felsefe:** Üç sütun, eşit önem. Birinin zayıflığı diğerleri sıfırlar.

> **"Sürdürülebilir trader edge sadece DATA + MODEL + TRADE üçlüsü mükemmel olduğunda doğar."**

---

## 🎯 ÜÇ SÜTUN — Eşdeğer Önem

```
        ╔══════════════════════════════════════════╗
        ║         AI TRADER DESTEK SİSTEMİ          ║
        ║   (Digital Twin Trader — Sürdürülebilir)  ║
        ╚════════════════╤══════════════════════════╝
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
       ▼                 ▼                 ▼
  ┌─────────┐       ┌─────────┐       ┌─────────┐
  │  DATA   │       │  MODEL  │       │  TRADE  │
  │EXCELLEN.│       │EXCELLEN.│       │EXCELLEN.│
  └─────────┘       └─────────┘       └─────────┘
```

---

## 1️⃣ DATA EXCELLENCY

**Tanım:** Her veri kaynağı temiz, tam, tutarlı, sürekli güncel ve **diğer sezonlarla uyumlu**.

### Standartlar
| Boyut | Standart | Kontrol Mekanizması |
|---|---|---|
| **Bütünlük** | %95+ coverage her alan | quality_score, has_*_flag |
| **Tutarlılık** | Tüm sezonlar aynı şema | uniformity audit (lig × sezon) |
| **Güncellik** | <24 saat data lag (live) | timestamp + version tag |
| **Doğruluk** | 0 duplicate, 0 leakage | anomaly_detection + timing audit |
| **Ortogonalite** | Yeni kaynak edge artırmalı | correlation matrix kontrolü |

### Kritik Eksik Alanlar (Bilinen)
- ❌ T1 xG **%0** (FotMob/Sofascore scraper bekliyor)
- ❌ KG closing odds **yok** (iddaa scraper bekliyor)
- ⚠️ 2025-26 anomaly **%50** (CSV opening odds çekilmedi → BUGÜN düzeltiliyor)
- ⏳ Sakatlık verisi **eski** (Transfermarkt scraper bekliyor)
- ⏳ Pinnacle opening odds **yok** (premium API kararı bekliyor)

### Audit Mekanizması
- **Haftalık**: matches_v2 quality audit (per lig × sezon)
- **Aylık**: Cross-source uniformity (signal_snapshots vs matches_v2)
- **Yeni veri kaynağı eklendiğinde**: Ortogonalite testi (korelasyon < 0.4)

### KPI
- Quality score ≥ %94
- Tüm liglerde tüm sezonlar aynı sinyal kapsamı (uniformity gap ≤ %5)
- Yeni kaynak entegrasyonu < 1 hafta

---

## 2️⃣ MODEL EXCELLENCY

**Tanım:** Modeller **istatistiksel anlamlı, kalibre, sürdürülebilir, açıklanabilir**.

### Standartlar
| Boyut | Standart | Kontrol Mekanizması |
|---|---|---|
| **İstatistiksel** | Bonferroni p < α/n geçilen ≥3 model | binomial Z + p-value test |
| **Sample yeterlilik** | n ≥ 500 (her model × pazar) | Sample size + CI width |
| **Sezon stabilite** | std ≤ %10 (9 sezon) | per-season hit rate |
| **Kalibrasyon** | Reliability gap ≤ %3 | calibration plot + Brier |
| **Walk-forward** | Out-of-sample %85+ of in-sample | proper time-series CV |
| **Leakage-free** | 0 timing leakage | deterministic timing audit |
| **CLV pozitif** | Picks CLV > %0 (long-term) | matches_v2 opening vs closing |
| **Ortogonal sinyaller** | Sinyaller korelasyon < 0.4 | correlation heatmap |

### Mevcut Skor (V2 19K)
| Boyut | Mevcut | Hedef | Durum |
|---|---|---|---|
| Bonferroni significant | 3/5 model | ≥3 | ✅ |
| Sample (büyük) | DUOVOX 1807 | ≥500 | ✅ |
| Sezon stabilite | std 7-9pp | ≤10pp | ✅ |
| Kalibrasyon (1X2) | %1.1 gap | ≤3 | ✅ |
| **Kalibrasyon (KG)** | %14 gap | ≤3 | ❌ **Platt gerek** |
| Walk-forward | proxy | proper | ⚠ |
| Leakage | 0 | 0 | ✅ |
| CLV | −%2-3 (negatif) | > 0 | ❌ **filtre yanlış** |

### Düzeltme Planı
- Platt scaling (Sprint Kapı 1)
- Walk-forward proper (Sprint Kapı 1)
- FAV → VALUE pivot (CLV pozitif için)

---

## 3️⃣ TRADE EXCELLENCY

**Tanım:** Trader operasyonu disiplinli, risk-aware, sürdürülebilir, **psikolojik dayanıklı**.

### Standartlar
| Boyut | Standart | Kontrol Mekanizması |
|---|---|---|
| **Pozisyon disiplini** | Q5+a2 → ALL-IN, Q3- → PAS | Karar matrisi |
| **Risk yönetimi** | Max stake %5 bankroll, %15 DD limit | Dynamic Kelly + stop-loss |
| **Çeşitlendirme** | Aynı yön ≤ 3 ALL-IN | Concentration check |
| **Vergi optimal** | İkramiye < 66,935 TL/kupon | K-seçimi otomatik |
| **CLV takip** | Her pick'in CLV'si log | matches_v2 ile join |
| **Hit rate izleme** | Beklenen vs gerçek %10 farktan az | Calibration alert |
| **Drawdown disiplini** | −%15 → stake yarı, −%25 → PAS | Risk Guardian Agent |
| **Korelasyon-aware** | Combo bağımsız leg'ler | \|r\| < 0.4 kuralı |
| **Multi-pazar** | 5 pazar paralel | 1X2 + A/Ü + KG + İY + AH |
| **Sezon-içi adaptif** | Hafta 10-18 PAS (devre arası) | Time-aware filter |
| **Kayıt + öğrenme** | Her pick + sonuç log | Learning Agent feedback |

### Mevcut Trader Strateji Stack (V2)

```
┌────────────────────────────────────────────────────────┐
│  10 SİLAH × Q5+agree2 SELECTIVE SNIPER                 │
├────────────────────────────────────────────────────────┤
│  1X2 Pazarı (5 model)                                  │
│   - TRIVOX (T1)         hit %82, p=0.0071              │
│   - DUOVOX (E0+SP1)     Bonferroni ⭐⭐⭐               │
│   - TRIOVOX             Bonferroni ⭐⭐⭐               │
│   - MONOVOX-E0          Bonferroni ⭐⭐⭐               │
│   - MONOVOX-SP1         p=0.0081 (%1)                  │
│                                                        │
│  A/Ü 2.5 Pazarı (lig-spesifik)                        │
│   - OU25-D1-Over        hit %61, +%3.09                │
│   - OU25-E0-Under       hit %43, +%5.98 ⭐⭐           │
│                                                        │
│  KG Pazarı (lig-spesifik)                              │
│   - BTTS-D1-Var         hit %61, +%3.58                │
│   - BTTS-SP1-Yes/No     hit %58/55, +%6.25/6.73 ⭐⭐    │
│   - BTTS-I1-Yok         hit %47, +%4.64                │
└────────────────────────────────────────────────────────┘
```

### Operasyonel Mekanizmalar
- **Haftalık rutin** (Pzt-Paz akış): TRADER_HAFTALIK_MANUEL.md
- **Pozisyon hesabı**: Dynamic Kelly + Q-tier
- **Sistem bahis**: 2/3, 3/4 sistem (varyans düşürme)
- **Vergi optimizasyon**: K-seçimi otomatik

---

## 🔗 ÜÇLÜ İLİŞKİ (Sinerji)

```
DATA + MODEL → İstatistiksel kanıt (Bonferroni)
MODEL + TRADE → Operasyonel edge (Q5+a2 sniper)
DATA + TRADE  → Reproducibility (her pick versiyonlu)
ALTı + UCü   → Sürdürülebilir AI Trader Destek
```

### Birinin Zayıflığı Diğerleri Sıfırlar
- **Data zayıf**: Model overfit, edge sahte → Trade ROI negatif
- **Model zayıf**: Yanlış pick, hit rate düşük → Trade kayıp
- **Trade disiplinsiz**: Doğru sinyal, yanlış stake → Bankroll bitik

---

## 📊 ŞU ANKİ DURUM — Üçlü Pillar Skoru

| Sütun | Mevcut Skor | Hedef | Durum |
|---|---|---|---|
| **DATA EXCELLENCY** | 7/10 | 9/10 | 🟡 İyileşiyor |
| **MODEL EXCELLENCY** | 6/10 | 9/10 | 🟡 V2 retrain ile |
| **TRADE EXCELLENCY** | 7/10 | 9/10 | 🟡 Operasyon kurulu |

**DATA bilinen eksikler:**
- 2025-26 anomaly %50 (BUGÜN düzeltiliyor)
- T1 xG %0 (sıra)
- KG closing odds yok (sıra)

**MODEL bilinen eksikler:**
- KG Platt kalibrasyon yok
- A/Ü >%20 edge bölgesi overconfident
- CLV negatif (filtre FAV→VALUE pivot bekliyor)

**TRADE bilinen eksikler:**
- Live shadow run henüz başlamadı
- Telegram/notifier yok
- Sistem bahis otomasyonu yok

---

## 🚀 PRENSİPLER — Her İş Bu Süzgeci Geçecek

Her yeni iş şu üç soruyu sormalı:
1. **DATA**: Bu iş veri kalitesini (bütünlük + tutarlılık + ortogonalite) artırıyor mu?
2. **MODEL**: Bu iş istatistiksel anlamlılık + kalibrasyon + CLV iyileştiriyor mu?
3. **TRADE**: Bu iş trader'ın operasyonel disiplinini + risk yönetimini iyileştiriyor mu?

**En az 2 sütunu birden iyileştiren işler öncelikli.**

---

## 🎯 ŞU AN — Üçlü Lens İle 2025-26 Refresh

**SORUN:** 2025-26 sezonunda anomaly sinyali %50 boş (CSV opening odds eksik kaydedildi).

**ÜÇLÜ ETKİ:**
- **DATA**: Uniformity %25 → %95 hedef (KRİTİK)
- **MODEL**: V2 retrain için temiz sample (KRİTİK)
- **TRADE**: 2025-26 final validation (sezon bitti, Trade Excellency için altın fırsat)

→ **3/3 etki: ÖNCELİKLİ İŞ. Şimdi çalıştırılıyor.**
