"""
SP1, I1, F1 ligleri için mirror'dan CSV indirme.
"""
from __future__ import annotations

import urllib.request as ur
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
RAW_DIR = THIS_DIR.parent.parent / "02_VERI" / "raw"

EXTRA_LEAGUES = {
    "SP1": "la-liga",
    "I1": "serie-a",
    "F1": "ligue-1",
}
SEASONS = ["2122", "2223", "2324", "2425", "2526"]

BASE = "https://raw.githubusercontent.com/huhao930422-debug/football-odds-mirror/main/data"


def download():
    n_total = 0
    for our_code, slug in EXTRA_LEAGUES.items():
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
                print(f"  {our_code}_{ss}: {len(data):,} bytes indirildi")
                n_total += 1
            except Exception as e:
                print(f"  {our_code}_{ss}: ERR {str(e)[:60]}")
    print(f"\n[OK] {n_total} CSV indirildi")


if __name__ == "__main__":
    download()
