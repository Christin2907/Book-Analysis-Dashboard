from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from database import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)

    # Listing-Daten
    title = Column(String, index=True)
    category = Column(String, index=True)
    price = Column(Float)
    rating = Column(Integer)  # 1..5
    availability = Column(String)

    # Detailseiten-Daten
    upc = Column(String, index=True)
    description = Column(Text)

    # API-Anreicherung (Open Library – best effort)
    author = Column(String, nullable=True)
    publish_year = Column(Integer, nullable=True)
    cover_url = Column(String, nullable=True)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True)

    # UPC als Referenz auf das Buch
    upc = Column(String, index=True)

    # Gespeicherter Preis zum Zeitpunkt des Scraping
    price = Column(Float)

    # Zeitpunkt der Erfassung
    scraped_at = Column(DateTime, default=datetime.utcnow)
