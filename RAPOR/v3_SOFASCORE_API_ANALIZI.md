# 🔬 Sofascore API — Keşif & Fizibilite Analizi (Görev #148)

**Tarih:** 2026-05-31
**Soru:** Sofascore'dan ne çekebiliriz? API/DATA kalitesi nasıl? Bizdeki veriyle benzer mi, katkı sağlar mı?
**Örnek maç:** Slavia Mozyr vs Belshina (Belarus) — *bu maç şu an bizim açık kuponumuzda var.*

---

## 0. YÖNETİCİ ÖZETİ (önce sonuç)

| Boyut | Bulgu |
|---|---|
| **API erişimi** | ⚠️ **Cloudflare korumalı** — düz script `403` alıyor (iddaa'nın açık JSON'unun aksine). Tarayıcı-taklidi veya headless gerekir. |
| **Veri zenginliği** | ⭐⭐⭐⭐⭐ Sektördeki en derin ücretsiz kaynaklardan: xG, oyuncu rating, momentum, şut haritası, dizilişler. |
| **Lig kapsamı** | ⭐⭐⭐⭐⭐ **Neredeyse iddaa'nın sunduğu HER lig** (Belarus, Avustralya, İzlanda, Estonya, milli takımlar…). |
| **Bizdeki açık** | 🔴 Kritik: niş liglerde (`ALL` kovası) xG=0, model=YOK. **Sofascore tam bu boşluğu doldurur.** |
| **Katkı** | 🟢 **Yüksek** — trader'ın en zayıf noktasını (kör bahis) kapatma potansiyeli. |
| **Maliyet/Risk** | 🟡 Erişim kırılgan (anti-bot) + ToS gri alan. Üretimde bakım yükü iddaa'dan fazla. |

**Tek cümle:** Sofascore'un verisi muazzam ve tam ihtiyacımız olan niş ligleri kapsıyor; **engel veri değil, erişim** (anti-bot). Erişim çözülürse trader'a en büyük "cephane" bu olur.

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

*Analiz: 2026-05-31 · Erişim ampirik test edildi (403/Cloudflare) · Karşılaştırma DB'den gerçek rakamlarla · Endpoint kataloğu network-capture ile birebir doğrulanacak.*
