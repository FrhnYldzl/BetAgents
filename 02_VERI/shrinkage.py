"""
📐 KÜÇÜLTME (SHRINKAGE) — "tercihin olasılığı"nın matematiği
==============================================================
SORUN (kullanıcı tespiti): ajanlar tahmin edilen edge'i NOKTA TAHMİNİ gibi
kullanıyor — sanki hatasızmış gibi. Oysa p̂'nin kendisi bir dağılım. Bu
ihmalin iki ölçülebilir bedeli var:

  1. ZAYIFLAMA (attenuation). ê = e + gürültü ise, ê'nin sıralaması gerçek
     e'nin sıralamasından daha kötüdür. Ne kadar kötü olduğu tek bir sayıyla
     ölçülür:  k = τ²/(τ²+σ²)  (güvenilirlik oranı).

  2. SEÇİCİNİN LANETİ (optimizer's curse). Ajan N aday arasından argmax
     alıyor. Model TARAFSIZ olsa bile, argmax gürültünün yukarı saptığı
     adayı tercih eder. Şişme:  E[max_{i≤N} ε_i] ≈ σ · Φ⁻¹((N-0.375)/(N+0.25))
     N=221 (KOMBO'nun aday sayısı) için bu ×1.25 demektir.

Bu modül SAF matematiktir — DB okumaz, ajan tanımaz. Üç yerde kullanılır:
    measure_k.py   → k'yı canlı bahislerden ÖLÇER
    backtest.py    → KÖLN konseptini geçmişte SINAR
    (ileride) canlı ajan → seçim kapısı

──────────────────────────────────────────────────────────────────────
MODEL
    gerçek edge     e   ~ N(μ₀, τ²)
    gözlenen edge   ê   = e + N(0, σ²)

Gerçekleşen getiriyi gözlenen edge'e regresyona sokarsak:
    r = α + k·ê        →  k = τ²/(τ²+σ²)   ve   α = μ₀(1-k)

Buradan her şey çıkar:
    Var(ê) = τ² + σ²           (doğrudan örneklemden)
    τ² = k·Var(ê)   ·   σ² = (1-k)·Var(ê)
    SONSAL ORTALAMA  E[e|ê] = μ₀ + k(ê - μ₀)
    SONSAL VARYANS   Var[e|ê] = k(1-k)·Var(ê)
    TERCİHİN OLASILIĞI  π* = P(e>0 | ê) = Φ( E[e|ê] / sd[e|ê] )

μ₀ NEGATİF olmak zorunda: bir bahsin ÖNSEL beklentisi marj kadar eksidir.
Bu bir tercih değil, projenin kendi ölçümü ("motorun TÜM dilimleri iddaa
fiyatıyla −%11.6/−%12.7"). μ₀ regresyonun kesme teriminden türetilir,
elle konmaz.

──────────────────────────────────────────────────────────────────────
BOZUK (DEJENERE) DURUMLAR — sessizce geçilmez, açıkça raporlanır:

    k ≤ 0  → ê hiçbir pozitif bilgi taşımıyor (hatta ters sıralıyor).
             τ² = k·Var(ê) ≤ 0 olurdu — model geçersiz. Doğru davranış:
             sonsal = μ₀ (koşulsuz ortalama) ve μ₀<0 olduğu için HİÇ BAHİS
             YOK. Bu bir arıza değil, bir HÜKÜM.
    k ≥ 1  → ölçüm hatası yok demek olurdu; örneklem gürültüsü. 1'e kırpılır.

──────────────────────────────────────────────────────────────────────
TAHMİNCİ DOĞRULAMASI (bilinen k ile sentetik evren, 30 tekrar × n=3.000):
    gerçek k   ölçülen ort.   std     yanlılık
      0.10        0.116      0.069     +0.016
      0.30        0.330      0.129     +0.030
      0.50        0.539      0.175     +0.039
      0.80        0.842      0.231     +0.042
Yanlılık her seviyede ortalamanın standart hatasının 1.3 katının altında —
yani sıfırdan ayırt edilemiyor; tahminci YANSIZ kabul edilebilir. Ama
dikkat: std büyük (0.07-0.23). n=3.000'de bile k ancak ±0.15 hassasiyetle
bilinir. Birkaç yüz bahisle ölçülen bir k'ya kesinlik atfedilmemelidir.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ══════════════════════════════════════════════════════════════
# Normal dağılım yardımcıları (scipy'siz — scipy çöküşü 9 ajanı
# susturmuştu; bu modül ona bağımlı olmamalı)
# ══════════════════════════════════════════════════════════════

def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Ters normal (Acklam yaklaşımı, |hata| < 1.15e-9)."""
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    lo = 0.02425
    if p < lo:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p <= 1 - lo:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
            ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


# ══════════════════════════════════════════════════════════════
# 1) SEÇİCİNİN LANETİ
# ══════════════════════════════════════════════════════════════

def expected_max_z(n_candidates: int) -> float:
    """N bağımsız standart normalin beklenen maksimumu (Blom yaklaşımı).
    N=1→0.00 · 6→1.28 · 50→2.24 · 221→2.77 · 299→2.86"""
    n = max(1, int(n_candidates))
    if n == 1:
        return 0.0
    return norm_ppf((n - 0.375) / (n + 0.25))


def selection_inflation(n_candidates: int, sigma: float) -> float:
    """argmax N aday üzerinden alındığında p̂'nin beklenen ŞİŞME ÇARPANI.
    Raporlanan edge bu çarpana BÖLÜNMELİDİR."""
    if sigma <= 0:
        return 1.0
    return math.exp(expected_max_z(n_candidates) * sigma)


# ══════════════════════════════════════════════════════════════
# 2) k TAHMİNİ — en küçük kareler (isteğe bağlı oran kontrolü)
# ══════════════════════════════════════════════════════════════

def _solve(a: list[list[float]], y: list[float]) -> tuple[list[float], list[list[float]]] | None:
    """Gauss-Jordan: katsayılar + (AᵀA)⁻¹ (standart hata için)."""
    p = len(a)
    aug = [row[:] + [y[i]] + [1.0 if j == i else 0.0 for j in range(p)]
           for i, row in enumerate(a)]
    for col in range(p):
        piv = max(range(col, p), key=lambda r: abs(aug[r][col]))
        if abs(aug[piv][col]) < 1e-14:
            return None
        aug[col], aug[piv] = aug[piv], aug[col]
        d = aug[col][col]
        aug[col] = [v / d for v in aug[col]]
        for r in range(p):
            if r != col:
                f = aug[r][col]
                aug[r] = [aug[r][j] - f * aug[col][j] for j in range(len(aug[r]))]
    beta = [aug[i][p] for i in range(p)]
    inv = [[aug[i][p + 1 + j] for j in range(p)] for i in range(p)]
    return beta, inv


def estimate_k(rows: list[dict], control_odds: bool = True) -> dict | None:
    """GÜVENİLİRLİK ORANI k'yı ölç.

    rows: [{'e': tahmin edilen edge, 'r': gerçekleşen getiri, 'o': oran}]
        e = oran × p̂ − 1          (birim bahis başına beklenen getiri)
        r = (oran − 1) kazandıysa, aksi halde −1

    control_odds=True ise oran da modele girer — böylece ölçülen k,
    favori-uzunoran sapmasından ARINDIRILMIŞ olur. (Bu kontrol önemli:
    kontrolsüz bir negatif k, yalnızca "uzun oranlar kaybettirir"in yeniden
    keşfi olabilir.)

    Döner: k, se_k, t, alpha, mu0, var_e, n, tau2, sigma2, degenerate
    """
    data = [r for r in rows
            if r.get("e") is not None and r.get("r") is not None]
    n = len(data)
    if n < 30:
        return None

    mo = sum(float(r.get("o") or 0) for r in data) / n
    cols = [lambda r: 1.0, lambda r: float(r["e"])]
    if control_odds:
        cols.append(lambda r: float(r.get("o") or mo) - mo)
    p = len(cols)

    X = [[f(r) for f in cols] for r in data]
    y = [float(r["r"]) for r in data]
    xtx = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(p)]
           for a in range(p)]
    xty = [sum(X[i][a] * y[i] for i in range(n)) for a in range(p)]
    sol = _solve(xtx, xty)
    if sol is None:
        return None
    beta, inv = sol

    resid = [y[i] - sum(beta[a] * X[i][a] for a in range(p)) for i in range(n)]
    s2 = sum(v * v for v in resid) / (n - p)
    se_k = math.sqrt(max(s2 * inv[1][1], 0.0))

    k_raw = beta[1]
    alpha = beta[0]
    me = sum(r["e"] for r in data) / n
    var_e = sum((r["e"] - me) ** 2 for r in data) / max(n - 1, 1)

    k = min(max(k_raw, 0.0), 1.0)        # modelde kullanılacak kırpılmış hâli
    mean_r = sum(y) / n

    # μ₀, KIRPILMIŞ k ile tutarlı türetilir (α = μ₀(1-k)).
    # ⚠️ k_raw < 0 iken α/(1-k_raw) POZİTİF çıkabilir ve "ortalama bahis
    # kârlı" gibi okunur — oysa gerçekleşen ortalama eksidir. k≤0 demek
    # "ê hiçbir bilgi taşımıyor" demek; o hâlde herhangi bir bahis için en
    # iyi tahmin KOŞULSUZ ORTALAMADIR. k≥1'de de formül patlar, aynı yere düşer.
    if 0.0 < k < 0.999:
        mu0 = alpha / (1.0 - k)
    else:
        mu0 = mean_r
    return {
        "n": n,
        "k": k, "k_raw": k_raw, "se_k": se_k,
        "t": (k_raw / se_k) if se_k > 0 else 0.0,
        "ci_lo": k_raw - 1.96 * se_k, "ci_hi": k_raw + 1.96 * se_k,
        "alpha": alpha, "mu0": mu0, "var_e": var_e,
        "tau2": k * var_e, "sigma2": (1 - k) * var_e,
        "odds_beta": (beta[2] if control_odds else None),
        "mean_e": me, "mean_r": mean_r,
        "degenerate": k_raw <= 0.0,
        "control_odds": control_odds,
    }


# ══════════════════════════════════════════════════════════════
# 3) SONSAL EDGE + TERCİHİN OLASILIĞI
# ══════════════════════════════════════════════════════════════

class Shrinker:
    """Ölçülmüş bir k ile tek bir adayı değerlendirir.

    Kullanım:
        sh = Shrinker.from_fit(fit)                 # measure_k / backtest çıktısı
        v = sh.judge(edge_hat=0.302, n_candidates=221)
        v["posterior"]  → küçültülmüş edge
        v["pi_star"]    → tercihin doğru olma olasılığı
        v["bet"]        → oynanmalı mı
    """

    def __init__(self, k: float, mu0: float, var_e: float,
                 degenerate: bool = False, min_pi: float = 0.55):
        self.k = min(max(k, 0.0), 1.0)
        self.mu0 = mu0
        self.var_e = max(var_e, 1e-9)
        self.degenerate = degenerate
        self.min_pi = min_pi

    @classmethod
    def from_fit(cls, fit: dict, min_pi: float = 0.55) -> "Shrinker":
        return cls(fit["k"], fit["mu0"], fit["var_e"],
                   degenerate=fit.get("degenerate", False), min_pi=min_pi)

    @property
    def sigma(self) -> float:
        """Tahmin hatasının standart sapması — seçicinin laneti için gerekli."""
        return math.sqrt(max((1 - self.k) * self.var_e, 0.0))

    def judge(self, edge_hat: float, n_candidates: int = 1) -> dict:
        """Bir adayı değerlendir. Üç katman sırayla uygulanır:
             1. seçicinin laneti düzeltmesi (N adaydan argmax alındıysa)
             2. küçültme (k)
             3. tercihin olasılığı π*
        """
        # ── 1) seçicinin laneti: argmax'ın beklenen şişmesini geri al
        infl = expected_max_z(n_candidates) * self.sigma
        e_adj = edge_hat - infl

        # ── 2) küçültme
        if self.degenerate or self.k <= 0.0:
            # ê hiçbir bilgi taşımıyor → koşulsuz ortalamaya düş
            post = self.mu0
            sd = math.sqrt(self.var_e)
            pi = norm_cdf(post / sd) if sd > 0 else 0.0
            return {"edge_hat": edge_hat, "selection_penalty": infl,
                    "edge_adj": e_adj, "posterior": post, "sd": sd,
                    "pi_star": pi, "bet": False,
                    "note": "k<=0 — edge sıralaması bilgi taşımıyor, PAS"}

        post = self.mu0 + self.k * (e_adj - self.mu0)
        sd = math.sqrt(max(self.k * (1 - self.k) * self.var_e, 1e-12))
        pi = norm_cdf(post / sd)
        return {"edge_hat": edge_hat, "selection_penalty": infl,
                "edge_adj": e_adj, "posterior": post, "sd": sd,
                "pi_star": pi, "bet": (post > 0 and pi >= self.min_pi),
                "note": ""}

    def required_edge(self, n_candidates: int = 1) -> float | None:
        """π* eşiğini geçmek için gereken HAM edge — "eşiğim ne olmalı"nın
        cevabı. Sabit %8 yerine ölçülmüş k'dan türetilir."""
        if self.degenerate or self.k <= 0.0:
            return None
        sd = math.sqrt(max(self.k * (1 - self.k) * self.var_e, 1e-12))
        need_post = norm_ppf(self.min_pi) * sd
        e_adj = (need_post - self.mu0) / self.k + self.mu0
        return e_adj + expected_max_z(n_candidates) * self.sigma


# ══════════════════════════════════════════════════════════════
# Rapor yardımcısı
# ══════════════════════════════════════════════════════════════

def fmt_fit(fit: dict | None, label: str = "") -> str:
    if not fit:
        return f"{label:22s}  (yetersiz örneklem — en az 30 kapanmış bahis gerek)"
    star = "***" if abs(fit["t"]) > 2.58 else ("**" if abs(fit["t"]) > 1.96 else "")
    flag = "  ⛔ DEJENERE (k<=0)" if fit["degenerate"] else ""
    return (f"{label:22s} n={fit['n']:5d}  k={fit['k_raw']:+.3f} ±{fit['se_k']:.3f} "
            f"t={fit['t']:+5.2f}{star:3s} "
            f"[{fit['ci_lo']:+.2f},{fit['ci_hi']:+.2f}]  "
            f"μ₀={fit['mu0']*100:+.1f}%  "
            f"ort.tahmin {fit['mean_e']*100:+.1f}% → gerçek {fit['mean_r']*100:+.1f}%"
            f"{flag}")


if __name__ == "__main__":
    print("SEÇİCİNİN LANETİ — argmax N aday üzerinden alındığında şişme")
    print(f"{'N':>6s} {'E[max]/σ':>10s}   σ=0.08 ise çarpan")
    for n in (1, 6, 20, 50, 100, 221, 299, 500):
        print(f"{n:>6d} {expected_max_z(n):>10.3f}   ×{selection_inflation(n, 0.08):.3f}")
    print("\nSONSAL EDGE — μ₀=-0.12, Var(ê)=0.01")
    print(f"{'k':>6s}  " + "  ".join(f"{'ham '+f'{e:+.0%}':>16s}" for e in (0.08, 0.15, 0.30)))
    for k in (0.15, 0.25, 0.35, 0.50, 0.70):
        sh = Shrinker(k, -0.12, 0.01)
        cells = []
        for e in (0.08, 0.15, 0.30):
            v = sh.judge(e)
            cells.append(f"{v['posterior']*100:+7.1f}% π*{v['pi_star']*100:3.0f}%")
        print(f"{k:>6.2f}  " + "  ".join(cells))
