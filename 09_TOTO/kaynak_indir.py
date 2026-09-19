"""
TOTO · KAYNAK İNDİRİCİ (yerel, geçmiş test için)
================================================
Açık veri kaynaklarını 09_TOTO/veri_cache/ altına indirir (git ve imaj dışı —
'*cache*' kalıbı .gitignore/.dockerignore'da). BetAgents'ın hiçbir dosyasına
ve tablosuna dokunmaz.

  fd/      football-data ana ligler (sezon başına CSV, kapanış oranları dahil)
  fd_new/  football-data ek ligler (İsveç, Norveç, Finlandiya, Brezilya, Japonya…)

⚠️ football-data.co.uk Türkiye'den DNS düzeyinde ENGELLİ (BetAgents
   scrapers/football_data_downloader.py aynı nedenle yansıyı kullanır). Günlük
   güncellenen birebir GitHub yansısı: huhao930422-debug/football-odds-mirror.
  intl/    milli maç sonuçları (martj42/international_results, 1872→bugün)

Kullanım:  python kaynak_indir.py [--yenile]
"""
from __future__ import annotations

import sys
import time
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parent / "veri_cache"
UA = {"User-Agent": "Mozilla/5.0 (toto-panel; arastirma)"}

YANSI = "https://raw.githubusercontent.com/huhao930422-debug/football-odds-mirror/main/data/"
ANA_LIGLER = {"E0": "premier-league", "E1": "championship", "E2": "league-one", "D1": "bundesliga",
              "D2": "bundesliga-2", "I1": "serie-a", "I2": "serie-b", "SP1": "la-liga", "SP2": "la-liga-2",
              "F1": "ligue-1", "F2": "ligue-2", "N1": "eredivisie", "B1": "jupiler-league",
              "P1": "primeira-liga", "T1": "super-lig", "SC0": "scottish-premiership",
              "SC1": "scottish-championship"}
SEZONLAR = ["1920", "2021", "2122", "2223", "2324", "2425", "2526", "2627"]
EK_LIGLER = {"BRA": "brazil", "DNK": "denmark", "FIN": "finland", "JPN": "japan", "NOR": "norway",
             "SWE": "sweden", "USA": "usa"}


def indir(url: str, hedef: Path, yenile: bool = False) -> str:
    if hedef.exists() and hedef.stat().st_size > 200 and not yenile:
        return "var"
    hedef.parent.mkdir(parents=True, exist_ok=True)
    for deneme in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                b = r.read()
            if len(b) < 200:
                return f"bos({len(b)})"
            hedef.write_bytes(b)
            return f"{len(b) // 1024}KB"
        except Exception as e:
            if "404" in str(e):
                return "404"
            time.sleep(3 + 5 * deneme)
    return "HATA"


def main(yenile: bool = False) -> None:
    for s in SEZONLAR:
        for lig, slug in ANA_LIGLER.items():
            yenile_bu = yenile or s in ("2526", "2627")      # sürmekte olan sezonlar tazelensin
            r = indir(f"{YANSI}{slug}/season-{s}.csv", KOK / "fd" / f"{lig}_{s}.csv", yenile_bu)
            if r not in ("var",):
                print(f"fd {lig}_{s}: {r}", flush=True)
                time.sleep(0.3)
    for lig, slug in EK_LIGLER.items():
        r = indir(f"{YANSI}{slug}/all-seasons.csv", KOK / "fd_new" / f"{lig}.csv", True)
        print(f"fd_new {lig}: {r}", flush=True)
        time.sleep(0.3)
    r = indir("https://raw.githubusercontent.com/martj42/international_results/master/results.csv",
              KOK / "intl" / "results.csv", True)
    print(f"intl results: {r}", flush=True)
    print("BITTI", flush=True)


if __name__ == "__main__":
    main("--yenile" in sys.argv)
