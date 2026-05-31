# 🎓 YÖNETİCİ ÖZETİ v5 — Final Konsolidasyon

**Versiyon:** v5.0 (T01-T20 + Bonferroni + vergi)
**Tarih:** 2026-05-27
**Format:** Bilimsel makale yapısı (akademik dürüstlük)
**Önceki:** v4 (T01-T16)

---

## 📄 ABSTRACT (revize)

20 ayrı bilimsel test ile **çoklu-sinyal konsensüsü** üzerinden inşa edilmiş 3-leg kombin stratejilerinin **gerçek-dünya uygulanabilirliği** araştırıldı. 6 lig × 5 sezon = ~5800 maç üzerinde simulasyon, **6 farklı boyut** (sinyal, lig, K, stake, timing, vergi) ele alındı.

**Ana bulgu:** T1 (Türk Süper Lig) K=3 FAV_CONFIRMED stratejisi, **4 sezon backtest'inde ROI +60.3%** (CI95 [+3.6%, +125.1%]) ve **vergi sonrası +36-38% net ROI** ile **istatistiksel olarak suggestive ama Bonferroni-significant değil**.

**Önemli yeni bulgular (v5):**
- **T17 (2526 replikasyon):** Sezon devam ediyor (n=37), prelim -13.6% (yetersiz sample)
- **T18 (Vergi %10):** T1 net ROI +36-39% ✅, 3-lig net ROI sadece +2.9-4.9% ⚠️
- **T19 (Bonferroni):** 19 testten 0'ı eşiği geçti — multiple testing inflation riski yüksek
- **T20 (6-lig genişleme):** **EDGE BOZULDU** (-38K zarar) — DC modeli olmayan liglerde FAV_CONFIRMED yetersiz

**Pratik karar:** Mevcut **T1-only K=3 strateji optimum**. 3-lig vergi sonrası marjinal. 6-lig genişleme veri eksikliğinden başarısız.

---

## 1. PROJE GENİŞ ÖZETİ

### 1.1 5 Faz × 20 Test Yapısı

```
FAZ I  (T01-T02) — Sinyal Tespiti
FAZ II (T03-T05) — Strateji Optimizasyonu
FAZ III(T06-T07) — Lig Mekaniği
FAZ IV (T08-T11) — Bankroll & Portföy
FAZ V  (T12-T16) — Timing & Skip
FAZ VI (T17-T20) — Robustness Validation (v5)
```

### 1.2 v4 → v5 Evrimi

| Soru | v4 (öncesi) | v5 (sonrası) |
|---|---|---|
| Edge gerçek mi? | T1 K=3 +60% CI[+3.6,+125] | Replikasyon prelim (n=37 yetersiz) |
| Vergi etkisi? | hesaba katılmadı | T1: hâlâ +36% ✅, 3-lig: +3% marjinal |
| Multiple testing? | tartışılmamış | Bonferroni 0/19 — daha replikasyon gerek |
| 6 lig daha iyi mi? | tahmin +27K/yıl | Gerçek: -38K (DC olmayan zarar) |

---

## 2. v5 YENİ TESTLER (T17-T20)

### 2.1 T17 — 2025-26 Replikasyon (PRELIM)

**Sample:** 37 kupon (sezon devam ediyor, sadece 135-210 closing odds)

| Lig | n | Hit% | ROI |
|---|---:|---:|---:|
| T1 | 6 | 0% | -100% (gürültü) |
| E0 | 20 | 10% | -66% |
| D1 | 11 | 36% | +128% |
| **TOPLAM** | **37** | **16%** | **-13.6%** |

**Karşılaştırma:** 4-sezon ortalaması +16.9% → 5. sezon -13.6%. **Belirsiz** — sezon bitince tekrar.

### 2.2 T18 — Vergi Etkisi (%10 Şans Oyunları Vergisi)

**Mode A (iyimser, net profit %10):**
- T1-only: +56K → **+42K (ROI +38.7%)**
- 3-lig: +63K → **+22K (ROI +4.9%)**

**Mode B (kötümser, gross payout %10):**
- T1-only: +56K → **+40K (ROI +36.4%)**
- 3-lig: +63K → **+13K (ROI +2.9%)** ⚠️

**Karar:** T1-only vergi-dayanıklı. 3-lig çok ince marjla pozitif. **T1 tercih**.

### 2.3 T19 — Bonferroni Multi-Test Correction

```
19 test yapıldı.
Bonferroni alpha' = 0.05 / 19 = 0.0026

Pre-correction p<0.05: 6/19 (T04 E0/T1, T06 T1 K=3, T08 Kelly Half, T11 ALL flat, T12 W1)
Post-Bonferroni:       0/19  ❌
```

**Akademik karar:** Hiçbir bulgu Bonferroni-significant değil. P-değerlerimiz **suggestive** ama **kesin kanıt değil**. **Replikasyon kritik** (T17 ve live shadow).

### 2.4 T20 — 6-Lig Genişleme

```
3-lig (T1+E0+D1): +62,897 TL  (yıllık +14,957)
6-lig (+SP1+I1+F1): +24,095 TL  (yıllık +4,486)
EK 3 lig fark: -38,802 TL ZARAR  ❌
```

**Per-lig kırılım:**
- T1: +51.5% ROI ✅
- D1: +10.2% (K=3'te pozitif!)
- I1: -0.7% (marjinal)
- E0: -3.7% ❌
- F1: -15.7% ❌
- SP1: -17.3% ❌

**Sebep:** SP1/I1/F1'de **DC modeli YOK** → FAV_CONFIRMED sadece anomaly+xG+form ile zayıf.

**Karar:** 6-lig genişleme reddedildi. **3-lig (T1+E0+D1) optimum.**

---

## 3. FINAL PRODUCTION STRATEJİSİ (v5 update)

```yaml
strateji: FAV_CONFIRMED K=3
ligler: [T1]  # PRIMARY (T18 vergi: ROI +38%)
# alternatif: T1+E0+D1 paralel (3-lig, T18 vergi sonrası ROI +5%)
mode: homogenous
min_confirmers: 1
stake: Flat 1000 TL/kupon

backtest (4 sezon, T1-only):
  n: 103 kupon
  ROI brüt: +60.3%
  ROI vergi (%10 net): +38.7%
  hacim: 103K TL
  net (vergi sonrası): +42K TL
  aylık: +875 TL (vergi sonrası)
  yıllık: +10,500 TL

backtest (4 sezon, 3-lig paralel):
  n: 397 kupon
  ROI brüt: +20.3%
  ROI vergi: +4.9%
  net (vergi sonrası): +22K TL
  aylık: +458 TL
  yıllık: +5,500 TL
  ⚠️ marjinal, sample variance riski yüksek

KARARLAR:
  Skip dark weeks:     HAYIR  (T15 overfit)
  Loss-streak pause:   HAYIR  (T16 gambler's fallacy)
  6-lig genişleme:    HAYIR  (T20 zarar -38K)
  Entry timing:        HER HAFTA
  K (legs):           3
  Confirmer:          ≥1 (T07 sıkısı çöker)
```

---

## 4. HİPOTEZ DOĞRULAMA TABLOSU (v5 final)

| H | Hipotez | v5 sonuç |
|---|---|:---:|
| H1 | Konsensüs edge yaratır | ✅ T6 ama Bonferroni-significant değil |
| H2 | Lig spesifik | ✅ T1 ✅, SP1/F1 ❌ |
| H3 | K=3 optimum | ✅ |
| H4 | Cross vs Homogen | ⚠️ stake regime'e bağlı |
| H5 | Half-Kelly | ✅ |
| H6 | Entry timing | ⚠️ W30 küçük sample |
| H7 | Skip dark weeks | ❌ T15 overfit |
| H8 | Multi-league flat | ⚠️ vergi sonrası marjinal |
| H9 | Combined optimum | ❌ overfit |
| H10 | Loss-streak pause | ❌ gambler's fallacy |
| **H11** | **5. sezon edge devam** | **⚠️ PRELIM (T17 sample küçük)** |
| **H12** | **Vergi sonrası +EV** | **✅ T1: %38, 3-lig: %5 marjinal** |
| **H13** | **Bonferroni geçer mi?** | **❌ 0/19 (replikasyon kritik)** |
| **H14** | **6-lig artırır mı?** | **❌ -38K ZARAR (DC olmayan)** |

---

## 5. AKADEMİK DÜRÜSTLÜK NOTLARI

### 5.1 Sınırlamalar (genişletilmiş)

1. **Sample n=103** — T1 finite, Bonferroni geçemiyor
2. **Replikasyon eksik** — T17 prelim (n=37)
3. **In-sample DC bias** — walk-forward sadece E0'da
4. **Pinnacle CLV yok** — opening odds eksik
5. **Multiple testing inflation** — 19 test
6. **Survivorship bias** — testler arasından en iyiyi seçtik
7. **Lig spesifik mekanik** bilinmiyor — T1 neden?
8. **6-lig zarar** — DC olmadan FAV_CONFIRMED zayıf
9. **Vergi modeli** Türkiye spesifik (%10)
10. **Live shadow yok** — sadece historical

### 5.2 Replikasyon Yol Haritası

🔴 **Kritik (gerçek edge kanıtı için):**
1. 2025-26 sezonu bitti → T17 tam replikasyon (Mayıs 2026)
2. Live shadow run 4-8 hafta (her hafta tek kupon)
3. T1 walk-forward DC (in-sample bias temizleme)

🟡 **Önemli:**
4. SP1+I1+F1 DC modelleri eğit (T20 başarısızlığını çözmek için)
5. Pinnacle opening odds kaynağı (CLV)
6. xG T1 alternatif (Sofascore/FotMob)

🟢 **Akademik tamamlama:**
7. Benjamini-Hochberg FDR analizi (Bonferroni yumuşatması)
8. Robustness checks (subset analysis)
9. Bayesian credibility intervals

---

## 6. UYGULAMA TAVSİYESİ

### Yeni Başlayan Kullanıcı için

**Adım 1:** Test ortamı
- Streamlit UI üzerinden geçmiş matchday'leri incele
- T1 K=3 strateji nasıl çalışıyor gör

**Adım 2:** Küçük live test (500-1000 TL bankroll)
- Her hafta T1 K=3 kuponu için 50 TL stake
- 4-8 hafta sonuç takip
- Eğer kayıp serisi -200 TL geçerse → DUR

**Adım 3:** Ölçeklendirme (kanıt sağlandıktan sonra)
- T1-only 1000 TL/hafta flat
- Aylık ortalama beklenti: **+875 TL net** (vergi sonrası)
- Yıllık beklenti: **+10K TL net**

### Risk uyarısı

- En uzun ardışık kayıp: 14 kupon (T8'den, 3-4 ay)
- Max drawdown: 14K TL (T1-only baseline)
- **Bonferroni geçemediği için "kesin garantili" diyemeyiz**
- 4 sezon backtest **suggestive evidence**, kanıt değil

---

## 7. TÜM TEST DOSYALARI

```
RAPOR/
├── YONETICI_OZETI_v5.md  ← FINAL (BU)
├── YONETICI_OZETI_v4.md  ← akademik 2
├── YONETICI_OZETI_v3.md  ← akademik 1
├── YONETICI_OZETI_v2.md  ← production
├── TEKNOLOJI_VE_BILIMSEL_BULGU_RAPORU.md (v1)
├── v4_FAZ5_TEST_ONERILER.md
├── T01_consensus_survival.md
├── T02_combo_kupon.md
├── T03_mvk_sweep.md
├── T04_league_validation.md
├── T05_final_pipeline.md
├── T06_k3_crossleague.md
├── T07_strict_filter.md
├── T08_bankroll_singleleague.md
├── T09_portfolio.md
├── T10_kelly_sizing.md
├── T11_flat1000.md
├── T12_entry_timing.md
├── T13_skip_strategy.md
├── T14_multileague_budget.md
├── T15_optimum_combo.md
├── T16_lossstreak_pause.md
├── T17_replication_2526.md  ← v5
├── T18_transaction_cost.md  ← v5
├── T19_bonferroni.md        ← v5
└── T20_6league_backtest.md  ← v5
```

---

## 🎓 BİLİMSEL ÖZ (v5)

> **"Bilim, sezgileri test ederek ilerler. Kanıt bekler. Sürtünme yaratır."**
>
> Sezgilerimizin **yarısı yanlış** çıktı:
> - Skip dark weeks → overfit (T15)
> - Loss-streak pause → gambler's fallacy (T16)
> - 6-lig genişleme → -38K zarar (T20)
> - Bonferroni-significant edge → 0/19 test (T19)
>
> Sezgilerimizin **yarısı doğru** çıktı:
> - 3 bağımsız ses konsensüsü → +60% ROI (T06, suggestive)
> - T1 farklıdır → out-of-sample da çalıştı (T15)
> - Vergi sonrası T1 hâlâ pozitif → +38% (T18)
> - K=3 optimum → tutarlı (T06)
>
> **Sonuç:** "Veri-driven epistemoloji" projesi. Kanıt yetersiz olsa bile, mevcut **suggestive evidence + replikasyon planı + risk yönetimi** ile uygulamaya geçmek **kabul edilebilir bir bilimsel temele dayanır**.

---

**Proje statüsü:** Backtest tamamlandı, replikasyon ve live shadow bekleniyor. Production kullanım için **küçük stake ile başla, validasyon ile ölçeklendir**.
