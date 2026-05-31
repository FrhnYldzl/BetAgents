"""
SELECTIVE EDGE v1.1 — Odds Anomaly Signal (GERÇEK cross-market checks)

v1.0 sorunu:
    "Anomaly" diye etiketlenmiş şey aslında favori bulucuydu — max(fair_prob).
    Bookmaker zaten favori dediği için "favori" sinyali üretmek edge değil.

v1.1 yaklaşımı — 5 gerçek bilim:

CHECK A — μ_total tutarlılığı (OU lines arası)
    OU1.5, OU2.5, OU3.5 üç ayrı Poisson μ tahmini verir.
    Aynı μ vermeli. std(μ) > 0.25 → bookmaker bir line'da hata var.

CHECK B — μ_total (OU) vs μ_total (1X2-implied)
    1X2 draw probability ile Poisson P(home==away|μ) eşleştir → μ_1X2
    OU2.5'ten μ_OU.
    |μ_1X2 - μ_OU| > 0.4 → markets uyuşmuyor.

CHECK C — Combo arbitrage (1X2_OU vs 1X2 × OU)
    iddaa.com "1 ve Üst" odd verir. Bağımsız olsalardı odd = (1X2.'1') × (OU.Üst)
    fp(1X2_OU) / [fp(1X2) × fp(OU)] = correlation factor.
    Aynı maç için MS-favori ve A/Ü negative correlated olur → factor < 1.
    Eğer factor > 1.05 → iddaa fazla iyimser combo'da → exploitable.

CHECK D — 1X2 favori vs Handikap consistency
    Sayısal olarak: 1X2 "1" implied prob ile HC-1.0 (home win by 2+) implied prob.
    Eğer fp(1X2.1) >> fp(HC-1.0.1)*1.5 → HC underestimates ev galibiyetini.

CHECK E — Overround dispersion
    Her pazarın overround'u farklı. std(overrounds) yüksekse bookmaker
    bazı pazara güvenmiyor (illiquid). dispersion >5pp → likit değil.

AGGREGATE — anomaly_strength:
    weighted_sum of checks, each producing 0-1 evidence.
    weighted average → final strength.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent.parent
sys.path.insert(0, str(YAZILIM / "02_VERI"))

import database as db


# ============================================================
# CORE HELPERS
# ============================================================

def _valid_odd(o):
    return o is not None and o > 1.001


def implied(odd: float) -> float:
    return 1.0 / odd if odd and odd > 0 else 0.0


def overround(odds: list[float]) -> float:
    return sum(implied(o) for o in odds) - 1.0


def fair_probs(odds: list[float]) -> list[float]:
    raw = [implied(o) for o in odds]
    s = sum(raw)
    if s == 0:
        return [0.0] * len(odds)
    return [r / s for r in raw]


def poisson_cdf(k: int, lam: float) -> float:
    """P(X <= k) for Poisson(lam)."""
    return sum((lam**j) * math.exp(-lam) / math.factorial(j)
               for j in range(k + 1))


def lambda_from_ou(fair_under: float, line: float, k_max: int | None = None) -> float | None:
    """Newton-Raphson μ from P(X<=k)=under for Poisson."""
    if fair_under is None or fair_under <= 0.001 or fair_under >= 0.999:
        return None
    if k_max is None:
        k_max = int(math.floor(line))
    lam = 2.5
    for _ in range(60):
        p = poisson_cdf(k_max, lam)
        diff = p - fair_under
        if abs(diff) < 1e-5:
            return lam
        deriv = -(lam**k_max) * math.exp(-lam) / math.factorial(k_max)
        if abs(deriv) < 1e-9:
            break
        lam = lam - diff / deriv
        lam = max(0.05, min(8.0, lam))
    return lam if 0.05 < lam < 8 else None


# ============================================================
# MARKET FETCH
# ============================================================

def get_match_odds(conn, iddaa_match_id: str, snapshot_id: str | None = None) -> dict:
    """Tüm pazar+selection odds'ları al."""
    if snapshot_id is None:
        row = conn.execute(
            "SELECT snapshot_id FROM iddaa_odds WHERE iddaa_match_id=? "
            "ORDER BY snapshot_id DESC LIMIT 1", (iddaa_match_id,)
        ).fetchone()
        if not row:
            return {}
        snapshot_id = row[0]

    rows = conn.execute(
        "SELECT market, selection, odd FROM iddaa_odds "
        "WHERE iddaa_match_id=? AND snapshot_id=?",
        (iddaa_match_id, snapshot_id)
    ).fetchall()
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        out.setdefault(r["market"], {})[r["selection"]] = r["odd"]
    return out


def _read_1x2(mkts: dict) -> tuple[float, float, float] | None:
    m = mkts.get("1X2", {})
    o1, ox, o2 = m.get("1"), m.get("0") or m.get("X"), m.get("2")
    if _valid_odd(o1) and _valid_odd(ox) and _valid_odd(o2):
        return fair_probs([o1, ox, o2])
    return None


def _read_ou(mkts: dict, line: str) -> tuple[float, float] | None:
    """Return (fair_under, fair_over)."""
    m = mkts.get(f"OU{line}", {})
    alt = m.get("Alt") or m.get("ALT")
    ust = m.get("Üst") or m.get("Ust") or m.get("UST")
    if _valid_odd(alt) and _valid_odd(ust):
        return fair_probs([alt, ust])
    return None


def _read_btts(mkts: dict) -> tuple[float, float] | None:
    """(fair_yes, fair_no)."""
    m = mkts.get("BTTS", {})
    var = m.get("Var") or m.get("Evet")
    yok = m.get("Yok") or m.get("Hayır") or m.get("Hayir")
    if _valid_odd(var) and _valid_odd(yok):
        return fair_probs([var, yok])
    return None


# ============================================================
# CHECK A — OU lines arası μ tutarlılığı
# ============================================================

def check_a_ou_mu_consistency(mkts: dict) -> dict:
    """OU1.5, OU2.5, OU3.5 → 3 μ tahmini → tutarlılık."""
    mus = {}
    for line_str, line_f in [("1.5", 1.5), ("2.5", 2.5), ("3.5", 3.5)]:
        ou = _read_ou(mkts, line_str)
        if ou:
            fp_under, _ = ou
            mu = lambda_from_ou(fp_under, line_f)
            if mu:
                mus[line_str] = mu

    if len(mus) < 2:
        return {"signal": 0.0, "mu_estimates": mus, "mu_std": None}

    vals = list(mus.values())
    mean = sum(vals) / len(vals)
    std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
    # std=0.0 → tam tutarlı (1.0). std>0.5 → tutarsız (0.0)
    consistency = max(0.0, 1.0 - std / 0.5)
    # Sinyal = inconsistency (yüksekse anomaly var)
    inconsistency = 1.0 - consistency
    return {
        "signal": inconsistency,        # 0-1, yüksek = anomaly
        "consistency": consistency,
        "mu_estimates": mus,
        "mu_mean": mean,
        "mu_std": std,
    }


# ============================================================
# CHECK B — OU μ vs 1X2-implied μ
# ============================================================

def check_b_ou_vs_1x2(mkts: dict) -> dict:
    """OU2.5 μ vs 1X2 draw-prob ile uyumlu μ."""
    ou = _read_ou(mkts, "2.5")
    one_x_two = _read_1x2(mkts)
    if not ou or not one_x_two:
        return {"signal": 0.0, "mu_ou": None, "mu_1x2": None, "delta": None}

    fp_under_ou, _ = ou
    mu_ou = lambda_from_ou(fp_under_ou, 2.5)

    # 1X2 draw prob → Poisson aynı skor prob.
    # Skor matrisi simplificasyonu: home_goals ~ Poi(λh), away_goals ~ Poi(λa)
    # P(draw) = Σ_k P(λh=k) × P(λa=k)
    # Total μ = λh + λa. Eğer simetrik dağılım varsa λh=λa=μ/2.
    # Asimetrik için: λh-λa biliyorsak çözebiliriz. Burada basit: |λh-λa| = inv_cdf(1X2 - imbalance)
    fp1, fpx, fp2 = one_x_two
    # Use a fixed μ search: λh+λa = μ, λh/(λh+λa) ~ fp1/(fp1+fp2)
    if (fp1 + fp2) > 0.01:
        ratio = fp1 / (fp1 + fp2)  # 0=full away, 1=full home
    else:
        return {"signal": 0.0, "mu_ou": mu_ou, "mu_1x2": None, "delta": None}

    # μ'yi tahmin et: P(draw) = fpx olacak şekilde
    mu_1x2 = None
    for mu_test in [v / 10 for v in range(8, 60)]:  # 0.8 to 6.0
        lh = mu_test * ratio
        la = mu_test * (1 - ratio)
        # P(draw) ≈ Σ_k e^-lh lh^k/k! × e^-la la^k/k!
        pd = sum(
            (math.exp(-lh) * lh**k / math.factorial(k)) *
            (math.exp(-la) * la**k / math.factorial(k))
            for k in range(0, 8)
        )
        if pd <= fpx + 0.001:
            mu_1x2 = mu_test
            break

    if mu_ou is None or mu_1x2 is None:
        return {"signal": 0.0, "mu_ou": mu_ou, "mu_1x2": mu_1x2, "delta": None}

    delta = abs(mu_ou - mu_1x2)
    # delta=0 → tutarlı. delta>0.6 → çok tutarsız (büyük sinyal)
    signal = min(1.0, delta / 0.6)
    return {
        "signal": signal,
        "mu_ou": mu_ou,
        "mu_1x2": mu_1x2,
        "delta": delta,
        # Yön: μ_OU > μ_1X2 → OU 2.5 "Üst" undervalued → OVER sinyali
        "direction": "OVER" if mu_ou > mu_1x2 else "UNDER",
    }


# ============================================================
# CHECK C — Combo arbitrage (1X2_OU vs 1X2 × OU)
# ============================================================

def check_c_combo_consistency(mkts: dict) -> dict:
    """
    1X2_OU market: 'no=1' "1 ve Alt", no=2 "0 ve Alt", no=3 "2 ve Alt",
                   no=4 "1 ve Üst", no=5 "0 ve Üst", no=6 "2 ve Üst"
    Selection strings depending on data: '1 ve Alt' etc.

    fp(1X2_OU "1 ve Üst") / (fp(1X2.1) × fp(OU.Üst)) = corr_factor.
    Negatif korelasyon var (ev favorisi → düşük skor) → factor < 1 normal.
    Eğer factor > 1.1 → over-priced combo (favori-DOMINANT pazar diyor) → MS-1 ve Üst alma!
    Eğer factor < 0.7 → under-priced combo → tersi.
    """
    one_x_two = _read_1x2(mkts)
    ou = _read_ou(mkts, "2.5")
    combo = mkts.get("1X2_OU", {})
    if not one_x_two or not ou or not combo:
        return {"signal": 0.0, "factors": {}}

    fp1, fpx, fp2 = one_x_two
    fp_under, fp_over = ou

    # All 6 outcomes
    outcomes = {
        "1 ve Üst": (fp1, fp_over),
        "0 ve Üst": (fpx, fp_over),
        "2 ve Üst": (fp2, fp_over),
        "1 ve Alt": (fp1, fp_under),
        "0 ve Alt": (fpx, fp_under),
        "2 ve Alt": (fp2, fp_under),
    }
    # iddaa combo overround
    combo_odds = list(combo.values())
    valid_combo = [o for o in combo_odds if _valid_odd(o)]
    if not valid_combo:
        return {"signal": 0.0, "factors": {}}
    combo_fps = fair_probs(valid_combo)
    selections_sorted = list(combo.keys())
    fp_combo_map = dict(zip(selections_sorted, combo_fps))

    # Her outcome için factor
    factors = {}
    deviations = []
    for sel_name, (px, po) in outcomes.items():
        fp_observed = fp_combo_map.get(sel_name)
        product = px * po
        if fp_observed and product > 0.005:
            factor = fp_observed / product
            factors[sel_name] = {
                "observed_fair": fp_observed,
                "product": product,
                "factor": factor,
                "log_deviation": math.log(factor),
            }
            deviations.append(abs(math.log(factor)))

    if not deviations:
        return {"signal": 0.0, "factors": factors}

    # Tipik corr factor ~0.85-0.95. |log| ~0.05-0.16
    # |log| > 0.3 → anomalous (factor 1.35 ya da 0.74)
    max_dev = max(deviations)
    signal = min(1.0, max_dev / 0.3)
    # En anomalous outcome
    worst = max(factors.items(), key=lambda kv: abs(kv[1]["log_deviation"]))
    return {
        "signal": signal,
        "factors": factors,
        "worst_outcome": worst[0],
        "worst_factor": worst[1]["factor"],
        # Direction: factor > 1 → iddaa combo too generous → outcome undervalued by combination
        "direction": worst[0] if worst[1]["factor"] > 1.05 else None,
    }


# ============================================================
# CHECK D — 1X2 vs HC consistency
# ============================================================

def check_d_handicap(mkts: dict) -> dict:
    """1X2 favori ile HC pazarı tutarlı mı?"""
    one_x_two = _read_1x2(mkts)
    if not one_x_two:
        return {"signal": 0.0}

    fp1, fpx, fp2 = one_x_two

    # HC odds — varsa
    hc_signals = []
    for hc_key in ("HC+1", "HC-1", "HC+1.5", "HC-1.5", "HC+2", "HC-2"):
        m = mkts.get(hc_key, {})
        if not m:
            continue
        # HC selections: '1', '0', '2'
        oh, od, oa = m.get("1"), m.get("0") or m.get("X"), m.get("2")
        if not (_valid_odd(oh) and _valid_odd(od) and _valid_odd(oa)):
            continue
        fph, fpd, fpa = fair_probs([oh, od, oa])
        # Beklenti: HC-1 ise ev galip prob HC.1 < 1X2.1 (çünkü ek koşul gerekli)
        # HC+1 ise dep galip prob HC.2 < 1X2.2
        # Heuristic: HC -1 implied home prob < 1X2 home prob ratio = expected_ratio
        if "+1" in hc_key:
            # Dep'e +1 → ev'in tek farkla galibiyeti gerekir
            # HC.2 should be much lower than 1X2.2 if 1X2 strong home favorite
            if fp2 > 0.05:
                ratio = fph / fp2  # Ev galip ratio
                # Tipik HC+1 ev prob ratio ~1.05-1.20 (ev iki gol fark)
                # Eğer ratio >> 1.5 → 1X2 ev favorisini abartıyor VEYA HC dep'e bonus veriyor
                deviation = abs(math.log(max(ratio, 0.01)) - math.log(1.15))
                hc_signals.append(deviation)
    if not hc_signals:
        return {"signal": 0.0}
    avg_dev = sum(hc_signals) / len(hc_signals)
    # |log| > 0.4 → anomalous
    signal = min(1.0, avg_dev / 0.4)
    return {"signal": signal, "hc_deviations": hc_signals}


# ============================================================
# CHECK E — Overround dispersion
# ============================================================

def check_e_overround_dispersion(mkts: dict) -> dict:
    """Pazarlar arası vig dispersion."""
    overrounds = {}
    # 1X2
    m = mkts.get("1X2", {})
    o1, ox, o2 = m.get("1"), m.get("0") or m.get("X"), m.get("2")
    if _valid_odd(o1) and _valid_odd(ox) and _valid_odd(o2):
        overrounds["1X2"] = overround([o1, ox, o2])
    # OU 2.5
    ou25 = mkts.get("OU2.5", {})
    alt = ou25.get("Alt"); ust = ou25.get("Üst") or ou25.get("Ust")
    if _valid_odd(alt) and _valid_odd(ust):
        overrounds["OU2.5"] = overround([alt, ust])
    # BTTS
    mb = mkts.get("BTTS", {})
    var = mb.get("Var"); yok = mb.get("Yok")
    if _valid_odd(var) and _valid_odd(yok):
        overrounds["BTTS"] = overround([var, yok])
    # DC
    dc_m = mkts.get("DC", {})
    if dc_m and all(_valid_odd(v) for v in dc_m.values()):
        overrounds["DC"] = overround(list(dc_m.values()))

    if len(overrounds) < 2:
        return {"signal": 0.0, "overrounds": overrounds}

    vals = list(overrounds.values())
    mean_or = sum(vals) / len(vals)
    std_or = math.sqrt(sum((v - mean_or) ** 2 for v in vals) / len(vals))
    # std>0.05 = 5pp arası dispersion büyük
    signal = min(1.0, std_or / 0.05)
    return {
        "signal": signal,
        "overrounds": overrounds,
        "mean_or": mean_or,
        "std_or": std_or,
    }


# ============================================================
# AGGREGATE
# ============================================================

CHECK_WEIGHTS = {
    "A_ou_mu_consistency": 0.20,    # μ_OU lines tutarlılığı
    "B_ou_vs_1x2": 0.30,             # En önemli: cross-market mu mismatch
    "C_combo_consistency": 0.25,     # Combo arbitrage
    "D_handicap": 0.15,              # HC consistency
    "E_overround_dispersion": 0.10,  # Vig dispersion
}


def signal_for_match(mkts: dict) -> dict:
    """5 check'i çalıştır, ağırlıklı agregat üret."""
    a = check_a_ou_mu_consistency(mkts)
    b = check_b_ou_vs_1x2(mkts)
    c = check_c_combo_consistency(mkts)
    d = check_d_handicap(mkts)
    e = check_e_overround_dispersion(mkts)

    sigs = {
        "A_ou_mu_consistency": a["signal"],
        "B_ou_vs_1x2": b["signal"],
        "C_combo_consistency": c["signal"],
        "D_handicap": d["signal"],
        "E_overround_dispersion": e["signal"],
    }
    # Ağırlıklı toplam
    total_w = sum(CHECK_WEIGHTS.values())
    anomaly_strength = sum(CHECK_WEIGHTS[k] * v for k, v in sigs.items()) / total_w

    # consistency = NOT anomaly + low overround → high consistency
    or_data = e.get("overrounds", {})
    mean_or = e.get("mean_or") or 0.10
    consistency_score = (1.0 - anomaly_strength) * max(0.0, 1.0 - mean_or / 0.20)

    # Aggregate direction — en güçlü sinyal yönünü öne çıkar
    direction = None
    if b["signal"] > 0.5 and b.get("direction"):
        direction = b["direction"]
    elif c["signal"] > 0.5 and c.get("direction"):
        direction = c["direction"]

    return {
        "anomaly_strength": anomaly_strength,
        "consistency_score": consistency_score,
        "structural_signal": direction,
        "checks": sigs,
        "details": {"A": a, "B": b, "C": c, "D": d, "E": e},
        # Compat alanları (selector.py için)
        "overround_1x2": or_data.get("1X2"),
        "overround_ou25": or_data.get("OU2.5"),
        "overround_btts": or_data.get("BTTS"),
        "mu_estimates": a.get("mu_estimates"),
        "mu_std": a.get("mu_std"),
    }


# ============================================================
# BATCH
# ============================================================

def compute_all(snapshot_id: str | None = None) -> list[dict]:
    from datetime import datetime
    conn = db.connect()
    try:
        if snapshot_id is None:
            row = conn.execute(
                "SELECT snapshot_id FROM iddaa_odds ORDER BY snapshot_id DESC LIMIT 1"
            ).fetchone()
            if not row:
                print("iddaa_odds bos")
                return []
            snapshot_id = row[0]

        match_ids = [r["iddaa_match_id"] for r in conn.execute(
            "SELECT DISTINCT iddaa_match_id FROM iddaa_odds WHERE snapshot_id=?",
            (snapshot_id,)
        ).fetchall()]

        meta = {r["iddaa_match_id"]: dict(r) for r in conn.execute(
            "SELECT iddaa_match_id, MAX(home_team) as home_team, MAX(away_team) as away_team, "
            "MAX(kickoff_iso) as kickoff_iso "
            "FROM iddaa_odds WHERE snapshot_id=? GROUP BY iddaa_match_id",
            (snapshot_id,)
        ).fetchall()}

        print(f"[anomaly v1.1] snapshot={snapshot_id} matches={len(match_ids)}")

        now = datetime.utcnow().isoformat()
        results = []
        for mid in match_ids:
            mkts = get_match_odds(conn, mid, snapshot_id)
            sig = signal_for_match(mkts)
            m = meta.get(mid, {})
            sig["iddaa_match_id"] = mid
            sig["home_team"] = m.get("home_team", "?")
            sig["away_team"] = m.get("away_team", "?")
            sig["kickoff_iso"] = m.get("kickoff_iso")
            results.append(sig)

            try:
                conn.execute("""
                    INSERT OR REPLACE INTO odds_anomaly_signals(
                        fixture_id, iddaa_match_id, snapshot_id,
                        overround_1x2, overround_ou, overround_btts,
                        consistency_score, structural_signal,
                        anomaly_direction, anomaly_strength, computed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    None, mid, snapshot_id,
                    sig["overround_1x2"], sig["overround_ou25"], sig["overround_btts"],
                    sig["consistency_score"], sig["structural_signal"],
                    sig["structural_signal"], sig["anomaly_strength"], now
                ))
            except Exception:
                pass
        conn.commit()
        return results
    finally:
        conn.close()


def report(top_n: int = 20):
    conn = db.connect()
    try:
        rows = conn.execute("""
            SELECT s.*,
                   COALESCE((SELECT MAX(home_team) FROM iddaa_odds o WHERE o.iddaa_match_id=s.iddaa_match_id),'?') as home,
                   COALESCE((SELECT MAX(away_team) FROM iddaa_odds o WHERE o.iddaa_match_id=s.iddaa_match_id),'?') as away
            FROM odds_anomaly_signals s
            WHERE s.anomaly_strength IS NOT NULL
            ORDER BY s.anomaly_strength DESC
            LIMIT ?
        """, (top_n,)).fetchall()

        print("=" * 110)
        print(f"TOP {top_n} GERCEK ANOMALI SINYALI (v1.1)")
        print("=" * 110)
        print(f"{'Match':45s} {'Anom':>5s} {'Cons':>5s} {'Sig.Yon':10s} {'OR_1X2':>7s} {'OR_OU':>7s}")
        print("-" * 110)
        for r in rows:
            label = f"{r['home']} vs {r['away']}"[:43]
            anom = f"{r['anomaly_strength']:.2f}"
            cons = f"{r['consistency_score']:.2f}" if r['consistency_score'] is not None else "-"
            sig = r["structural_signal"] or "-"
            or1 = f"{(r['overround_1x2'] or 0)*100:.1f}%"
            oro = f"{(r['overround_ou'] or 0)*100:.1f}%"
            print(f"{label:45s} {anom:>5s} {cons:>5s} {sig:10s} {or1:>7s} {oro:>7s}")
    finally:
        conn.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "compute"
    if cmd == "compute":
        compute_all()
        report(20)
    elif cmd == "report":
        report(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    elif cmd == "match":
        # debug tek mac
        conn = db.connect()
        try:
            mid = sys.argv[2]
            mkts = get_match_odds(conn, mid)
            sig = signal_for_match(mkts)
            import json
            print(json.dumps(sig, ensure_ascii=False, indent=2, default=str))
        finally:
            conn.close()
    else:
        print("Komutlar: compute | report [N] | match <iddaa_match_id>")
