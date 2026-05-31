# BAHIS AGENT — Problem Tanımı

> "Bilimsel temelli, AI destekli, en iyi futbol bahis karar destek sistemi."

---

## 1. Vizyon

Spor bahisleri istatistiksel olarak **negatif beklenti** oyunudur (bookmaker marjı %5-10).
Buna rağmen küçük bir azınlık **uzun vadeli pozitif getiri** sağlar. Bu azınlığın yöntemi:
veri + bilim + disiplin + sabırlı sermaye yönetimi.

**BAHIS AGENT**, bu yöntemi sistematikleştiren ve sıradan bir kullanıcıya **karar destek aracı**
olarak sunan bir sistemdir.

İlk faz: **futbol**. Sonraki fazlarda: basketbol, tenis, e-spor.

---

## 2. Problem

> Bookmaker (iddaa, Pinnacle, Bet365) **dünyanın en sharp pricing'i** yapar.
> Tek başına xG, gol istatistiği, Elo gibi açık veriyle onu yenmek **çok zordur**.
>
> **Asıl edge**, diğer bahisçilerin **göremediği veya zamanında kullanamadığı**
> bilgiyi (haber, sosyal medya, lokal kaynak, taktiksel ayrıntı) yapılandırılmış
> feature'a çevirebilen bir sistemdedir.

Bizim çözmeye çalıştığımız problem:

1. **Tek bir insanın yapamayacağı** ölçekte bilgi işlemek
2. **Çoklu LLM** (Gemini + GPT + Claude + HuggingFace) ile sentez
3. **GPU compute** ile feature extraction
4. **Bilimsel kalibrasyon** (CLV, t-test, bootstrap)
5. **Risk yönetimi** (Kelly fractional, transaction cost)

Bunu yaparken:
- **Hata yaptırmama** — kullanıcı yanlış bilgi ile bahis koymasın
- **Şeffaflık** — model neyi neye göre dedi, hep açık
- **Bilimsel dürüstlük** — false promise yok, CLV negatif ise söylenir

---

## 3. Başarı Kriterleri (KPI)

### Bilimsel Kriterler (Phase 1)

| Metrik | Hedef | Mevcut |
|---|---|---|
| Sample size (n) | ≥ 500 | 577 ✅ |
| ROI t-test p-value | < 0.05 | 0.48 ❌ |
| CLV mean | > +%0.5 | -%1.85 ❌ |
| CLV > 0 oran | > %50 | %33 ❌ |
| Bootstrap P(ROI>0) | > %90 | %24 ❌ |
| Brier score | < piyasa (vig-adjusted) | test edilmedi |

### Ticari Kriterler (Phase 2+, edge kanıtlandıktan sonra)

| Metrik | Hedef |
|---|---|
| Yıllık ROI (bet hacmi üzerinden) | +%3-7 (sharp bettor seviyesi) |
| Maksimum drawdown | < %30 |
| Sharpe-equivalent | > 1.0 |
| Kullanıcı sayısı | 100 → 1K → 10K |
| Aylık ARPU | 100-500 ₺ |

### Operasyonel Kriterler

| Metrik | Hedef |
|---|---|
| API çağrı kotası kullanımı | < %50 / gün |
| UI ortalama yanıt süresi | < 2 saniye |
| Veri güncelliği | <24 saat geride |
| Sistem uptime | %99 |

---

## 4. Kapsam (Scope)

### ✅ Kapsam İçinde

- Avrupa büyük 5 lig (EPL, La Liga, Serie A, Bundesliga, Ligue 1)
- Türkiye Süper Lig
- Verimsiz pazarlar: Belarus, Kazakistan, İran, Norveç (Sprint 2.2)
- 7 ana iddaa pazarı: MS 1X2, İY 1X2, Handikap, A/Ü, KG, Çifte Şans, İY/MS
- Yapılandırılmış veri: skor, xG, sakatlık, lineup, hakem
- Yapılandırılmamış veri (LLM ile): yazar yorumu, sosyal medya, haber
- Walk-forward backtest, CLV ölçümü, t-test
- Risk yönetimi (Kelly, max drawdown, daily loss limit)

### ❌ Kapsam Dışı (şu an)

- Otomatik bet yerleştirme (sadece öneri)
- Canlı (in-play) bahis tahmini — ileride
- Arbitraj — etik konular
- Match-fixing detection — başka bir proje
- Diğer sporlar (basketbol, tenis) — Phase 3+
- Casino oyunları — kapsam dışı

---

## 5. Etik ve Yasal Çerçeve

- iddaa.com Türkiye'de **Spor Toto Teşkilatı** tarafından lisanslı, **yasal** platform
- 18 yaş altı katılım yasak (iddaa Madde 6/1)
- Kumar bağımlılığı uyarısı zorunlu (Yeşilay 0850 222 39 39)
- Maç sabitleme, içeriden bilgi vb. **ASLA** kullanılmaz
- Sadece **açık veri** + **AI sentezi** + **istatistiksel modelleme**

---

## 6. Hangi Liglerde Çalışıyor?

| Lig | Veri | Model | Test |
|---|---|---|---|
| 🏴 Premier League (E0) | 1,900 maç | DC fit ✅ | n=213 |
| 🇹🇷 Türkiye Süper Lig (T1) | 1,750 maç | DC fit ✅ | n=195 |
| 🇩🇪 Bundesliga (D1) | 1,530 maç | DC fit ✅ | n=169 |
| 🇪🇸 La Liga (SP1) | api-football | DC bekliyor | — |
| 🇮🇹 Serie A (I1) | api-football | DC bekliyor | — |
| 🇫🇷 Ligue 1 (F1) | api-football | DC bekliyor | — |
| 🇰🇿 Kazakistan, Belarus, İran | YOK | Sprint 2.2 | — |

xG verisi: Avrupa 5 büyük lig × 3 sezon = **5,330 maç**.
Sakatlık verisi: 6 lig × 1 sezon = **15,475 kayıt**.

---

## 7. Mevcut Bilimsel Durum (27 Mayıs 2026)

> Multi-league backtest (n=577, 3 lig): **CLV -%1.85, p=0.0000**
> → İstatistiksel olarak güçlü negatif edge.
> Yani şu anda kupon önerilerimiz **uzun vadede zarar** ediyor.

**Net:** Sistemin temel işlevleri (kupon önerme, risk yönetimi, UI) çalışıyor ama
matematiksel olarak henüz "kazandıran" bir araç değil. Sprint 2.3 (LLM Augmentation)
ve Sprint 2.2 (alt lig coverage) ile edge yaratılmaya çalışılacak.

Bu **dürüstlük** ürünün asıl değeri. Pazarlama yalanı değil, gerçek bilim.

---

## 8. Sıradakiler

[`URUN_ROADMAP.md`](./URUN_ROADMAP.md) — detaylı sprint planı

Özet:
- **Sprint 2.2** — Alt lig (Belarus, Kazakistan, İran)
- **Sprint 2.3** — LLM Augmentation (Gemini + GPT + HuggingFace)
- **Sprint 2.4** — Transaction cost & risk yönetimi
- **Sprint 2.5** — Continuous validation
- **Phase 3** — Production deployment + kullanıcı arayüzü
