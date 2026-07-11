"""🛡 TEMKİNLİ — geriye uyumluluk shim'i.

Ajan mantığı agents.py'ye taşındı (TEMKİNLİ + MEMUR + AVCI tek profil
motorunda). Bu modül eski import/CLI'ler kırılmasın diye duruyor.
"""
from __future__ import annotations

import sys

from agents import run_profile, ensure_portfolio as _ensure

PID = "TEMKINLI_V1"


def ensure_portfolio() -> None:
    _ensure(PID)


def run(place: bool = True):
    return run_profile(PID, place=place)


if __name__ == "__main__":
    run(place="--place" in sys.argv)
