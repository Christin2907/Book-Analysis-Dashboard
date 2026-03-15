from database import Base, SessionLocal, engine
from models import Book, PriceHistory
from scraper import BookScraper
from api_client import OpenLibraryClient


_BOOK_FIELDS = (
    "title",
    "category",
    "price",
    "rating",
    "availability",
    "description",
    "author",
    "publish_year",
    "cover_url",
)


def upsert_books(db, book_dicts: list):
    """Upsert-Logik über UPC:

    - Wenn UPC existiert -> Update
    - Sonst -> Insert
    """
    for b in book_dicts:
        upc = b.get("upc")
        if not upc:
            continue

        existing = db.query(Book).filter(Book.upc == upc).first()

        if existing:
            for f in _BOOK_FIELDS:
                setattr(existing, f, b.get(f))
        else:
            db.add(Book(**b))

    db.commit()


def run_scrape():
    """Hauptpipeline:

    1) Scraping
    2) API-Anreicherung
    3) DB Upsert
    4) PriceHistory schreiben
    """
    Base.metadata.create_all(bind=engine)

    scraper = BookScraper()
    api = OpenLibraryClient(sleep_sec=0.3, debug=False)

    print("Starte Scraping...")
    books = scraper.scrape_all_books(sleep_sec=0.0)
    print(f"{len(books)} Bücher gescraped.")

    enriched = []
    for i, b in enumerate(books, start=1):
        title = b.get("title", "")
        upc = b.get("upc", "")

        try:
            extra = api.enrich(title=title, isbn_or_upc=upc)
            # Cover nicht überschreiben (kommt aus Scraping)
            extra.pop("cover_url", None)
            b.update(extra)
        except Exception as e:
            print(f"[API Fehler] Titel={title!r} | {e}")

        enriched.append(b)
        if i % 50 == 0:
            print(f"API-Anreicherung Fortschritt: {i}/{len(books)}")

    db = SessionLocal()
    try:
        upsert_books(db, enriched)

        for b in enriched:
            if b.get("upc") and b.get("price") is not None:
                db.add(PriceHistory(upc=b["upc"], price=b["price"]))
        db.commit()
    finally:
        db.close()

    print(f"Saved/updated {len(enriched)} books.")
    print("Scraping + Anreicherung abgeschlossen.")
