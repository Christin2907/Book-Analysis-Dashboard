import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class BookScraper:
    def __init__(self, base_url="https://books.toscrape.com/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "BookScout/1.0 (Educational Project)"})

    def _get_soup(self, url: str) -> BeautifulSoup:
        # Timeout verhindert "hängt endlos"
        r = self.session.get(url, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")

    def _rating_to_int(self, rating_class: str) -> int:
        return {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}.get(rating_class, 0)

    @staticmethod
    def _parse_price(text: str) -> float | None:
        cleaned = "".join(ch for ch in (text or "") if (ch.isdigit() or ch == "."))
        return float(cleaned) if cleaned else None

    def scrape_all_books(self, sleep_sec=0.0) -> list:
        books = []
        next_url = self.base_url + "catalogue/page-1.html"
        page_count = 0

        while True:
            page_count += 1
            print(f"[Scraper] Seite {page_count}: {next_url}")

            soup = self._get_soup(next_url)

            items = soup.select("article.product_pod")
            print(f"[Scraper]   Bücher auf Seite: {len(items)}")

            for item in items:
                title = item.h3.a.get("title", "").strip()

                price_tag = item.select_one(".price_color")
                price_text = price_tag.text.strip() if price_tag else ""
                price = self._parse_price(price_text)
                if price is None:
                    print(f"[Scraper]   ⚠️ Preis nicht parsebar: {repr(price_text)} | Titel: {title}")
                    continue

                rating_tag = item.select_one("p.star-rating")
                rating_classes = rating_tag.get("class", []) if rating_tag else []
                rating_word = next((c for c in rating_classes if c != "star-rating"), "")
                rating = self._rating_to_int(rating_word)

                availability_tag = item.select_one(".availability")
                availability = availability_tag.text.strip() if availability_tag else ""

                detail_rel = item.h3.a.get("href", "")
                if not detail_rel:
                    print(f"[Scraper]   ⚠️ Kein Detail-Link gefunden | Titel: {title}")
                    continue

                detail_url = self._to_absolute(detail_rel)

                try:
                    detail_data = self.scrape_book_detail(detail_url)
                except Exception as e:
                    print(f"[Scraper]   ❌ Fehler bei Detailseite: {detail_url} | {e}")
                    continue

                books.append(
                    {
                        "title": title,
                        "price": price,
                        "rating": rating,
                        "availability": availability,
                        "category": detail_data.get("category", ""),
                        "upc": detail_data.get("upc", ""),
                        "description": detail_data.get("description", ""),
                        "cover_url": detail_data.get("cover_url", None),  # ✅ neu
                    }
                )

                if len(books) % 50 == 0:
                    print(f"[Scraper]   Fortschritt: {len(books)} Bücher gescraped")

                if sleep_sec > 0:
                    time.sleep(sleep_sec)

            next_link = soup.select_one("li.next a")
            if not next_link:
                print(f"[Scraper] Fertig. Gesamt: {len(books)} Bücher")
                break

            next_rel = next_link.get("href", "")
            next_url = self._next_page_url(current_page_url=next_url, next_rel=next_rel)

        return books

    def scrape_book_detail(self, detail_url: str) -> dict:
        soup = self._get_soup(detail_url)

        breadcrumb = soup.select("ul.breadcrumb li a")
        category = breadcrumb[2].text.strip() if len(breadcrumb) >= 3 else ""

        desc = ""
        desc_header = soup.select_one("#product_description")
        if desc_header:
            p = desc_header.find_next("p")
            if p:
                desc = p.text.strip()

        upc = ""
        for row in soup.select("table.table.table-striped tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td and th.text.strip() == "UPC":
                upc = td.text.strip()
                break

        # ✅ Cover-URL scrapen (Detailseite hat ein img mit relativem src)
        cover_url = None
        img = soup.select_one("div.item.active img")
        if img and img.get("src"):
            cover_url = urljoin(detail_url, img["src"])

        return {"category": category, "description": desc, "upc": upc, "cover_url": cover_url}

    def _to_absolute(self, href: str) -> str:
        if href.startswith("http"):
            return href
        href = href.replace("../../../", "")
        return self.base_url + "catalogue/" + href

    def _next_page_url(self, current_page_url: str, next_rel: str) -> str:
        if "catalogue/" in current_page_url:
            prefix = current_page_url.split("catalogue/")[0] + "catalogue/"
            return prefix + next_rel
        return self.base_url + next_rel