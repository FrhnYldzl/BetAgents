"""
MERKEZÎ VERİTABANI KATMANI — SQLite (yerel) ↔ PostgreSQL (Railway)
==================================================================
Tek giriş noktası. `DATABASE_URL` ortam değişkenine göre otomatik seçer:

    DATABASE_URL boş/yok   → bireysel PG* değişkenlerine bak, yoksa SQLite
    DATABASE_URL=postgres… → PostgreSQL (psycopg2)

Öncelik sırası:
  1. DATABASE_URL ortam değişkeni (Railway tarafından otomatik set edilir)
  2. PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE bireysel değişkenleri
  3. Yerel SQLite (02_VERI/bahis_agent.db) — geliştirme ortamı

Amaç: canlı-yol kodu (paper_engine, auto_play/settle, app_*) HİÇ değişmeden
çalışsın. Wrapper, sqlite3.Connection davranışını taklit eder:

    conn = db.connect()
    conn.execute("SELECT * FROM matches_v2 WHERE id=?", (mid,)).fetchall()
    df = conn.read_df("SELECT * FROM signal_snapshots")
    conn.commit(); conn.close()

Dialect farkları wrapper içinde otomatik çevrilir:
    ?  → %s                                  (placeholder)
    INSERT OR IGNORE → … ON CONFLICT DO NOTHING
    satırlar hem row[0] hem row['col'] destekler (DictCursor / sqlite3.Row)

Tarih/saat kolonları HER İKİ tarafta da TEXT'tir (ISO string) — kod
string karşılaştırması yaptığı için davranış birebir korunur.
"""
from __future__ import annotations

import os
import re
import warnings
from pathlib import Path

# pandas, raw psycopg2 bağlantısında "SQLAlchemy önerilir" uyarısı verir — zararsız.
warnings.filterwarnings("ignore", message=r".*pandas only supports SQLAlchemy.*")

THIS_DIR = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = THIS_DIR / "bahis_agent.db"


# ============================================================
# MOD TESPİTİ
# ============================================================

def database_url() -> str:
    """
    PostgreSQL bağlantı URL'sini döndür.

    Öncelik:
      1. DATABASE_URL ortam değişkeni (Railway tarafından otomatik set edilir)
      2. PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE bireysel değişkenleri
      3. Boş string → SQLite moduna düşer

    Railway'in postgres:// şeması psycopg2 için postgresql:// olarak düzeltilir.
    """
    url = (os.environ.get("DATABASE_URL") or "").strip()

    # Railway bazen postgres:// prefix'i kullanır; psycopg2 postgresql:// ister.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    if url:
        return url

    # DATABASE_URL yoksa bireysel PG* değişkenlerinden URL oluştur
    host = os.environ.get("PGHOST", "").strip()
    if host:
        port     = os.environ.get("PGPORT",     "5432").strip()
        user     = os.environ.get("PGUSER",     "postgres").strip()
        password = os.environ.get("PGPASSWORD", "").strip()
        database = os.environ.get("PGDATABASE", "railway").strip()
        # Şifredeki özel karakterleri URL-encode et
        import urllib.parse
        encoded_password = urllib.parse.quote(password, safe="")
        return f"postgresql://{user}:{encoded_password}@{host}:{port}/{database}"

    return ""


def is_postgres() -> bool:
    u = database_url()
    return u.startswith("postgresql://")


def backend() -> str:
    return "postgres" if is_postgres() else "sqlite"


# ============================================================
# DIALECT ÇEVİRİSİ (yalnız PostgreSQL modunda)
# ============================================================

_RE_INSERT_OR_IGNORE = re.compile(r"INSERT\s+OR\s+IGNORE\s+INTO", re.IGNORECASE)
_RE_INSERT_OR_REPLACE = re.compile(r"INSERT\s+OR\s+REPLACE\s+INTO", re.IGNORECASE)

# Büyük harf içeren kolon adları: PostgreSQL tırnaksız identifier'ı küçük harfe
# çevirir → "closing_X" kolonu `closing_x` aranınca bulunamaz. SQLite harf-duyarsız
# olduğu için kod bu kolonları tırnaksız yazıyor. PG modunda otomatik tırnaklarız.
# (uzun adlar önce → alternation'da doğru eşleşme)
_MIXED_CASE_COLS = ["odd_open_X", "closing_X", "opening_X", "odd_X", "fp_X"]
_RE_MIXED_CASE = re.compile(
    r'(?<![\w"])(' + "|".join(_MIXED_CASE_COLS) + r')(?![\w"])'
)

# SQLite'ta MAX(a,b)/MIN(a,b) skaler (2-arg) fonksiyondur; PostgreSQL'de YOK
# (MAX/MIN sadece aggregate). 2-arg form → GREATEST/LEAST. Tek-arg aggregate'e
# dokunma. (İç içe parantez içermeyen argümanlar için güvenli.)
_RE_SCALAR_MAXMIN = re.compile(r"\b(MAX|MIN)\(([^()]+)\)", re.IGNORECASE)


def _scalar_maxmin(sql: str) -> str:
    def _repl(m):
        fn, args = m.group(1), m.group(2)
        if "," in args:  # 2 argüman → skaler
            return ("GREATEST" if fn.upper() == "MAX" else "LEAST") + "(" + args + ")"
        return m.group(0)  # tek argüman → aggregate, olduğu gibi bırak
    return _RE_SCALAR_MAXMIN.sub(_repl, sql)


def _xlate_dialect(sql: str) -> str:
    """SQLite-özel SQL yapılarını PostgreSQL'e çevir (placeholder hariç)."""
    s = sql
    if _RE_INSERT_OR_IGNORE.search(s):
        s = _RE_INSERT_OR_IGNORE.sub("INSERT INTO", s)
        s = s.rstrip().rstrip(";") + "\nON CONFLICT DO NOTHING"
    if _RE_INSERT_OR_REPLACE.search(s):
        # Canlı yolda kullanılmıyor; güvenli tarafta hata ver.
        raise NotImplementedError(
            "INSERT OR REPLACE PostgreSQL'e otomatik çevrilemiyor "
            "(ON CONFLICT ... DO UPDATE hedef sütun gerekir)."
        )
    # Büyük harfli kolonları tırnakla (zaten tırnaklı/word-içi olanlara dokunma)
    s = _RE_MIXED_CASE.sub(r'"\1"', s)
    # 2-arg MAX/MIN → GREATEST/LEAST
    s = _scalar_maxmin(s)
    return s


def _xlate_params(sql: str) -> str:
    """Param VARSA: literal % kaç, sonra ? → %s."""
    return sql.replace("%", "%%").replace("?", "%s")


# ============================================================
# CURSOR / CONNECTION WRAPPER
# ============================================================

class _Cur:
    """sqlite3.Cursor benzeri ince sarmalayıcı (hem SQLite hem PG için)."""

    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def fetchmany(self, size=None):
        return self._cur.fetchmany(size) if size is not None else self._cur.fetchmany()

    def __iter__(self):
        return iter(self._cur)

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        return getattr(self._cur, "lastrowid", None)

    @property
    def description(self):
        return self._cur.description

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass


class Conn:
    """
    sqlite3.Connection davranışını taklit eden taşınabilir bağlantı.
    Mevcut kod `conn.execute(...).fetchall()`, `conn.commit()`, `dict(row)`,
    `conn.close()`, `with conn:` kalıplarını değişmeden kullanabilir.
    """

    def __init__(self, raw, is_pg: bool):
        self._raw = raw
        self._pg = is_pg
        # Bazı kodlar `conn.row_factory = sqlite3.Row` atar; PG'de no-op.
        self.row_factory = None

    # ---- temel ----
    @property
    def raw(self):
        return self._raw

    @property
    def is_postgres(self) -> bool:
        return self._pg

    def cursor(self):
        return _Cur(self._raw.cursor())

    def execute(self, sql: str, params=None) -> _Cur:
        cur = self._raw.cursor()
        if self._pg:
            s = _xlate_dialect(sql)
            if params:
                cur.execute(_xlate_params(s), params)
            else:
                cur.execute(s)
        else:
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
        return _Cur(cur)

    def executemany(self, sql: str, seq_of_params) -> _Cur:
        cur = self._raw.cursor()
        if self._pg:
            s = _xlate_dialect(sql)
            cur.executemany(_xlate_params(s), seq_of_params)
        else:
            cur.executemany(sql, seq_of_params)
        return _Cur(cur)

    def executescript(self, sql_script: str):
        """Çoklu-statement betik. SQLite: executescript; PG: tek execute."""
        if self._pg:
            cur = self._raw.cursor()
            cur.execute(sql_script)
        else:
            self._raw.executescript(sql_script)
        return self

    def read_df(self, sql: str, params=None):
        """pandas DataFrame döndür (placeholder/dialect otomatik çevrilir)."""
        import pandas as pd
        if self._pg:
            s = _xlate_dialect(sql)
            if params:
                s = _xlate_params(s)
            return pd.read_sql_query(s, self._raw, params=params)
        return pd.read_sql_query(sql, self._raw, params=params)

    # ---- transaction / lifecycle ----
    def commit(self):
        self._raw.commit()

    def rollback(self):
        try:
            self._raw.rollback()
        except Exception:
            pass

    def close(self):
        try:
            self._raw.close()
        except Exception:
            pass

    # ---- context manager (sqlite3 ile aynı: çıkışta commit/rollback) ----
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            try:
                self._raw.commit()
            except Exception:
                pass
        else:
            self.rollback()
        return False


# ============================================================
# BAĞLANTI AÇ
# ============================================================

def connect(sqlite_path: str | os.PathLike | None = None) -> Conn:
    """
    Ortama göre bağlantı döndür.
      - PostgreSQL: DATABASE_URL (veya PG* değişkenleri) kullanılır (psycopg2 + DictCursor).
      - SQLite:    sqlite_path (vars. 02_VERI/bahis_agent.db), Row factory.

    Bağlantı hatası durumunda açıklayıcı bir RuntimeError fırlatır.
    """
    if is_postgres():
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError as exc:
            raise RuntimeError(
                "psycopg2 kurulu değil. 'pip install psycopg2-binary' komutunu çalıştırın."
            ) from exc
        url = database_url()
        try:
            raw = psycopg2.connect(
                url,
                cursor_factory=psycopg2.extras.DictCursor,
            )
        except psycopg2.OperationalError as exc:
            # Bağlantı bilgilerini logla (şifreyi gizle)
            import re as _re
            safe_url = _re.sub(r":[^:@]+@", ":***@", url)
            raise RuntimeError(
                f"PostgreSQL bağlantısı kurulamadı: {exc}\n"
                f"Bağlantı URL'si (şifre gizli): {safe_url}\n"
                "DATABASE_URL, PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE "
                "ortam değişkenlerini kontrol edin."
            ) from exc
        return Conn(raw, is_pg=True)

    import sqlite3
    path = str(sqlite_path) if sqlite_path else str(DEFAULT_SQLITE_PATH)
    raw = sqlite3.connect(path)
    raw.row_factory = sqlite3.Row
    return Conn(raw, is_pg=False)


# ============================================================
# KISA YOL: tek seferlik okuma
# ============================================================

def read_df(sql: str, params=None):
    """Bağlantıyı aç-oku-kapat (tek seferlik sorgular için kısa yol)."""
    c = connect()
    try:
        return c.read_df(sql, params)
    finally:
        c.close()


if __name__ == "__main__":
    c = connect()
    print(f"Backend: {backend()}")
    n = c.execute("SELECT COUNT(*) FROM matches_v2").fetchone()[0]
    print(f"matches_v2: {n}")
    c.close()
