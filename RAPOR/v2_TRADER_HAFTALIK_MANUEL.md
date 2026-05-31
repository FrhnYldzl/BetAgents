# TRADER HAFTALIK MANUEL — BAHIS AGENT
## "Sen TRADER'sın. Bu manuel sana ne zaman ne yapacağını söyler."

**Tarih:** 2026-05-28
**Versiyon:** v0.1 (1X2 only — multi-market v1.0'da gelecek)
**Hedef:** Hafta hafta net düzen + ligbazlı karar + kupon mantığı + PAS kuralları

---

## 🎯 ANA İLKE

> **"Modelin SANA söylediği nadirdir. Ona kulak verene kadar otur. Konuşunca pozisyonu doğru ayarla."**

3 olası karar:
1. **OYNA — BÜYÜK** (Q5 + agree≥2) — Ayda 5-7 kez
2. **OYNA — STANDART** (Q4 veya Q5+agree=1) — Ayda 10-15 kez
3. **PAS** (Q1-Q3 veya hiç sinyal yok) — Çoğu hafta budur

---

## 📅 HAFTA AKIŞI

### PAZARTESİ — Hafta Açılışı (15 dk)

**1. Maç takvimini gör**
- 5 lig fixture'larını al: T1, E0, SP1, D1, I1, F1 (sadece bilgi için, D1+I1+F1 zayıf model)
- Bu hafta toplam kaç maç? Tipik: 30-50 maç

**2. Bankroll kontrolü**
- Mevcut bankroll = X TL
- Temel stake birimi = X × %1 (örnek: 10,000 TL → 100 TL)
- Hafta önceki haftalardan kalan açık kupon var mı? (yoksa devam)

**3. Drawdown check**
- Son 30 günde toplam PnL?
- Bankroll −%15+ düştüyse: tüm stake çarpanlarını yarıya indir
- Bankroll −%25+ düştüyse: bu hafta PAS, audit yap

---

### SALI — Sinyal Üretimi (Otomatik, 0 dk insan)

**Cron'da otomatik çalışan script:**
```bash
python 03_MODELLER/selective/run_weekly_picks.py
```

Çıktı (örnek):
```
═══════════════════════════════════════════════════════════════
HAFTA: 2026-05-30 / 2026-06-01
═══════════════════════════════════════════════════════════════

TRIVOX (T1) — 3 maç tahmini
  [Q4]  Galatasaray - Fenerbahce      | 1 @ 1.85  agree=1  score=0.81
  [Q3]  Trabzonspor - Besiktas        | 2 @ 3.20  agree=1  score=0.71
  [Q2]  Konyaspor - Antalyaspor       | X @ 3.40  agree=1  score=0.58

MONOVOX-E0 (Premier League) — 5 maç tahmini
  [Q5+a2] Liverpool - Tottenham        | 1 @ 1.55  agree=2  score=0.93  *** ALL-IN ***
  [Q5]    Arsenal - Chelsea            | 1 @ 1.70  agree=1  score=0.91
  [Q4]    Newcastle - West Ham         | 1 @ 1.75  agree=1  score=0.84
  ...

DUOVOX (E0+SP1) — 8 maç tahmini
  [Q5+a2] Liverpool - Tottenham        | 1 @ 1.55  agree=2 (DUOVOX confirm)
  [Q5+a2] Real Madrid - Real Betis     | 1 @ 1.45  agree=2  *** ALL-IN ***
  ...

TRIOVOX (E0+SP1+D1) — 12 maç tahmini
  ...

MONOVOX-SP1 (La Liga) — 5 maç tahmini
  ...

═══════════════════════════════════════════════════════════════
ÖZET: Bu hafta 3 ALL-IN, 5 STANDART, 6 KÜÇÜK aday
═══════════════════════════════════════════════════════════════
```

---

### ÇARŞAMBA — Watch List (10 dk)

**1. ALL-IN adaylarını gözden geçir**
- Q5+agree≥2 olan maçları aç
- Kontroller:
  - Sakatlık haberi son 48 saatte? (lineup teyidi)
  - Hava durumu, saha durumu anormal mi?
  - Kulüp içi haberler? (transfer/teknik direktör)
- Eğer **şüphe varsa** → ALL-IN'i STANDART'a düşür veya PAS

**2. Closing odds tahmini**
- Şu anki opening odds vs Pinnacle/Bet365 closing tahmini
- Eğer **odds bizim aleyhimize sertçe düşüyorsa** (sharp money against us) → PAS
- Eğer **lehimize hareket varsa** (sharp money with us) → güven artar

**3. Multi-model konsensüs check (önemli)**
- Aynı maç birden fazla modelde Q5'de mi?
  - Örnek: Liverpool-Tottenham hem MONOVOX-E0 hem DUOVOX'ta Q5
  - 2+ model aynı yönde Q5 → **ULTRA-KONSENSÜS** (pozisyonu artır)

---

### PERŞEMBE — Karar Matrisi (5 dk)

Her aday için tabloyu doldur:

| Maç | Lig | Model(ler) | Yön | Odd | Quintile | agree | Pozisyon | Final |
|---|---|---|---|---|---|---|---|---|
| Liverpool-Tottenham | E0 | MONOVOX-E0 + DUOVOX | 1 | 1.55 | Q5 | 2 | ALL-IN | 500 TL |
| Real Madrid-Betis | SP1 | DUOVOX + MONOVOX-SP1 | 1 | 1.45 | Q5 | 2 | ALL-IN | 500 TL |
| Arsenal-Chelsea | E0 | MONOVOX-E0 | 1 | 1.70 | Q5 | 1 | BÜYÜK | 300 TL |
| Galatasaray-FB | T1 | TRIVOX | 1 | 1.85 | Q4 | 1 | STANDART | 100 TL |
| Trabzon-Besiktas | T1 | TRIVOX | 2 | 3.20 | Q3 | 1 | MİNİMAL | 25 TL |

**Karar Kuralları:**
- Aynı maça birden fazla modelin Q5'i geliyorsa → tek kupon, ULTRA pozisyon
- 2+ Q5+agree2 sinyali geliyorsa → ayrı kuponlar (varyans dağıtımı)
- ALL-IN sayısı 3'ten fazlaysa → en güçlü 3'ünü seç (yoğunlaşma)

---

### CUMA — Pre-Match Buffer (5 dk, opsiyonel)

- Maç günü yaklaştıkça odds değişimi:
  - Bizim seçtiğimiz tarafta sharp drop varsa → "doğru taraf" güveni artar
  - Bizim tarafta drift varsa → PAS düşün
- Lineup açıklandı mı? (1-2 saat öncesi)
  - Anormal eksiklik varsa (yıldız oyuncu yok) → PAS

---

### CUMARTESİ — Bahis Koyma (10 dk)

**1. Kupon stratejisi (1X2 only versiyon — multi-market sonra):**

**Tek-Maç Tek-Bahis (RECOMMENDED):**
```
Kupon 1: Liverpool 1@1.55    Stake: 500 TL (ALL-IN)
Kupon 2: Real Madrid 1@1.45  Stake: 500 TL (ALL-IN)
Kupon 3: Arsenal 1@1.70      Stake: 300 TL (BÜYÜK)
Kupon 4: Galatasaray 1@1.85  Stake: 100 TL (STANDART)
```
4 ayrı kupon, hepsi K=1. Risk dağıtılır, varyans düşer.

**KOMBINE (sadece izole edilmiş alanlarda):**
```
Kupon: Liverpool 1 + Real Madrid 1 = combo @ 2.25
       Stake: 200 TL
```
- Sadece **Q5+agree2 × Q5+agree2** birleştirilebilir
- Vergi avantajı: 66,935 TL üstü için K=2 sınırı

**2. Bahis girme**
- iddaa.com'a manuel gir (otomatik henüz yok)
- Her kuponu logla: matchday, leg(s), stake, odds, model_source

**3. Kupon log dosyası** (`07_LOG_VE_RAPORLAR/trader_log.csv`)
```csv
date,model,league,home,away,direction,odd,stake,quintile,agree,result,won,pnl
2026-05-31,MONOVOX-E0,E0,Liverpool,Tottenham,1,1.55,500,Q5,2,?,?,?
```

---

### PAZAR — Sonuç İzleme (5 dk)

- Maç sonuçları gelince log'u güncelle
- Hit/Miss kaydet
- Hesap bakiyesini bankroll'a not et
- Eğer ALL-IN kaybetti → next hafta PAS düşün (1 hafta sakinleşme)
- Eğer ALL-IN kazandı → bankroll güncel, gelecek hafta normal

---

### PAZARTESİ (sonraki) — Haftalık Audit (10 dk)

**Önceki haftanın muhasebesi:**
```
Hafta: 2026-05-30
═══════════════════════════════════════════════
Aday picks: 14
Oynanan: 4 (10 PAS)
Stake: 1,400 TL
Kazanan: 3
Pnl_gross: +480 TL
Pnl_net: +432 TL (vergi sonrası)
Hit rate: 75% (3/4)
ROI haftalık: +3.1%
═══════════════════════════════════════════════
```

**Aylık audit (her ay sonu):**
- Toplam hit rate per model
- Q5 hit rate vs beklenen
- Sapma >%10 ise model audit
- CLV kontrol (closing odds ile karşılaştır)

---

## 📊 LİG BAZLI KARAR REFERANSI

| Lig | Model | Karar Eşiği | Frekans |
|---|---|---|---|
| **T1** (Türk) | TRIVOX | Q5+agree2 → ALL-IN, Q5 → BÜYÜK, Q4 → STANDART | Ayda 0.5 ALL-IN |
| **E0** (Premier) | MONOVOX-E0 + DUOVOX | Q5 konsensüsü → ULTRA-ALL-IN | Ayda 1-2 ALL-IN |
| **SP1** (La Liga) | MONOVOX-SP1 + DUOVOX | Q5 konsensüsü → ULTRA-ALL-IN | Ayda 0.5-1 ALL-IN |
| **D1** (Bundes) | TRIOVOX'un parçası | Sadece TRIOVOX bütününde Q5 ise | Ayda 0.5 |
| **I1** (Serie A) | (model yok) | PAS | 0 |
| **F1** (Ligue 1) | (RED FLAG) | PAS — bu lig sistemli kaybediyor | 0 |

---

## 🚫 PAS Kuralları (Net Olmalı)

**ASLA bahis yapma:**
1. Sample n<5 olan modeli kullanma (gürültü)
2. F1 (Ligue 1) tek başına — sistemli kayıp
3. Q1-Q2 quintile picks — modelin emin olmadığı
4. Drawdown −%25+ ise — risk soğutma
5. Birden fazla ALL-IN aynı yönde (örn. 3 takım kazansın) — korelasyon riski
6. Lineup'ta beklenmedik eksik varsa
7. Closing odds bizim aleyhimize >%10 hareket ettiyse
8. Hafta 10-18 arası (devre arası) → ihtiyatlı, küçük pozisyon

**OYNAMAK SERBEST:**
1. Q5+agree≥2 ve sample yeterli
2. Multi-model konsensüs (2+ model aynı yön)
3. Q4 ve sample yeterli, normal koşullar

---

## 🎯 BEKLENEN OPERASYONEL RİTM

```
HAFTALIK
══════════════════════════════════════════════
  Çalıştırılan model       : 5 (otomatik)
  Üretilen aday pick        : 20-40
  Oynanan ALL-IN            : 0-2
  Oynanan STANDART          : 1-3
  PAS edilen                : %80-90
  Stake / hafta             : 500-2,000 TL
  Beklenen kazanç           : +50 ile +500 TL net

AYLIK
══════════════════════════════════════════════
  ALL-IN sinyali            : ~5-7
  ALL-IN hit                : %70-83
  STANDART sinyali          : ~10-15
  STANDART hit              : %60-65
  Aylık net PnL             : 300-800 TL
  Aylık ROI (10K bankroll)  : %3-8
  Yıllık ROI tahmini        : %40-80 net
```

**⚠️ NOT:** Bu tahminler tarihsel backtest'ten. Live'da %30-50 daha düşük olabilir.

---

## 🔥 BİR SONRAKİ BÜYÜK ATILIM: MULTI-MARKET

Şu anki manuel **sadece 1X2 (Maç Sonucu)** üzerinde çalışıyor. **Birkaç hafta içinde** model şu pazarları da tahmin edecek:

1. **Maç Sonucu** (1, X, 2) ✅ mevcut
2. **İlk Yarı Sonucu** (1, X, 2) ⏳ V2'de
3. **Handikaplı Maç Sonucu** (1, X, 2) ⏳ V2'de
4. **Alt/Üst 2.5** (Alt, Üst) ⏳ V2'de (closing odds var, model yok)
5. **Karşılıklı Gol** (Var, Yok) ⏳ V2'de

Bu **çok büyük açılım**:
- Aynı maçta 5 farklı pazar tahmini
- Korelasyonlu pazarlar tek kuponda kombine edilebilir
- Edge alanı **5x genişler**
- Detaylı tasarım: `v2_MULTIMARKET_MODEL_TASARIMI.md`

---

## 📋 TEK SAYFA ÖZET (DUVAR POSTERİ)

```
┌────────────────────────────────────────────────────────────┐
│              TRADER WEEKLY CHEAT-SHEET                     │
├────────────────────────────────────────────────────────────┤
│  PZT  Bankroll + maç takvimi check (15 dk)                 │
│  SAL  Model otomatik çalışır (0 dk)                        │
│  ÇAR  Watch list incele (10 dk)                            │
│  PER  Karar matrisi doldur (5 dk)                          │
│  CUM  Pre-match buffer (opsiyonel)                         │
│  CMT  Bahis koy + log (10 dk)                              │
│  PAZ  Sonuç izle (5 dk)                                    │
│  PZT  Haftalık audit (10 dk)                               │
├────────────────────────────────────────────────────────────┤
│  Q5+agree≥2  → ALL-IN (5x stake)  → Ayda 5-7 kez           │
│  Q5+agree=1  → BÜYÜK (3x stake)   → Ayda 5-10              │
│  Q4          → STANDART (1x)      → Ayda 10-15             │
│  Q3+agree≥2  → KÜÇÜK (0.5x)       → Ayda 5-10              │
│  Q1, Q2      → PAS                → Çoğunluk               │
├────────────────────────────────────────────────────────────┤
│  ALL-IN sayısı ≥ 3              → En güçlü 3'ünü seç        │
│  Drawdown ≥ −%15                → stake/2                   │
│  Drawdown ≥ −%25                → 1 hafta PAS               │
│  F1 (Ligue 1)                   → ASLA                      │
│  I1 (Serie A) tek başına        → ASLA                      │
└────────────────────────────────────────────────────────────┘
```
