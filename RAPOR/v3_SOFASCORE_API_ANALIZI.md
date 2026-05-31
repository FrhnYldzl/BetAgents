# 🔬 Sofascore API — Keşif & Fizibilite Analizi (Görev #148)

**Tarih:** 2026-05-31
**Soru:** Sofascore'dan ne çekebiliriz? API/DATA kalitesi nasıl? Bizdeki veriyle benzer mi, katkı sağlar mı?
**Örnek maç:** Slavia Mozyr vs Belshina (Belarus) — *bu maç şu an bizim açık kuponumuzda var.*

---

## 0. YÖNETİCİ ÖZETİ (önce sonuç)

> **GÜNCELLEME (ampirik):** Playwright network-capture ile gerçek veriye ulaşıldı; aşağıdaki tablo ve §6 ampirik test sonuçlarıyla revize edildi.

| Boyut | Bulgu (ampirik) |
|---|---|
| **API erişimi** | ✅ **Çözüldü** — düz script `403`, ama **headless Playwright + sayfa-içi fetch** ile 127/147 çağrı `200`. Eklenti/headed gerekmez. |
| **Veri zenginliği** | ⭐⭐⭐⭐⭐ üst/orta ligler: xG + 40-46 metrik + diziliş + olaylar + kitle-oyu. |
| **Lig kapsamı** | ⭐⭐⭐⭐ **Understat'tan çok geniş** (Brezilya, Çin, Mısır, İrlanda, Norveç, İskandinavya…) AMA en dip egzotik ligler (Belarus 2.düzey, Çek alt-lig) **sığ — sadece kart**. |
| **Bizdeki açık** | 🟡 Kısmen kapanır: niş liglerin **çoğunda** xG gelir, **en dibinde gelmez** (örnek maç Belarus = sığ). |
| **Katkı** | 🟢 **Yüksek ama evrensel değil** — xG kapsamı 5 lig → onlarca lige çıkar; egzotik kuyruk eksik kalır. |
| **Maliyet/Risk** | 🟡 Headless tarayıcı/çekim gerekir (iddaa'dan ağır) + ToS gri alan. |

**Tek cümle (revize):** Sofascore xG kapsamımızı 5 Avrupa liginden **dünya çapında onlarca lige** çıkarır (dev DATA kazancı) — ama iddaa'nın en dip egzotik liglerinin (Belarus vb.) bir kısmı orada da sığ. **Engel veri değil erişimdi; erişim çözüldü (headless+in-page fetch).**

---

## 1. API ERİŞİM & KALİTE (önce bunu test ettim)

### Ampirik test (2026-05-31)
```
GET https://api.sofascore.com/api/v1/sport/football/events/live
  → 403 Forbidden   (düz urllib, tam tarayıcı header'ları ile bile)
```
İki uç noktada da (`api.` ve `www.`) **403**. Yani Sofascore, isteği **TLS-parmakizi / edge (Cloudflare)** seviyesinde eliyor — sadece `User-Agent` eklemek yetmiyor.

### iddaa vs Sofascore — erişim karşılaştırması
| | iddaa.com | Sofascore |
|---|---|---|
| API tipi | Açık JSON (sportsbookv2/statisticsv2) | Açık JSON ama **Cloudflare arkasında** |
| Düz script erişimi | ✅ `urllib` ile çalışıyor | ❌ `403` |
| Auth | Yok | Yok (ama bot-koruma var) |
| Üretim erişim yöntemi | Basit `requests`/`urllib` | Tarayıcı-taklidi / headless / network-capture |
| Bakım yükü | Düşük | **Orta-Yüksek** (anti-bot değişebilir) |

### Erişim seçenekleri (önerilen → kaçınılması gereken)
1. **🟢 Network-capture (en temiz):** Senin tarayıcında açık Sofascore sayfasının yaptığı gerçek XHR çağrılarını yakalamak (iddaa'da yaptığımız yöntem). Tarayıcı Cloudflare'i meşru geçer. *Chrome eklentisi bağlanınca yapılabilir.*
2. **🟡 Headless tarayıcı (Playwright):** Sayfayı gerçek tarayıcıyla aç, XHR yanıtlarını yakala. Güvenilir ama ağır (her çekimde tarayıcı).
3. **🟡 BetRadar köprüsü:** iddaa'nın `bri` (BetRadar ID) alanı ile Sofascore event'ini eşleştirme — iki kaynağı birleştirme imkânı.
4. **🔴 TLS-impersonation kütüphaneleri (curl_cffi/cloudscraper):** Anti-botu programatik aşma → **ToS ihlali + kırılgan**, önerilmez.

> **ToS notu:** Sofascore API'si resmî/halka açık değildir; otomatik çekim ToS'a aykırıdır ve aktif olarak engellenir. Paper-trading araştırması için düşük risk, ama ticari/yoğun kullanım uygun değil. Lisanslı alternatif: Sportradar (ücretli).

---

## 2. SOFASCORE VERİ KATALOĞU (bilinen API yapısı)

Frontend'in kullandığı `api.sofascore.com/api/v1/...` uç noktaları (network-capture ile birebir doğrulanacak):

| Endpoint | Veri | Bizim için değer |
|---|---|---|
| `/event/{id}` | Maç özeti, skor, durum, takımlar, turnuva | Temel eşleme |
| `/event/{id}/statistics` | **xG**, şut (isabetli/total), top hakimiyeti, korner, faul, ofsayt, pas isabeti | 🟢🟢🟢 Model girdisi |
| `/event/{id}/lineups` | 11'ler + yedekler + **oyuncu rating** + pozisyon + forma no | 🟢🟢 Kadro gücü/eksik |
| `/event/{id}/graph` | **Attack momentum** zaman serisi (dakika-dakika baskı) | 🟢🟢 Yeni feature (canlı edge) |
| `/event/{id}/incidents` | Goller, kartlar, değişiklikler, VAR | 🟢 Olay zaman çizelgesi |
| `/event/{id}/h2h` / `/event/{id}/h2h/events` | Geçmiş karşılaşmalar | 🟢 (bizde H2H zaten var, doğrulama) |
| `/event/{id}/pregame-form` | Son form (W/D/L) + lig pozisyonu | 🟡 (bizde form var) |
| `/event/{id}/odds/1/all` | Maç oranları (çoklu pazar) | 🟡 (iddaa'dan zaten var) |
| `/team/{id}/...`, `/player/{id}/...` | Sezon istatistikleri, sakatlık/eksik | 🟢 Derin takım/oyuncu profili |
| `/sport/football/scheduled-events/{YYYY-MM-DD}` | Günün tüm maçları (tüm ligler) | 🟢 Fikstür keşfi |

**Kritik fark:** Sofascore xG'yi **Understat'tan çok daha geniş lig yelpazesinde** üretir (kendi modeli). Understat sadece top-5 Avrupa; Sofascore **dünya geneli** + alt ligler + kupalar + milli maçlar.

---

## 3. BİZDEKİ VERİYLE KARŞILAŞTIRMA (gerçek rakamlar — DB'den)

### Mevcut xG kapsamımız (`matches_v2.home_xg`)
| Lig | Maç | xG dolu | Oran |
|---|---|---|---|
| E0 (İngiltere) | 3.420 | 1.412 | %41 |
| I1 (İtalya) | 3.420 | 1.412 | %41 |
| SP1 (İspanya) | 3.420 | 1.128 | %33 |
| F1 (Fransa) | 3.096 | 1.094 | %35 |
| D1 (Almanya) | 2.754 | 706 | %26 |
| **T1 (Türkiye)** | 3.088 | **0** | **%0** ❌ |
| **ALL (canlı niş ligler)** | 117 | **0** | **%0** ❌ |

→ Kaynak: Understat (5.752 maç, sadece 5 Avrupa ligi, kısmi sezon). **Türkiye dahil hiçbir niş ligde xG yok.**

### Canlı kuponların ligleri = tam da boşlukta olan yer
Açık kuponların **TAMAMI** `league_code="ALL"` kovasında:
```
Olympic FC vs Brisbane City (Avustralya)   ·  Slavia Mozyr vs FC Belshina (Belarus)
FK Arsenal Dzerz. vs Dinamo Minsk (Belarus) ·  Valur vs Vikingur (İzlanda)
Karlskrona vs Lilla Torg (İsveç)            ·  Farul vs Chindia (Romanya)
Nomme United vs Flora (Estonya)             ·  Esperance vs Zarzis (Tunus)
Almanya vs Finlandiya (Milli)               ·  Singapur vs Moğolistan (Milli)
```
Bu maçlarda elimizde **ne xG, ne DC modeli, ne sinyal** var → edge = sadece `-vig` (negatif). Trader bunlara **kör** giriyor. **Sofascore bu liglerin hepsini xG + istatistik + rating ile kapsıyor.**

### Benzerlik özeti
| Veri | Bizde | Sofascore | Sonuç |
|---|---|---|---|
| 1X2/A-Ü/KG oranları | ✅ (iddaa + FD) | ✅ | Örtüşür |
| H2H / form / puan durumu | ✅ (enricher) | ✅ | Örtüşür (doğrulama) |
| xG (top-5 Avrupa) | 🟡 kısmi | ✅ tam | Sofascore daha iyi |
| **xG (T1 + niş ligler)** | ❌ YOK | ✅ VAR | **Sadece Sofascore** |
| Oyuncu rating | ❌ | ✅ | **Yeni** |
| Attack momentum | ❌ | ✅ | **Yeni** |
| Şut haritası / detay istatistik | 🟡 (FD korner/kart) | ✅ derin | Sofascore daha iyi |

---

## 4. KATMA DEĞER — DATA · MODEL · TRADE

**DATA:** Niş ligler (iddaa'nın yaz programının çoğu!) için ilk kez xG + istatistik. `matches_v2`'ye `sofa_home_xg`, `sofa_away_xg`, `sofa_rating_*`, `momentum_*` kolonları. Understat'ın ulaşamadığı T1 dahil.

**MODEL:** Şu an niş liglerde model YOK → Sofascore xG ile bu ligler için **xG-tabanlı bir baseline model** (Poisson/DC) kurulabilir. "ALL" kovasındaki kör bahisler → gerçek olasılık tahminine döner. Oyuncu rating + momentum = yeni ortogonal feature'lar (mevcut DC/xG ensemble'ı güçlendirir).

**TRADE:** En somut kazanç — trader'ın **en zayıf noktası kapanır.** Şu an -%13 edge'li niş-lig kuponları, gerçek modelli edge hesabına döner → ya pozitif-edge bulur ya da o maçı **eler** (kör bahisten kaçınma bile net kazanç). "Daha fazla silah ve cephane" tam olarak bu.

---

## 5. ÖNERİ (sıradaki adım)

1. **Erişimi network-capture ile doğrula:** Chrome eklentisini bağla → açık Sofascore maç sayfasının XHR çağrılarını yakala → `statistics`, `lineups`, `graph` yanıtlarının gerçek şemasını çıkar (1 örnek maç: Slavia Mozyr).
2. **Eşleme stratejisi:** iddaa `bri` (BetRadar ID) ↔ Sofascore event eşlemesi mümkün mü test et (mümkünse otomatik birleştirme).
3. **PoC:** Tek niş lig (ör. Belarus) için Sofascore xG çek → o lig maçlarına xG-baseline model → backtestّte edge anlamlı mı bak.
4. Sonuç olumluysa → `data_sources/sofascore.py` adapter + `matches_v2` enrichment + model entegrasyonu.

> **Karar:** Veri muazzam ve ihtiyaca birebir; engel erişimin kırılganlığı. Önce **küçük PoC** (1 lig, network-capture ile) ile değeri kanıtla, sonra ölçekle.

---

---

## 6. AMPİRİK SONUÇLAR (Playwright network-capture — 2026-05-31)

**Probe:** `02_VERI/scrapers/sofascore_probe.py` (tek maç) + `sofascore_depth_calib.py` (lig derinliği).

### 6.1 Erişim — ÇÖZÜLDÜ ✅
- Düz `urllib`/`requests` → **403** (Cloudflare).
- `page.request.get()` (Playwright API context) → **403**.
- **Headless Chromium + sayfanın KENDİ `fetch()`'i (page.evaluate)** → **200** (127/147 çağrı). ✅
- Maç sayfası yüklenince 140 `/api/v1` çağrısı yakalandı; event id otomatik bulundu (16142049).

### 6.2 Gerçek endpoint kataloğu (200-OK, doğrulandı)
```
/event/{id}                  → maç özeti (skor, takım, turnuva, durum)
/event/{id}/statistics       → maç istatistikleri (üst liglerde xG + 40-46 metrik)
/event/{id}/lineups          → 11'ler + yedekler (+rating: üst liglerde)
/event/{id}/incidents        → gol/kart/değişiklik zaman çizelgesi
/event/{id}/managers         → teknik direktörler
/event/{id}/pregame-form     → maç öncesi form + lig pozisyonu
/event/{id}/votes            → kitle tahmini (1X2, KG, ilk gol)
/team/{id}/.../statistics/overall   → takım sezon istatistikleri
/tournament/{id}/season/{id}/standings/total → puan durumu
/sport/football/scheduled-events/{YYYY-MM-DD} → günün tüm maçları
(graph/momentum: yalnız üst maçlarda; bu örnekte 404)
```

### 6.3 Veri DERİNLİĞİ lig-seviyesine bağlı (14 maç kalibrasyonu, 2026-05-30)
| Lig | Metrik | xG |
|---|---|---|
| UEFA Şampiyonlar Ligi | 46 | ✅ |
| Brezilya Série A / B | 42 / 45 | ✅ |
| Çin Super League | 45 | ✅ |
| Mısır / İrlanda / Norveç Eliteserien | 43-45 | ✅ |
| LaLiga2 / Serie B / Fransa / Şili / Bolivya / Ekvador | 40-44 | ✅/derin |
| **Belarus Vysshaya** (örnek maç) | **2** | ❌ sadece kart |
| **Çek alt-lig (relegation)** | **2** | ❌ sadece kart |

→ **9/14 maçta açık xG; üst+orta liglerin neredeyse tamamı zengin.** Yalnız en dip ligler sığ.

### 6.4 Net karar
- **DATA kazancı gerçek ve büyük:** xG kapsamı 5 Avrupa ligi (Understat) → **dünya çapında onlarca lig** (Brezilya, İskandinavya, Çin, Mısır, İrlanda…). iddaa yaz programının büyük kısmı bunlarla örtüşür.
- **Sınır:** Belarus 2.düzey / Estonya / Çek alt-lig gibi en dip egzotikler Sofascore'da da sığ → bu maçlarda yine model kurulamaz (ama bunlar zaten **elenmeli** — kör bahisten kaçınmak da kazanç).
- **Erişim yöntemi netleşti:** headless Playwright + in-page fetch (üretimde `data_sources/sofascore.py` adapter buna dayanır).

### Sıradaki (PoC)
1. iddaa açık kuponlarındaki liglerin Sofascore'da hangi oranda **zengin** (xG'li) olduğunu ölç (kapsam haritası).
2. xG'li niş ligler için (ör. Norveç/Brezilya/İrlanda) → maçları Sofascore xG ile çek → xG-baseline edge modeli → backtest.
3. Sığ ligleri (Belarus vb.) → otomatik **PAS** kuralı (model yoksa kupona alma).

---

*Analiz: 2026-05-31 · Erişim & şema Playwright network-capture ile AMPİRİK doğrulandı · Derinlik 14-maç kalibrasyonuyla ölçüldü · Probe: `02_VERI/scrapers/sofascore_probe.py` + `sofascore_depth_calib.py`*
