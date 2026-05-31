# TRADER PLAYBOOK v0.1
## BAHIS AGENT — Selective Sniper Stratejisi

**Tarih:** 2026-05-28
**Hedef:** Tek kuponu tutarlı tutturmak. Selective sniper. Sinyal gücüne göre pozisyon.
**Paradigma kayması:** ROI bazlı düşünme → Hit rate × pozisyon disiplini.

---

## 1) ANA TEZ

> "Her hafta bahis koymak gerekmez. Modelin güçlü sinyal verdiği anlar nadirdir ama o anlarda **%67-83 hit rate** elde edilebilir. Trader işi: bu anları yakalamak, pozisyonu doğru ayarlamak, beklemeyi öğrenmek."

### Veri Tabanı (sample = signal_snapshots, 10,657 settled maç, 5 sezon)

Kapı 0 testleriyle ispatlandı:
- xG/form sinyallerinde **0 leakage** (T03)
- Market kalibrasyon **stabil** (T04)
- TRIVOX K=1 baseline **+%2 ROI, p≈0.0025** — Bonferroni sınırında geçer (T01)
- Q5 (top 20% güçlü sinyal) **5 model hepsinde stabil** (T10)

---

## 2) ÜRÜN AİLESİ — 5 MODEL PARALEL

| Model | Lig | Q5 hit (mean) | Q5 std | Son 2 sezon | Frekans (Q5+agree2) |
|---|---|---|---|---|---|
| **TRIVOX** | T1 (Türk Süper Lig) | %70 | 9pp | %78 | Ayda ~0.5 (sniper) |
| **MONOVOX-E0** | E0 (Premier League) | %72 | 10pp | %67 | Ayda ~1 |
| **DUOVOX** | E0+SP1 | **%71** | **3pp** ⭐ | %69 | Ayda ~1.5 |
| **TRIOVOX** | E0+SP1+D1 | %69 | 3pp ⭐ | %67 | Ayda ~2 |
| **MONOVOX-SP1** | SP1 (La Liga) | %70 | 10pp | %78 | Ayda ~0.5 |

**Tüm modeller "LIVE-OK" verdict aldı.**

### Hangi Model Kime?

- **Disiplinli sabırlı**: TRIVOX veya MONOVOX-SP1 (ayda 0.5 maç, ama %78-83 hit)
- **Standart kullanıcı**: DUOVOX (ayda 1.5 maç, %69-71 hit, **en stabil**)
- **Aktif kullanıcı**: TRIOVOX (ayda 2 maç, %65-75)
- **Hiçbiri tek başına yetmiyor**: 5'i birlikte çalıştır → toplam ayda 5-7 super pick

---

## 3) SİNYAL → POZİSYON KARAR MATRİSİ

Her maç için **score_v13** (0-1 arası) ve **agree_count** (1-4 kaç sinyal aynı yönü gösteriyor) hesaplanır. Bu iki değer trader kararını verir:

```
┌─────────────────────────────────────────────────────────────────┐
│ SİNYAL FİLTRESİ                  POZİSYON           ÖRNEK STAKE  │
├─────────────────────────────────────────────────────────────────┤
│ Q5 + agree≥2  (ULTRA-NADIR)      "ALL-IN"            5x stake   │
│ Q5 + agree=1                      "BÜYÜK"             3x stake   │
│ Q4                                "STANDART"          1x stake   │
│ Q3 + agree≥2 (orta-güçlü)         "KÜÇÜK"             0.5x stake │
│ Q3 + agree=1                      "MİNİMAL"           0.25x      │
│ Q1-Q2                             "PAS"               OYNAMA     │
└─────────────────────────────────────────────────────────────────┘
```

### Pozisyon Çarpanı Mantığı

- **1x stake** = bankroll'un %1-2'si (operasyonel temel birim)
- **5x stake (ALL-IN)** = %5-10 bankroll — modelin en güvendiği anlar
- **Asla %10'u aşma** — Kelly-style ihtiyat

---

## 4) HAFTALIK İŞ AKIŞI (Trader Routine)

```
PERŞEMBE / CUMA — Hazırlık
  1. 5 modelin tüm pick'lerini üret (otomatik script)
  2. Her pick'i score quintile + agree_count'a göre sırala
  3. Q5 ve Q4 pick'leri liste

CUMARTESİ SABAH — Ön Karar
  4. Listede kaç Q5+agree2 var? → ALL-IN aday(lar)
  5. Kaç Q4 var? → standart aday
  6. Closing odds yakınlığını kontrol et (zaman buffer)

CUMARTESİ ÖĞLEN-AKŞAM / PAZAR — Bahis
  7. ALL-IN'leri kupon olarak yatır (eğer varsa)
  8. Standart pick'leri ayrı kupon
  9. Kuponları log'la (matchday, pick, score, agree, stake)

HAFTA SONU — Kayıt
 10. Sonuçlar geldikte hit kaydet
 11. Aylık özet: hit rate, pozisyon-ağırlıklı PnL
 12. CLV ölç (opening vs closing) — modelin gerçek edge'i mi?
```

---

## 5) RİSK YÖNETİMİ

### Stake Hesabı (örnek: 10,000 TL bankroll, %1 temel birim)

| Durum | Stake | Bankroll % |
|---|---|---|
| ALL-IN (Q5+a2) | 500 TL | %5 |
| BÜYÜK (Q5+a1) | 300 TL | %3 |
| STANDART (Q4) | 100 TL | %1 |
| KÜÇÜK (Q3+a2) | 50 TL | %0.5 |
| MİNİMAL (Q3+a1) | 25 TL | %0.25 |
| PAS (Q1-Q2) | 0 | %0 |

### Drawdown Kuralları

- **−%15 drawdown** → tüm stake çarpanlarını %50 azalt
- **−%25 drawdown** → modeli **durdur**, audit yap
- **Ardışık 3 ALL-IN kayıp** → bir hafta tüm modeller PAS

### Vergi Bilgisi (Türkiye)

- İddaa stopajı: kazanç üzerinden %10 (tek kuponda)
- 66,935 TL üzeri ikramiye: %20 ek vergi
- Bu nedenle **K=1 (tek bahis) tercih edilir**, kombin riski kaçınılır

---

## 6) BEKLENEN PERFORMANS (Tarihsel Bazlı)

### Aylık Frekans (5 model paralel)

```
TRIVOX Q5+a2     : Ayda ~0.5 ALL-IN
MONOVOX-E0 Q5+a2 : Ayda ~1 ALL-IN
DUOVOX Q5+a2     : Ayda ~1.5 ALL-IN
TRIOVOX Q5+a2    : Ayda ~2 ALL-IN
MONOVOX-SP1 Q5+a2: Ayda ~0.5 ALL-IN
─────────────────────────────────
TOPLAM           : Ayda ~5-7 ALL-IN sinyali
```

### Beklenen Kazanım (10K bankroll, mean Q5 hit %70, mean odd 1.65)

**Sadece Q5+agree2 oynanır senaryosu (ayda 5 ALL-IN):**
- 5 ALL-IN × 500 TL = 2,500 TL/ay risk
- Hit %75 (Q5+a2 ortalaması) → 3.75 kazanan, 1.25 kayıp
- Beklenen kazanç: 3.75 × 500 × 0.65 (odd-1) − 1.25 × 500 = 1,219 − 625 = **+594 TL/ay gross**
- %10 stopaj sonrası: **~535 TL/ay net**
- **%5.4 aylık net ROI** (10K bankroll)
- Yıllık: ~6,420 TL net, **%64 yıllık ROI**

**Standart pick'ler eklenirse (ayda 5 ALL-IN + 10 Q4):**
- Q4 hit %62 → ROI küçük ama pozitif
- Toplam aylık ROI tahmini: **%6-8 net**

⚠️ **UYARI:** Bu tahminler **in-sample backtest**'ten geliyor. Gerçek live performans 1.5-2x daha düşük olabilir (komite tezi).

---

## 7) HALA YAPILACAKLAR

### Bu Playbook'u Production'a Götürmek İçin

1. ✅ Q5 sezonsal stabilite ispatlandı (T10)
2. ⏳ **Yeni 19K matches_v2 üzerinde aynı testler** (Kapı 0 smoke test)
3. ⏳ **Live shadow run** — gerçek hafta sonunda picks üret, sonuç kaydet, hiç para koymadan 4-12 hafta
4. ⏳ **V2 sinyal güçlendirmesi** — FAV→VALUE pivot (CLV pozitif yapma hedefi)
5. ⏳ **Production UI** — trader haftalık dashboard

### Açık Sorular

- CLV hala negatif (−%2 to −%4) — Q5'te bile. Yeni sample ile değişir mi?
- 2025-26 sezonu için Q5 hit yüksek ama sample küçük (n=5-19) — sezon ortasında doğrula
- Hafta 10-18 "devre arası direnci" (T07) — playbook'a "ihtiyatlı dönem" eklemeli mi?

---

## 8) TEK CÜMLE ÖZET

> **5 model paralel + Q5+agree≥2 filtre + değişken pozisyon = ayda ~5 sniper bahis, mean hit %67-78, tarihsel %5-8 aylık net ROI tahmini.**

**Komite tezi vs Playbook tezi:**
- Komite: "Her hafta 1000 TL flat" → +%2 ROI marjinal → yatırılamaz
- Playbook: "Q5+a2 sniper, değişken pozisyon" → %70+ hit → trader silahı

**Aynı veri, farklı paradigma — bütün mesele buydu.**
