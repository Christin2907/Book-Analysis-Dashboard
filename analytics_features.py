# analytics_features.py
import pandas as pd
import numpy as np


_FILL_COLS = {
    "cover_fill": "cover_url",
    "author_fill": "author",
    "year_fill": "publish_year",
    "desc_fill": "description",
    "avail_fill": "availability",
}


def data_quality_metrics(df: pd.DataFrame) -> dict:
    """Calculates data quality metrics (completeness)."""
    total = len(df)
    out = {"total": total, **{k: 0.0 for k in _FILL_COLS}}
    if total == 0:
        return out

    def fill_rate(col: str) -> float:
        # Share of non-empty values (NaN or "" counts as missing)
        if col not in df.columns:
            return 0.0
        s = df[col]
        return float((s.notna() & (s.astype(str).str.strip() != "")).mean())

    out.update({k: fill_rate(col) for k, col in _FILL_COLS.items()})
    return out


def author_analytics(df: pd.DataFrame, top_n: int = 10) -> dict:
    """Author analytics: top authors by count + avg rating/price."""
    empty_top = pd.DataFrame(columns=["author", "books"])
    empty_stats = pd.DataFrame(columns=["author", "books", "avg_rating", "avg_price"])

    if "author" not in df.columns or df.empty:
        return {"top_authors_count": empty_top, "author_stats": empty_stats}

    d = df.copy()
    d["author"] = d["author"].fillna("").astype(str).str.strip()
    d = d[d["author"] != ""]

    if d.empty:
        return {"top_authors_count": empty_top, "author_stats": empty_stats}

    top_authors = (
        d["author"].value_counts().head(top_n).rename_axis("author").reset_index(name="books")
    )

    author_stats = (
        d.groupby("author", as_index=False)
        .agg(books=("title", "count"), avg_rating=("rating", "mean"), avg_price=("price", "mean"))
        .sort_values(["books", "avg_rating"], ascending=[False, False])
        .head(top_n)
    )

    return {"top_authors_count": top_authors, "author_stats": author_stats}


def segment_books(df: pd.DataFrame) -> pd.DataFrame:
    """Segmentation: Price (Low/Mid/High) x Rating (Low/High)"""
    if df.empty:
        return df.assign(segment=pd.Series(dtype=str))

    d = df.copy()

    # Robust thresholds via quantiles
    p20, p80 = map(float, (d["price"].quantile(0.20), d["price"].quantile(0.80)))

    def price_bucket(x: float) -> str:
        # Price classes (dynamic labels)
        if x <= p20:
            return f"Low Price: <{round(p20)}"
        if x <= p80:
            return f"Mid Price: >{round(p20)} & <{round(p80)}"
        return f"High Price: >{round(p80)}"

    d["price_bucket"] = d["price"].apply(price_bucket)
    d["rating_bucket"] = np.where(d["rating"] >= 4, "High Rating >=4", "Low Rating <4")
    d["segment"] = d["price_bucket"] + "\n" + d["rating_bucket"]
    return d


def hidden_gems(df: pd.DataFrame, min_rating: float = 4.0, max_price_quantile: float = 0.35) -> pd.DataFrame:
    """Hidden Gems: high rating + low price (quantile-based)."""
    if df.empty:
        return df

    d = df.copy()
    price_thr = float(d["price"].quantile(max_price_quantile))

    gems = d[(d["rating"] >= min_rating) & (d["price"] <= price_thr)].copy()
    gems = gems.sort_values(["rating", "price"], ascending=[False, True])

    cols = [
        c
        for c in ["title", "category", "price", "rating", "availability", "author", "publish_year"]
        if c in gems.columns
    ]
    return gems[cols]


def category_rating_heatmap_source(df: pd.DataFrame) -> pd.DataFrame:
    """Heatmap data source: Category x Rating -> Count"""
    if df.empty:
        return pd.DataFrame(columns=["category", "rating", "count"])

    d = df.dropna(subset=["category", "rating"]).copy()
    d["category"] = d["category"].astype(str)
    d["rating"] = d["rating"].astype(int)

    pivot = d.groupby(["category", "rating"]).size().reset_index(name="count")
    pivot["rating_label"] = pivot["rating"].astype(str) + " ⭐"
    return pivot


def generate_insights(df: pd.DataFrame) -> list[str]:
    """Generates short insights (used only if your UI calls it)."""
    if df.empty:
        return ["No data available. Please run Refresh."]

    insights: list[str] = []

    cat_price = df.groupby("category")["price"].mean().sort_values(ascending=False)
    if not cat_price.empty:
        insights.append(
            f"Most expensive category on average: **{cat_price.index[0]}** (avg £{cat_price.iloc[0]:.2f})."
        )

    cat_rating = df.groupby("category")["rating"].mean().sort_values(ascending=False)
    if not cat_rating.empty:
        insights.append(
            f"Best-rated category on average: **{cat_rating.index[0]}** (avg {cat_rating.iloc[0]:.2f} ⭐)."
        )

    if df["price"].notna().any() and df["rating"].notna().any():
        corr = float(df["price"].corr(df["rating"]))
        insights.append(f"Price vs rating correlation: **r = {corr:.3f}** (near 0 ⇒ weak linear relationship).")

    if "cover_url" in df.columns:
        missing_cover = int((df["cover_url"].isna() | (df["cover_url"].astype(str).str.strip() == "")).sum())
        insights.append(f"**{missing_cover}** books currently have **no cover**.")

    try:
        vs = value_score(df)
        if not vs.empty:
            best = vs.iloc[0]
            insights.append(
                f"Best value: **{best['title']}** (score {best['value_score']:.2f}, {best['rating']} ⭐, £{best['price']:.2f})."
            )
    except Exception:
        pass

    try:
        over = overpriced_detector(df)
        if isinstance(over, pd.DataFrame):
            insights.append(f"Overpriced candidates (default rule): **{len(over)}** books.")
    except Exception:
        pass

    return insights


def value_score(df: pd.DataFrame) -> pd.DataFrame:
    """Value Score: high rating at low price.

    value_score = rating / log(price + 1)  -> higher is better.
    """
    if df.empty:
        return df

    d = df.dropna(subset=["price", "rating"]).copy()
    d["price_safe"] = d["price"].clip(lower=0.01)
    d["value_score"] = d["rating"] / np.log1p(d["price_safe"])

    cols = [
        c
        for c in ["title", "category", "price", "rating", "value_score", "availability", "author", "publish_year"]
        if c in d.columns
    ]
    return d[cols].sort_values("value_score", ascending=False)


def overpriced_detector(df: pd.DataFrame, low_rating_max: float = 3.0, high_price_quantile: float = 0.80) -> pd.DataFrame:
    """Overpriced: low rating + high price (quantile-based).

    Example: rating <= 3.0 and price >= 80th percentile.
    """
    if df.empty:
        return df

    d = df.dropna(subset=["price", "rating"]).copy()
    price_thr = float(d["price"].quantile(high_price_quantile))

    bad = d[(d["rating"] <= low_rating_max) & (d["price"] >= price_thr)].copy()
    bad = bad.sort_values(["price", "rating"], ascending=[False, True])

    cols = [
        c
        for c in ["title", "category", "price", "rating", "availability", "author", "publish_year"]
        if c in bad.columns
    ]
    return bad[cols]