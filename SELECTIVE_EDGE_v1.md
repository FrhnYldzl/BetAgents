# SELECTIVE EDGE v1.0 — Haftanın 3 Maçı

> "Her maçı bilmeye çalışmak saçma. 100 maçtan en garanti 3'ünü seçmek **sharp bettor mantığı**."
> — Kullanıcı, 27.05.2026

---

## Felsefe

Pinnacle, Bet365, iddaa — **dünyanın en güçlü modelleri**. Her maçta onları yenmek imkansız.
Ama her hafta **birkaç maçta** market dengesizliği, yorumcu konsensüsü, ya da
asimetrik bilgi olur. Bunları **bulup seçmek** = real edge.

**Selektif olmak > yüksek hacim.**

---

## 3 Sinyal Kaynağı (Gerçek Data)

### 1️⃣ iddaa İç-Pazar Anomalileri
iddaa'nın **kendi pazarları arasındaki tutarsızlıklar** sinyaldir:

- **1X2 implied probability** vs **A/Ü 2.5 implied** mismatch
  - Örnek: Ev 1.50 favorisi AMA A/Ü 2.5 odds 1.85/1.95 dengesi → ev kontrollü düşük skor sinyali
- **Çifte Şans paradox**: 1X (1.20) ve 2 (4.00) — implied prob toplam ≠ 1 anormal
- **Handikap +1 vs MS 1**: handikap odds < MS 1 odds → bookmaker "kesin galip" diyor
- **KG Yok vs Alt 2.5**: yüksek korelasyon, biri "şüpheli" düşükse anomali

**Hipotez:** Birden çok pazar aynı yöne kuvvetle göstermiyorsa **yapısal belirsizlik var**.
Hepsi aynı yöne gösteriyorsa **konsensüs çok yüksek** → güvenli seçim.

### 2️⃣ Yorumcu Konsensüsü
**Tipsters / Spor yazarları:**

| Kaynak | İçerik | Erişim |
|---|---|---|
| **iddaa.com Yazar Yorumları** | 10+ Türk yazarın kuponları | Web scrape (Next.js JSON) |
| **Tipstrr.com** | International tipsters + win rate | API/scrape |
| **OLBG** | UK tipsters + community vote | Scrape |
| **BlogAbet** | Pro tipsters + ROI track record | Scrape |
| **Mackolik / Sahadan** | Türk yazar tahminleri | Scrape |

**Her yorumcu** için track record skoru tut:
```
tipster_score = (kazanma_orani × bet_sayisi × recent_form) / variance
```

**Yorumcu konsensüsü = top 10 yorumcunun aynı maçta aynı tahminde olması**
- 10/10 → 1.0 (mükemmel)
- 7/10 → 0.4 (orta)
- 5/10 → 0.0 (belirsiz)

### 3️⃣ Model Güveni + Risk Skoru
Mevcut Dixon-Coles + fixture statistics:
- DC probability > %65 (yüksek güven)
- Variance düşük (xG_diff > 0.5)
- Recent form tutarlı

---

## Selection Score Formülü

```
selection_score(match) =
    0.35 * odds_anomaly_signal      # iddaa içi tutarsızlık
  + 0.30 * tipster_consensus         # yorumcu birlik
  + 0.20 * model_confidence          # DC olasılık
  + 0.15 * inverse_variance          # düşük varyans

range: 0-1
```

Top-3 maç **selection_score**'a göre seçilir.

---

## Kombinasyon Optimizer

3 maç seçildi (A, B, C). Her birinde 7 pazar:
- MS-1, MS-X, MS-2, Üst 2.5, Alt 2.5, KG Var, KG Yok

→ **7³ = 343 kombinasyon**

Her kombinasyon için:
```
joint_prob = pA × pB × pC  (bağımsız varsayım)
combined_odds = oA × oB × oC
EV = joint_prob × combined_odds - 1
risk_score = sqrt(var(probs))  # ne kadar varyans?
sharpe_eq = EV / risk_score
```

**Top kombinasyonlar 3 tier'da:**
- 🛡️ **GARANTİ** (sharpe > 1.5, joint_prob > 0.5)
- ⚖️ **DENGELİ** (sharpe > 0.8)
- 🚀 **YÜKSEK EV** (max EV, daha riskli)

---

## Risk Çarpanı (Yorumcu Karşılaştırması)

```
nihai_skor = selection_score × tipster_multiplier

if our_pick == top_tipster_pick: multiplier = 1.3
elif our_pick != top_tipster_pick: multiplier = 0.7
else: multiplier = 1.0
```

Top yorumcular katılıyorsa → kuponu **güçlendir**.
Bizimle uyuşmuyorsa → **dikkat** (model yanılıyor olabilir, ya da onlar)

---

## Implementation Plan

### Sprint 4.1 — Veri Katmanı
- [ ] **iddaa.com scraper** — bütün pazar odds'ları (1X2, A/Ü, KG, Hcp, vb)
  - Next.js `__NEXT_DATA__` + iddaa internal API
- [ ] **Yorumcu scraper** — iddaa.com Yazar Yorumları + Mackolik + OLBG
  - Her yorumcunun son 50 kuponunu + tutma oranını topla
- [ ] DB tabloları: `iddaa_odds`, `tipster_picks`, `tipster_stats`

### Sprint 4.2 — Sinyal Modülleri
- [ ] **odds_anomaly.py** — iddaa internal market consistency check
- [ ] **tipster_consensus.py** — track record + ağırlıklı konsensüs
- [ ] **model_confidence.py** — DC + fixture_statistics ile selection score

### Sprint 4.3 — Selector + Optimizer
- [ ] **selector.py** — 100 maçtan top-3 maç seçer
- [ ] **combination_optimizer.py** — 343 kombinasyon arasından en iyi
- [ ] Backtest: geçmiş haftalarda bu sistem ne yapardı?

### Sprint 4.4 — UI
- [ ] Yeni sayfa: 🏆 **HAFTANIN 3 MAÇI**
- [ ] Her maç için: selection_score breakdown, tipster konsensüsü, anomali sebep
- [ ] 3 tier kombinasyon önerisi (Garanti / Dengeli / Yüksek EV)

---

## Başarı Kriteri (CLV Pozitif)

**Mevcut:** Tüm maçlar bahse → CLV -%1.85, ROI -%7
**Hedef:** Sadece top-3 → CLV +%1, ROI +%5

Bu mümkün çünkü:
- Sample 10× azalır ama **bet kalitesi 5× artar**
- "Selektif" = sharp bettor felsefesi
- Bookmaker tek tek maçta perfect ama "her hafta hangi 3 maç değer var" bilemez

---

## Önemli Felsefi Değişim

**ÖNCE:** "Her maçı tahmin et, sonra edge'liyi bul" → her maçta Pinnacle vs biz
**ŞİMDİ:** "Pazar dengesizlik + yorumcu konsensüs + model güven → SEÇ"

Bu **bookmaker'la rekabet etmiyor**, **pazar verimsizliklerini bulup avlanıyor**.
