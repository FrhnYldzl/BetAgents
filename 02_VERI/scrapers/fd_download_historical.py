"""
v2 — B1: 2017-2021 historical sezonları indir
"""
from __future__ import annotations
import urllib.request as ur
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent.parent / "02_VERI" / "raw"

LEAGUE_SLUGS = {
    "T1": "super-lig", "E0": "premier-league", "D1": "bundesliga",
    "SP1": "la-liga", "I1": "serie-a", "F1": "ligue-1",
}
SEASONS = ["1718", "1819", "1920", "2021"]
BASE = "https://raw.githubusercontent.com/huhao930422-debug/football-odds-mirror/main/data"


def download():
    n = 0
    for our_code, slug in LEAGUE_SLUGS.items():
        for ss in SEASONS:
            out = RAW_DIR / f"{our_code}_{ss}.csv"
            if out.exists():
                print(f"  {our_code}_{ss}: zaten var")
                continue
            url = f"{BASE}/{slug}/season-{ss}.csv"
            try:
                r = ur.urlopen(url, timeout=15)
                data = r.read()
                out.write_bytes(data)
                print(f"  {our_code}_{ss}: {len(data):,} bytes")
                n += 1
            except Exception as e:
                print(f"  {our_code}_{ss}: ERR {str(e)[:60]}")
    print(f"\n[OK] {n} CSV indirildi (yenisi)")


if __name__ == "__main__":
    download()
