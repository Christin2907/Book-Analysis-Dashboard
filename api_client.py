import re
import time
import requests


class OpenLibraryClient:
    def __init__(self, sleep_sec: float = 0.3, debug: bool = False):
        self.base = "https://openlibrary.org"
        self.sleep_sec = sleep_sec
        self.debug = debug

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "BookScout/1.0 (Educational Project)"})

    # -----------------------------
    # Helpers
    # -----------------------------
    def _sleep(self):
        # Kleine Drosselung (OpenLibrary empfiehlt 1-3 req/sec)
        if self.sleep_sec and self.sleep_sec > 0:
            time.sleep(self.sleep_sec)

    def _get_json(self, url: str, *, params: dict, err_ctx: str) -> dict:
        try:
            r = self.session.get(url, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if self.debug:
                print(f"[OpenLibrary] {err_ctx} | {e}")
            return {}
        finally:
            self._sleep()

    def _normalize_title(self, title: str) -> str:
        """Titel vereinfachen, um die Trefferquote zu erhöhen."""
        t = (title or "").strip()
        if not t:
            return ""

        # Klammern-Inhalte entfernen
        t = re.sub(r"\([^)]*\)", "", t)

        # Untertitel nach ':' entfernen
        if ":" in t:
            t = t.split(":", 1)[0]

        # Whitespace normalisieren
        return re.sub(r"\s+", " ", t).strip()

    def _safe_int_year(self, s) -> int | None:
        # Jahr robust extrahieren
        if s is None:
            return None
        try:
            return int(s)
        except Exception:
            return None

    # -----------------------------
    # Methode 1: ISBN/ID (api/books)
    # -----------------------------
    def enrich_by_isbn(self, isbn: str) -> dict:
        """Sucht Buchdaten über ISBN via /api/books (zuverlässiger als Titel-Suche).

        Hinweis: Auf books.toscrape ist 'upc' nicht immer echte ISBN -> deshalb fallback nötig.
        """
        isbn = (isbn or "").strip()
        if not isbn:
            return {}

        data = self._get_json(
            f"{self.base}/api/books",
            params={"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
            err_ctx=f"ISBN request error | isbn={isbn}",
        )

        key = f"ISBN:{isbn}"
        if key not in data:
            if self.debug:
                print(f"[OpenLibrary] ISBN not found | isbn={isbn}")
            return {}

        book = data[key]

        # Autor
        author = None
        authors = book.get("authors") or []
        if authors:
            author = authors[0].get("name")

        # Jahr (aus publish_date)
        publish_year = None
        publish_date = book.get("publish_date")
        if publish_date:
            m = re.search(r"(\d{4})", str(publish_date))
            if m:
                publish_year = self._safe_int_year(m.group(1))

        # Cover
        cover = book.get("cover") or {}
        cover_url = cover.get("medium") or cover.get("large") or cover.get("small")

        return {"author": author, "publish_year": publish_year, "cover_url": cover_url}

    # -----------------------------
    # Methode 2: Titel-Suche (search.json)
    # -----------------------------
    def enrich_by_title(self, title: str, limit: int = 5) -> dict:
        """Sucht nach Titel. Nimmt bevorzugt ein Ergebnis mit Cover (cover_i)."""
        q_raw = (title or "").strip()
        q = self._normalize_title(q_raw)
        if not q:
            return {}

        data = self._get_json(
            f"{self.base}/search.json",
            params={"title": q, "limit": limit},
            err_ctx=f"Title request error | title={q_raw!r} | q={q!r}",
        )

        docs = data.get("docs", [])
        if not docs:
            if self.debug:
                print(f"[OpenLibrary] No docs | title={q_raw!r} | q={q!r}")
            return {}

        # Bestes Dokument wählen: bevorzugt mit cover_i
        best = next((d for d in docs if d.get("cover_i")), None)
        if best is None:
            best = docs[0]
            if self.debug:
                print(f"[OpenLibrary] Docs but no cover_i | title={q_raw!r} | q={q!r}")

        author = None
        if best.get("author_name"):
            author = best["author_name"][0]

        publish_year = None
        if best.get("first_publish_year"):
            publish_year = self._safe_int_year(best.get("first_publish_year"))

        cover_url = None
        cover_i = best.get("cover_i")
        if cover_i:
            cover_url = f"https://covers.openlibrary.org/b/id/{cover_i}-M.jpg"

        return {"author": author, "publish_year": publish_year, "cover_url": cover_url}

    # -----------------------------
    # Final: Kombiniert (ISBN -> Titel)
    # -----------------------------
    def enrich(self, title: str, isbn_or_upc: str | None = None) -> dict:
        """Kombinierte Strategie:

        1) Erst ISBN/UPC über /api/books probieren
        2) Wenn nichts gefunden -> Titel-Suche als Fallback
        """
        if isbn_or_upc:
            extra = self.enrich_by_isbn(isbn_or_upc)
            # Wenn wir schon ein Cover haben, reicht es meistens
            if extra.get("cover_url") or extra.get("author") or extra.get("publish_year"):
                return extra

        return self.enrich_by_title(title)