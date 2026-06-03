# MACKOLİK ARŞİVİ — VERİ KAYNAĞI DEĞERLENDİRMESİ (#149)

**Tarih:** 2026-06-03
**Soru:** Mackolik verisi DATASET + MODELLERİMİZE ne katar? TRADING'i nasıl etkiler?
**Yöntem:** "Önce DATA ve API kalitesi" — canlı endpoint probe + maç sayfası karakterizasyonu + bizdeki doluluk oranı kıyası.

---

## 0) TL;DR — KARAR

> **Mackolik = derin TARİHSEL ARŞİV + Türkiye otoritesi (hakem DB, kadro, isim eşleme), ama
> (1) temiz JSON API'si ÖLÜ → erişim kırılgan HTML scraping, (2) en kritik boşluğumuz olan
> xG'yi DOLDURMAZ, (3) tek başına trading EDGE yaratmaz.**
>
> **Tavsiye: Şu an FULL scraper inşa etme. Sadece 2 dar, yüksek-ROI kullanımı değerli:
> (a) HAKEM verisi backfill (18% → tam), (b) cross-source DOĞRULAMA (Football-Data hatalarını yakala).
> Asıl model boşluğu (T1 xG) için doğru kaynak FotMob/Sofascore (#120/#148), Mackolik değil.**

---

## 1) ERİŞİLEBİLİRLİK & API KALİTESİ (en kritik test)

| Host | Durum |
|---|---|
| `arsiv.mackolik.com` | ✅ Canlı (Akamai CDN, legacy ASP.NET `.aspx`) |
| `www.mackolik.com` | ✅ Canlı (modern site) |
| `goapi.mackolik.com/livedata` | ❌ **DNS YOK** — temiz JSON feed ölmüş (2018 GitHub repo'su artık geçersiz) |
| `api.mackolik.com`, `widget.`, `m.iddaa.` | ❌ DNS yok |
| `arsiv.../AjaxHandler/*.ashx` | ⚠️ Var ama JSON yerine HTML stub döndü (komut arayüzü kilitli/değişmiş) |

**Sonuç:** Eskiden Sofascore/iddaa gibi temiz JSON çekebildiğimiz bir API **yok**. Entegrasyon =
`.aspx` sayfalarını **HTML parse** etmek (BeautifulSoup). Bu, Sofascore Playwright çözümümüzden
**daha kırılgan** (yapı değişince kırılır, geo/IP riski, nazik rate-limit şart).
→ **Entegrasyon maliyeti: YÜKSEK.**

---

## 2) MACKOLİK'TE GERÇEKTE NE VAR

**Tarihsel derinlik: OLAĞANÜSTÜ.** Maç detay sayfaları **1909'a** kadar geri gidiyor
(`Match/Default.aspx?id=<id>`). Türkiye futbolu baştan sona arşivlenmiş.

**Maç sayfası şablonu** (her maç için sekmeler): Skor · Tarih · Stadyum · **Hakem** · Teknik direktörler
· Son 5 form · Lig tablosu · **Kadrolar** · **İstatistik** · **İddaa oranları** · Karşılaştırma.

- **Eski maçlar (örn. 1980):** sadece temel alanlar dolu (skor, hakem, stad, TD, form). O dönem
  şut/possession verisi *üretilmiyordu* — Mackolik'in kusuru değil, tarihin.
- **Modern maçlar (2017+):** şut / topla oynama / kadro / dakika-dakika olay / **geçmiş iddaa oranı**
  sekmeleri dolu. (Template doğrulandı; tam doluluk oranı bir scrape-spike ile ölçülmeli.)

**İstatistik bankası:** oyuncu/kaleci/takım istatistikleri, **piyasa değerleri**, **hakem veritabanı**,
stadyum DB, kadrolar. Ülke + Sezon filtresi (2001-2025), geniş uluslararası + Türkiye kapsamı.

---

## 3) BİZDE NE VAR / NE EKSİK (19.315 maç · E0/I1/SP1/F1/T1/D1 · 2017-2025)

| Alan | Bizdeki doluluk | Mackolik doldurur mu? |
|---|---|---|
| Skor / İY skor / sonuç | %100 | — (gerek yok) |
| Korner | %99 | — |
| Sarı/kırmızı kart | %100 | — |
| İsabetli şut | %100 | — |
| Seyirci | %100 | — |
| 1X2 kapanış oranı | %95 | — (iddaa'dan canlı zaten) |
| A/Ü 2.5 oranı | %72 | kısmen (mirror) |
| **KG (BTTS) geçmiş oranı** | **%1** | ⚠️ kısmen — ama iddaa'dan ileriye canlı alıyoruz |
| **TOPLAM şut** | **%0** | ✅ modern maçlarda var (ama isabetli şutumuz zaten %100) |
| **HAKEM** | **%18** | ✅✅ Mackolik'in güçlü yanı (tam hakem DB) |
| **xG** | **%30** (sadece Understat ligleri) | ❌ **YOK — Mackolik xG hesaplamaz** |

---

## 4) MACKOLİK NE KATAR — NE KATMAZ (dürüst muhasebe)

### ✅ Gerçek katkı (dar ama gerçek)
1. **Hakem verisi (18% → tam).** Hakem; kart/penaltı/korner pazarları için bilinen sinyal.
   Modeli zenginleştirir — *yeni bir niş pazar* (kart üst/alt) açabilir.
2. **Cross-source DOĞRULAMA.** Football-Data ile çapraz kontrol → skor/oran hatalarını yakalama,
   veri kalitesi auditi. (Tek kaynak riskini azaltır.)
3. **Türkiye derinliği + isim eşleme.** Mackolik, Türk takım/oyuncu isim kanonikleştirmesinde altın
   standart. T1 ve alt ligler için ileride değerli (şu an sadece Süper Lig modelliyoruz).
4. **Kadro/sakatlık geçmişi.** Bekleyen "injury feature" (#119) için besleyebilir.

### ❌ Katmadığı (yanlış beklentiyi önle)
1. **xG YOK.** En kritik model boşluğumuz (T1 xG). Mackolik bir sonuç/oran sitesi, analitik/xG
   sağlayıcısı değil. **Bu en önemli nokta** — "Mackolik = daha çok xG" sanılırsa yanlış olur.
2. **İleriye dönük oran zaten bizde.** Canlıyı iddaa'nın *kaynağından* alıyoruz; Mackolik sadece
   iddaa oranını aynalar → canlı için **gereksiz**.
3. **Avrupa ileri istatistik** zaten Football-Data + Understat ile karşılanıyor.

---

## 5) TRADING'E ETKİSİ (asıl soru)

**Kritik gerçeklik kontrolü:** Bu sezon kanıtladık — sistem kapanış oranlarına karşı **~0/negatif edge**.
Darboğaz **veri HACMİ değil**; kapanış çizgisinin (closing line) çok verimli olması ve modelin onu
geçememesi (naive xG modeli kapanışı yenemedi — kanıtlandı).

Sonuç: Mackolik'ten **hakem / toplam-şut / Türkiye-arşivi** eklemek →
- **FEATURE** ekler, otomatik **EDGE** eklemez.
- Edge sorusu = CLV (closing line value). Daha fazla *betimleyici* geçmiş istatistik, verimli bir
  kapanış çizgisine karşı nadiren CLV üretir.
- **Tek somut trading kapısı:** hakem verisi → **kart/korner pazarı** (şu an oynamadığımız, iddaa'da
  olan) için *yeni* bir niş model. Bu denenebilir ama spekülatif.

→ **Trading'e net etki: DÜŞÜK-ORTA. Veri-kalitesi/çapraz-doğrulama için ORTA.**

---

## 6) MALİYET / FAYDA & TAVSİYE

| Seçenek | Maliyet | Fayda | Karar |
|---|---|---|---|
| Full Mackolik HTML scraper (tüm maç+stat) | YÜKSEK (kırılgan, geo, bakım) | DÜŞÜK-ORTA | ❌ Şimdi yapma |
| **Hakem DB backfill** (dar scrape) | ORTA | ORTA (kart pazarı + feature) | ⭐ Değerli, ama opsiyonel |
| **Cross-source audit** (örneklem) | DÜŞÜK | ORTA (kalite) | ⭐ İyi ROI |
| T1 xG için Mackolik | — | ❌ (xG yok) | ❌ Yanlış kaynak |
| T1 xG için **FotMob/Sofascore** (#120/#148) | ORTA | YÜKSEK (gerçek boşluk) | ✅ Asıl öncelik |

### Önerilen sıra
1. **Şimdi:** Mackolik'e full yatırım YAPMA. 1-2 haftalık canlı gözlemi bekle.
2. **İstersek dar spike:** Hakem verisi backfill (T1 öncelik) — kart/korner niş pazarı denemesi için.
3. **Asıl model boşluğu (T1 xG):** Mackolik değil, **FotMob/Sofascore** (gerçek xG sağlar).
4. **Düşük efor değer:** Football-Data anomali auditinde Mackolik'i ikinci-kaynak doğrulayıcı yap.

---

## Kaynaklar
- arsiv.mackolik.com/Canli-Sonuclar · /Statistics/Default.aspx · /Match/Default.aspx?id=333721
- DNS/endpoint probe (yerel): goapi/api/widget subdomain'leri ölü; AjaxHandler HTML stub.
- Bizdeki doluluk: matches_v2 (19.315 maç) doluluk sorgusu.
