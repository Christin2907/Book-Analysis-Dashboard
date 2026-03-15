# 📚 BookScout – Book Analysis Dashboard

BookScout is an **end-to-end data pipeline and analytics dashboard** for collecting, enriching, storing, and analyzing book data from an online source.

The project demonstrates how modern **data engineering workflows**—web scraping, API enrichment, data storage, analytics, and visualization—can be combined into a complete pipeline.

---

# 🚀 Project Overview

BookScout automatically:

1. Scrapes book data from an online bookstore
2. Enriches the dataset using an external API
3. Stores the data in a structured database
4. Tracks historical price changes
5. Visualizes insights in an interactive dashboard

---

# 🏗️ Architecture

The system consists of several modular components:

| Layer                      | Description                              |
| -------------------------- | ---------------------------------------- |
| **Data Acquisition**       | Web scraping of book data                |
| **API Enrichment**         | Metadata enrichment via OpenLibrary API  |
| **Pipeline Orchestration** | Controls the data pipeline workflow      |
| **Database Layer**         | Structured storage using SQLite          |
| **Analytics Layer**        | Data processing and feature calculations |
| **Presentation Layer**     | Interactive dashboard with Streamlit     |

---

# 🔎 Data Source

Book data is collected from:

```
books.toscrape.com
```

Extracted information includes:

* Title
* Price
* Rating
* Category
* Availability
* UPC
* Description
* Cover image URL

---

# 🗄️ Database

Data is stored in a **SQLite database** using **SQLAlchemy ORM**.

Main tables:

**Books**

* title
* category
* price
* rating
* availability
* description
* UPC
* author
* publication year
* cover URL

**price_history**

* UPC
* price
* timestamp

This enables **price trend analysis across multiple scans**.

---

# 📊 Analytics

Analytics features include:

* Data quality metrics
* Author analysis
* Price segmentation
* Value score calculation

---

# 📈 Dashboard

The project includes an **interactive BI dashboard built with Streamlit**.

Features:

* Filter by category, price, and rating
* KPI overview
* Price and rating analysis
* Category comparison
* Segmentation charts
* Drill-down into book details

Visualization library: **Altair**

---

# 🛠️ Tech Stack

| Technology      | Purpose                   |
| --------------- | ------------------------- |
| Python          | Core programming language |
| BeautifulSoup   | Web scraping              |
| requests        | HTTP requests             |
| OpenLibrary API | Metadata enrichment       |
| SQLite          | Database                  |
| SQLAlchemy      | ORM                       |
| Streamlit       | Dashboard                 |
| Altair          | Data visualization        |

---

# ✨ Key Features

* Automated web scraping pipeline
* API-based metadata enrichment
* Upsert logic to prevent duplicates
* Historical price tracking
* Interactive data dashboard

---

# 📌 Use Cases

* Book price analysis
* Market insights
* Data pipeline demonstrations
* BI dashboard exploration

---
