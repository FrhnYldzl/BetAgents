# SÜPER TOTO — veri › model › ajanlar › Toto Master

BetAgents'tan **ayrı** bir ürün. BetAgents ile ortak olanlar yalnızca şunlar:

- aynı veritabanı sunucusu, ama yalnız `toto_*` tabloları,
- ortak bağlantı yardımcısı (`02_VERI/db.py`),
- paneldeki gezinme girişi ("SÜPER TOTO" bölümü).

Toto, BetAgents tablolarına yazmaz ve BetAgents kodu çağırmaz. BetAgents de Toto'ya dokunmaz.

## Akış

```
DATA     sportoto.py      Spor Toto programı, sonuç, ikramiye (resmi API). Devir ve D türetilir.
         canli.py         iddaa'nın o anki 1/0/2 fiyatı (Toto'nun kendi çekimi)
         kaynaklar.py     football-data yansısı (24 lig) + 1872'den bugüne milli maçlar (yerel)
MODEL    kalabalik.py     q: kalabalık hangi sonucu ne sıklıkla işaretliyor (β_aile·log p + popülerlik)
         deger.py         sistem kuponunun beklenen değeri (15–14 tam, 12–13 önem örneklemesi) + kurucu
AGENTS   ajanlar.py       PİYASA · ELO · FORM · H2H — her biri 1/0/2 olasılığı + gerekçe
         pazar.py         Kelly bahisçileri pazarı ("Polymarket arka ucu"): servet ağırlıklı fiyat
MASTER   canli.analiz     P (pazar) × q (kalabalık) × havuz → profil × bütçe kuponları, gerekçeleriyle
```

## Üretim (Railway)

- `start.py`, `toto_worker.py`'yi ayrı bir süreç olarak başlatır. Kapatmak için `TOTO_WORKER=0`.
- Zamanlayıcının işleri:
  - saatlik senkron,
  - günde üç analiz (09:05, 15:05, 21:05 TR),
  - kapanışa 3 saat kala son analiz,
  - sonuç açıklanınca kâğıt kuponları kapatma, cüzdanları güncelleme ve dersi yazma.
- Ağır geçmiş veri üretimde işlenmez. Ajanların hafızası `model_durum.json`, kalabalık modeli `model_parametre.json` dosyasından okunur.
- Panel: `08_AI_TRADER/app_v2.py` › SÜPER TOTO. Sayfalar `toto_panel.py`'de. Hata olursa yalnız Toto sayfası uyarı gösterir.

## Yerel bakım (haftada bir)

```
python 09_TOTO/kaynak_indir.py     # açık veri (football-data yansısı + milli maçlar) → veri_cache/
python 09_TOTO/durum.py            # ajan hafızası → model_durum.json
python 09_TOTO/veri_seti.py        # geçmiş test veri seti (ajan görüşleri, sızıntısız)
python 09_TOTO/kalibrasyon.py      # kalabalık modeli + cüzdanlar → model_parametre.json
python 09_TOTO/geri_test.py        # ileriye yürüyen geçmiş test (~1 saat)
python 09_TOTO/gt_ozet.py          # panelin Geçmiş Test sayfası → geri_test_ozet.json
```

Önizleme, üretime dokunmadan çalışır:

```
python 09_TOTO/yerel.py              # SQLite önizleme DB'sine senkron + analiz
python 08_AI_TRADER/onizleme.py      # http://127.0.0.1:8610 → SÜPER TOTO
```

## Oyun kuralları (oyun planı)

- 15 maç, her maça 1/0/2. Birden çok işaret sistem kuponu olur ve kolon sayısı çarpılır.
- Bir bilette en çok 2.500 kolon. Kolon bedeli 10 TL (18.03.2025'ten beri).
- Oyun, ilk maçın başlamasıyla kapanır. Yeni program, önceki program kapanınca satışa açılır.
- Dağıtılan tutar, KDV'siz hasılatın %83'üdür. Brüt hasılat üzerinden yaklaşık %69 eder.
- Kademe payları: 15 → %35, 14 → %20, 13 → %20, 12 → %25.
- Bir kolon yalnız bildiği en üst dereceden ödeme alır.
- Kazananı çıkmayan kademenin tutarı sonraki haftaya devreder.
