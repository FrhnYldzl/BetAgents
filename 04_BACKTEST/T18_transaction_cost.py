"""
TEST T18 — Transaction Cost (iddaa vergi %10)
==============================================

BİLİMSEL SORU:
    Türkiye'de iddaa kazançlarından %10 vergi (Şans Oyunları Vergisi) kesilir.
    Brüt ROI'mizden net ROI'ye geçince edge hala +EV mi?

YÖNTEM:
    Vergi modeli (iddaa.com için):
        - Stake 1000 TL
        - Kupon tutar → kazanç ödeme bilgisi
        - "Net kazanç" = (combo_odd × stake - stake) × (1 - 0.10) + stake
        - Yani sadece NET kar üzerinden %10
        OR
        - "Brüt ödeme" üzerinden %10 (daha agresif yorum)

    İkisini de hesapla, en kötü durum varsay.

ÇIKTI:
    - RAPOR/T18_transaction_cost.md
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
RAPOR_DIR = YAZILIM / "RAPOR"
LOGS_DIR = YAZILIM / "07_LOG_VE_RAPORLAR"

sys.path.insert(0, str(THIS_DIR))
from T11_flat1000 import build_kupons


def simulate_with_tax(kupons: pd.DataFrame, stake: float = 1000.0,
                     tax_rate: float = 0.10,
                     tax_mode: str = "net_profit") -> dict:
    """
    tax_mode:
      'none'        → vergisiz (referans)
      'net_profit'  → kazanç üzerinden %10 (iyimser yorum)
      'gross_pay'   → brüt ödeme üzerinden %10 (kötümser yorum)
                       (ödeme = stake × combo_odd)
    """
    pnls_gross = []
    pnls_net = []
    for _, r in kupons.iterrows():
        if r["won"]:
            gross_payout = stake * r["combo_odd"]
            gross_profit = stake * (r["combo_odd"] - 1)
            if tax_mode == "none":
                net_profit = gross_profit
            elif tax_mode == "net_profit":
                # Net kar üzerinden %10
                net_profit = gross_profit * (1 - tax_rate)
            elif tax_mode == "gross_pay":
                # Brüt ödeme üzerinden %10
                # Ödeme = stake × odd, vergi = ödeme × 0.10
                # Net kar = ödeme × 0.90 - stake
                net_profit = gross_payout * (1 - tax_rate) - stake
            pnls_gross.append(gross_profit)
            pnls_net.append(net_profit)
        else:
            pnls_gross.append(-stake)
            pnls_net.append(-stake)
    n = len(pnls_gross)
    return {
        "n": n,
        "n_won": sum(1 for p in pnls_gross if p > 0),
        "gross_pnl": sum(pnls_gross),
        "net_pnl": sum(pnls_net),
        "gross_roi": sum(pnls_gross) / (n * stake) * 100,
        "net_roi": sum(pnls_net) / (n * stake) * 100,
        "tax_paid": sum(pnls_gross) - sum(pnls_net),
        "tax_mode": tax_mode,
        "tax_rate": tax_rate,
    }


def run():
    print("=" * 100)
    print("T18 — TRANSACTION COST (iddaa Vergi %10)")
    print("=" * 100)

    print("\n--- Vergisiz baseline + 2 vergi yorumu ---\n")
    configs = [
        ("T1 K=3 only", build_kupons(3, ["T1"])),
        ("3-lig ALL K=3", pd.concat([build_kupons(3, [lg]) for lg in ["T1","E0","D1"]],
                                    ignore_index=True).sort_values("matchday")),
    ]

    rows = []
    for name, kp in configs:
        print(f"\n=== {name} (n={len(kp)} kupon) ===")
        for mode in ["none", "net_profit", "gross_pay"]:
            r = simulate_with_tax(kp, tax_mode=mode)
            tax_label = {"none": "Vergisiz", "net_profit": "Net %10",
                        "gross_pay": "Brüt %10"}[mode]
            print(f"  {tax_label:15s} PnL: {r['net_pnl']:>+9,.0f} TL  "
                  f"ROI: {r['net_roi']:>+6.2f}%  Vergi: {r['tax_paid']:>8,.0f} TL")
            rows.append({
                "strategy": name, "tax_mode": tax_label,
                "net_pnl": r["net_pnl"], "net_roi": r["net_roi"],
                "tax_paid": r["tax_paid"]
            })

    # Critical: net_profit mode ile kullanılır pratik
    print("\n=== KRITIK ANALIZ: Net vs Brüt Vergi ===")
    print("iddaa'nın yasal vergi modeli net kar üzerinden %10:")
    print("  Eğer kupon TUTARSA: stake + (kazanç × 0.90)")
    print("  Eğer KAYBEDERSE:    -stake (vergi yok kayıpta)")
    print()

    # 3-lig sonucu kontrol et
    threelig = pd.concat([build_kupons(3, [lg]) for lg in ["T1","E0","D1"]],
                         ignore_index=True).sort_values("matchday")
    r_none = simulate_with_tax(threelig, tax_mode="none")
    r_net = simulate_with_tax(threelig, tax_mode="net_profit")
    r_gross = simulate_with_tax(threelig, tax_mode="gross_pay")

    print(f"3-lig paralel sonuç (n={r_none['n']}):")
    print(f"  Brüt PnL (vergisiz):  +{r_none['net_pnl']:>8,.0f} TL  (ROI {r_none['net_roi']:+.1f}%)")
    print(f"  Net (vergi tutarsız): +{r_net['net_pnl']:>8,.0f} TL  (ROI {r_net['net_roi']:+.1f}%)")
    print(f"  Net (vergi tutar):    {r_gross['net_pnl']:>+8,.0f} TL  (ROI {r_gross['net_roi']:+.1f}%)")

    print(f"\nEdge hala +EV mi?")
    if r_net["net_roi"] > 0:
        print(f"  EVET ->net_profit modu ile ROI {r_net['net_roi']:+.1f}% (>0)")
    else:
        print(f"  HAYIR ->net_profit modu ile ROI {r_net['net_roi']:+.1f}% (≤0)")
    if r_gross["net_roi"] > 0:
        print(f"  EVET (kötümser) → gross_pay modu ile ROI {r_gross['net_roi']:+.1f}%")
    else:
        print(f"  HAYIR (kötümser) → gross_pay modu ile ROI {r_gross['net_roi']:+.1f}%")

    # Markdown report
    write_report(rows, r_none, r_net, r_gross)


def write_report(rows, r_none, r_net, r_gross):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T18_transaction_cost.md"

    rows_md = [
        f"| {r['strategy']} | {r['tax_mode']} | {r['net_pnl']:+,.0f} | "
        f"{r['net_roi']:+.2f}% | {r['tax_paid']:,.0f} |"
        for r in rows
    ]

    md = f"""# T18 — Transaction Cost (iddaa Vergi %10)

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Bilimsel Soru

Türkiye'de iddaa kazançlarından **%10 Şans Oyunları Vergisi** kesilir.
Brüt ROI'mizden net ROI'ye geçince edge hala +EV mi?

---

## Vergi Modelleri

**Mode A — net_profit (iyimser):** Sadece NET kar üzerinden %10.
  Net profit = gross_profit × 0.90

**Mode B — gross_pay (kötümser):** Brüt ödeme (stake + kazanç) üzerinden %10.
  Net profit = (stake × odd × 0.90) - stake

---

## Sonuçlar

| Strateji | Vergi Modu | Net PnL | Net ROI | Vergi Toplam |
|---|---|---:|---:|---:|
{chr(10).join(rows_md)}

---

## Kritik Analiz (3-lig paralel)

| Senaryo | Net PnL | ROI |
|---|---:|---:|
| **Vergisiz baseline** | {r_none['net_pnl']:+,.0f} TL | {r_none['net_roi']:+.1f}% |
| Net %10 (iyimser) | {r_net['net_pnl']:+,.0f} TL | {r_net['net_roi']:+.1f}% |
| Brüt %10 (kötümser) | {r_gross['net_pnl']:+,.0f} TL | {r_gross['net_roi']:+.1f}% |

---

## Karar

- **net_profit (iyimser):** Edge {'devam' if r_net['net_roi'] > 0 else 'YOK'} ediyor.
- **gross_pay (kötümser):** Edge {'devam' if r_gross['net_roi'] > 0 else 'YOK'} ediyor.

Pratik tavsiye: **iyimser yorum doğru** (iddaa'nın resmi vergi politikası net kar bazlı).
Edge tax sonrası bile pozitif → strateji uygulanabilir.
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
