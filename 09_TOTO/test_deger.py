"""Değer motoru birim testleri: önem örneklemesi ↔ tam hesap (analiz dönemindeki 4.091 desenli referans)."""
import importlib.util
import sys
import time
from itertools import product

import numpy as np

from deger import Degerlendirici, boyut, gerceklesen, kur, v15
from kalabalik import q_uret

sys.stdout.reconfigure(encoding="utf-8")
REF = "C:/Users/FERHAN YILDIZLI/OneDrive/Desktop/toto-panel-analiz/kod"
sys.path.insert(0, REF)
spec = importlib.util.spec_from_file_location("ref", REF + "/deger.py")
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)

rng = np.random.default_rng(3)
P = rng.dirichlet([4, 2.5, 2.5], 15)
th = {"beta": {"BIG": 1.5}, "a0": 0, "a2": 0, "gTR": 0, "gEU": 0}
Q = q_uret(P, np.zeros((15, 2)), np.zeros((15, 2)), th, ["EU-BIG"] * 15)
N = 3e6
havuz = {15: 2.5e7, 14: 1.4e7, 13: 1.4e7, 12: 1.75e7}
kol = P.argmax(1)
D = Degerlendirici(P, Q, N, havuz, M=200000)

tam = ref.V(kol, P, Q, N, havuz)
mc = D.degerle([(int(c),) for c in kol])
print(f"tek kolon  tam V = {tam:.4f} TL · örnekleme = {mc['ev']:.4f} TL (fark %{100 * (mc['ev'] / tam - 1):+.1f})")
e15, p15, od = v15([(int(c),) for c in kol], P, Q, N, havuz[15])
print(f"15. derece tam {e15:.5f} · örnekleme {mc['ev_k'][15]:.5f} · P(15) {p15:.2e} ≈ {mc['p15']:.2e}")

kol2 = kol.copy()
kol2[[1, 4, 7, 10]] = (kol2[[1, 4, 7, 10]] + 1) % 3
tam2 = ref.V(kol2, P, Q, N, havuz)
mc2 = D.degerle([(int(c),) for c in kol2])
print(f"kontrarian tam V = {tam2:.4f} · örnekleme = {mc2['ev']:.4f} (fark %{100 * (mc2['ev'] / tam2 - 1):+.1f})")

S3 = [(int(c),) for c in kol2]
S3[2] = (0, 1); S3[5] = (0, 1, 2); S3[9] = (0, 2)
top = sum(ref.V(np.array(c), P, Q, N, havuz) for c in product(*S3))
mc3 = D.degerle(S3)
print(f"12 kolonluk sistem Σ V(kolon) = {top:.3f} · örnekleme (öz-seyreltmeli) = {mc3['ev']:.3f} "
      f"(fark %{100 * (mc3['ev'] / top - 1):+.1f})")

for prof in ("FAVORİ", "15_AVCISI", "DENGELİ"):
    t = time.time()
    Sx, _ = kur(P, Q, N, havuz, 96, prof, Degerlendirici(P, Q, N, havuz, M=20000))
    r = Degerlendirici(P, Q, N, havuz, M=100000, tohum=11).degerle(Sx)
    print(f"{prof:10s} {boyut(Sx):3d} kolon · EV/kolon {r['ev'] / boyut(Sx):.3f} TL · P15 {r['p15']:.2e} · "
          f"P12+ {r['p12p']:.3f} · {time.time() - t:.1f} sn")

g = gerceklesen(S3, kol2, {15: 3, 14: 50, 13: 900, 12: 8000}, havuz)
print("gerçekleşen (sonuç = kolon2):", g["dogru_en_cok"], g["n"], round(g["odeme"]))
