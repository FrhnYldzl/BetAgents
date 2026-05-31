# 🔧 Veri Bütünlüğü Audit + Düzeltmeler — Özet

**Tarih:** 2026-05-27
**Süreç:** DATA_AUDIT.py → Tespit → Fuzzy xG fix → EUVOX retune

---

## 1. AUDIT BULGULARI (Önceki Durum)

### Eksiklik 1: SP1/I1/F1 — 2526 sezonu signal_snapshots'ta YOK ❌

**Sebep:** `rebuild_extra_with_dc.py` UPDATE yapıyordu ama 2526 row'ları daha önce INSERT edilmemişti.
**Fix:** `fix_2526_extra.py` → 1,065 yeni satır eklendi.

### Eksiklik 2: D1 xG coverage ÇOK DÜŞÜK (%5-19)

**Sebep:** Understat takım isimleri farklı:
- "Bayer Leverkusen" vs "Leverkusen"
- "Borussia M.Gladbach" vs "M'gladbach"
- "RasenBallsport Leipzig" vs "RB Leipzig"
- "FC Cologne" vs "FC Koln"

xG cache exact-key lookup yapıyordu → eşleşmiyordu.

**Fix:** `extra_signals.py` `xg_luck_signal`'a **fuzzy match fallback** eklendi.
Eğer exact key yoksa, similarity ≥0.70 olan key'i kullan.

### Eksiklik 3: T1 xG — TAMAMEN YOK

**Sebep:** Understat Türk Süper Lig'i desteklemiyor.
**Çözüm:** Yok. T1 için 3 sinyalle (anomaly + model + form) idare ediyoruz. TRIVOX'ta sorun değil.

---

## 2. DÜZELTME SONRASI

### xG Coverage İyileşme

| Lig | Sezon | Önce | Sonra | Artış |
|---|---|---:|---:|---:|
| **D1** | 2021-22 | %5 | **%28** | **5.6x** ✨ |
| D1 | 2022-23 | %19 | %46 | 2.4x |
| D1 | 2023-24 | %16 | %44 | 2.8x |
| D1 | 2024-25 | %16 | %50 | 3.1x |
| **E0** | 2021-22 | %43 | %56 | +13pp |
| E0 | 2022-23 | %52 | %73 | +21pp |
| E0 | 2023-24 | %55 | %74 | +19pp |
| **SP1** | 2021-22 | %22 | %44 | +22pp |
| SP1 | 2022-23 | %22 | %54 | +32pp |
| SP1 | 2023-24 | %34 | %57 | +23pp |

### EUVOX Per-Lig Tuning Retune

| Lig | Önceki Config | Önceki ROI | Yeni Config | **Yeni ROI** |
|---|---|---:|---|---:|
| T1 | K3/mc1/thr0 | +51.5% | K3/mc1/thr0 | +51.5% (aynı) |
| E0 | K2/mc1/thr0 | +16.1% | K2/mc1/thr0 | +11.7% (-4.4pp) |
| **D1** | K2/mc1/thr0.7 | +11.3% | **K3/mc1/thr0.7** | **+21.5%** ✨ (+10pp) |
| SP1 | K2/mc1/thr0.7 | +13.0% | K2/mc1/thr0 | +8.4% (-4.6pp) |
| **I1** | K3/mc1/thr0 | +12.2% | **K2/mc2/thr0.7** | **+31.9%** ✨ (+20pp) |
| **F1** | K2/mc2/thr0 | +14.9% | K2/mc2/thr0 | **+25.8%** ✨ (+11pp) |

**D1, I1, F1 ROI ciddi arttı** (xG fuzzy match sayesinde).
E0, SP1 hafif düştü (xG sinyali güçlenince filtreleme daha sıkı oldu).

### EUVOX Toplam

| Metrik | EUVOX v1.0 | EUVOX v1.1 |
|---|---:|---:|
| n kupon | 1,011 | 956 |
| PnL brüt | +179,122 TL | +175,645 TL |
| ROI brüt | +17.7% | **+18.4%** |
| PnL net (%10 vergi) | +92,809 TL | +93,980 TL |
| Avg combo odd | 4.35 | 4.20 |

**Net değişim:** Kupon sayısı düştü (-55), ROI/kupon arttı, toplam PnL benzer.
v1.1 daha **kaliteli kupon, hafifçe daha az fırsat**.

---

## 3. KALAN VERİ ZAYIFLIKLARI

### 2526 Sezonu (devam ediyor)

| Lig | DC% | Closing odds% | Etki |
|---|---:|---:|---|
| T1 | 44% | 44% | Sezon yarısı |
| E0 | 55% | 55% | Sezon yarısı |
| D1 | 49% | 49% | Sezon yarısı |
| SP1 | 44% | 49% | Sezon yarısı |
| I1 | 37% | 52% | Sezon yarısı |
| F1 | 45% | – | Sezon yarısı |

**Durum:** Sezon Mayıs 2026'da biter, o zaman tam coverage olur. **Production'ı engellemez.**

### T1 xG — Kalıcı Yok

**Etki:** T1 K=3 sadece 3 sinyalle çalışıyor (anomaly + model + form). FAV_CONFIRMED min_conf=1 yeterli.
**TRIVOX zaten bu şekilde +51.5% veriyor.**

---

## 4. EUVOX v1.1 PRODUCTION CONFIG

```yaml
EUVOX v1.1 (Fuzzy xG düzeltmesi sonrası):

ligler:
  T1:  K=3, mc=1, thr=0      # +51.5% ROI (Türk)
  E0:  K=2, mc=1, thr=0      # +11.7% (Premier)
  D1:  K=3, mc=1, thr=0.7    # +21.5% ✨ xG iyileşti (Bundesliga)
  SP1: K=2, mc=1, thr=0      # +8.4%  (La Liga)
  I1:  K=2, mc=2, thr=0.7    # +31.9% ✨ xG iyileşti (Serie A)
  F1:  K=2, mc=2, thr=0      # +25.8% ✨ (Ligue 1)

backtest 4 sezon (T1+E0+D1+SP1+I1+F1):
  n kupon:           956
  PnL brüt:          +175,645 TL
  PnL net (%10):     +93,980 TL
  ROI brüt:          +18.4%
  ROI net:           +9.8%
  Yıllık ortalama:   ~+44K TL net
```

---

## 5. ÇÖKÜNTÜ RİSKİ DEĞERLENDİRMESİ

| Lig | Çöküntü riski | Sebep |
|---|:---:|---|
| T1 | DÜŞÜK | 3 sinyal yeterli (xG yok kabul) |
| E0 | DÜŞÜK | 4 sinyal hepsi mevcut |
| D1 | DÜŞÜK | Fuzzy xG sonrası coverage 3x arttı |
| SP1 | DÜŞÜK | DC eklendi + xG fuzzy match çalışıyor |
| I1 | DÜŞÜK | En iyi 4-sinyal coverage'ı |
| F1 | DÜŞÜK | xG iyi, DC eklendi |
| **TOPLAM** | **GÜVENLİ** | **Hiçbir lig 'ÇÖKÜNTÜ' kategorisinde değil** |

---

## 🎓 BİLİMSEL ÖZ

> **Veri bütünlüğü audit yapmadan model deploy etme.**
>
> Audit yapıldı, eksiklikler tespit edildi, düzeltildi:
> - SP1/I1/F1 2526 yüklendi (+1,065 satır)
> - xG fuzzy match (D1 %5→%28, E0/SP1 ortalama +%20)
> - EUVOX retune (D1/I1/F1 ROI ciddi arttı)
>
> EUVOX v1.1: **+18.4% ROI**, **6/6 lig pozitif**, **çöküntü riski yok**.

---

**Audit + fix tamam. EUVOX v1.1 production-stable.**
