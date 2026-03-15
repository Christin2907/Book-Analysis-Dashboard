import pandas as pd
import streamlit as st
import altair as alt
from urllib.parse import quote_plus

from database import SessionLocal, Base, engine
from models import Book
from data_processor import DataProcessor
from main import run_scrape

from analytics_features import (
    data_quality_metrics,
    author_analytics,
    segment_books,
    value_score,
)


# -----------------------------
# Shared column sets / helpers
# -----------------------------
BOOK_COLS = [
    "title","category","price","rating","availability","upc","description","author","publish_year","cover_url"
]
CARD_COLS = [
    "title","category","price","rating","availability","author","publish_year","upc"
]

def pick_cols(df, cols):
    return [c for c in cols if c in df.columns]

def safe_int_len(df):
    return int(len(df)) if df is not None else 0

# -----------------------------
# Global UI styling (bigger fonts)
# -----------------------------
st.markdown(
    """
    <style>
      /* Base text size */
      html, body, [class*="css"]  { font-size: 18px !important; }

      /* Headings a bit larger */
      h1 { font-size: 2.2rem !important; }
      h2 { font-size: 1.75rem !important; }
      h3 { font-size: 1.35rem !important; }

      /* Dataframe/table font size */
      .stDataFrame div, .stDataFrame span, .stDataFrame p {
        font-size: 17px !important;
      }

      /* Metric label/value sizes */
      [data-testid="stMetricLabel"] { font-size: 1.05rem !important; }
      [data-testid="stMetricValue"] { font-size: 2.2rem !important; }

      /* Slightly larger sidebar fonts */
      section[data-testid="stSidebar"] * { font-size: 16px !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Altair default theme (bigger axis/legend/title fonts)
def _bigger_altair_theme():
    return {
        "config": {
            "axis": {
                "labelFontSize": 16,
                "titleFontSize": 17,
                "labelLimit": 300,
            },
            "legend": {
                "labelFontSize": 16,
                "titleFontSize": 17,
            },
            "title": {"fontSize": 18},
            "view": {"stroke": "transparent"},
        }
    }


alt.themes.register("bigger", _bigger_altair_theme)
alt.themes.enable("bigger")


@st.cache_data(show_spinner=False)
def load_books_df_cached() -> pd.DataFrame:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        rows = db.query(Book).all()
        df = pd.DataFrame([
            {
                "title": r.title,
                "category": r.category,
                "price": r.price,
                "rating": r.rating,
                "availability": r.availability,
                "upc": r.upc,
                "description": r.description,
                "author": r.author,
                "publish_year": r.publish_year,
                "cover_url": r.cover_url,
            }
            for r in rows
        ])

        if "publish_year" in df.columns:
            df["publish_year"] = pd.to_numeric(df["publish_year"], errors="coerce").astype("Int64")

        return df
    finally:
        db.close()


def export_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _format_rating_number_kpi(x: float) -> str:
    if x is None or pd.isna(x):
        return "—"
    try:
        return f"{float(x):.2f}".replace(".", ",")
    except Exception:
        return "—"


def _stars_html_from_value(rating_value: float, font_px: int = 18) -> str:
    """
    Yellow stars only (no numeric prefix). Rounds to nearest whole star. Always 5 stars.
    """
    if rating_value is None or pd.isna(rating_value):
        return "<span style='color:#999;'>—</span>"
    try:
        r = float(rating_value)
        r = max(0.0, min(5.0, r))
        r_stars = int(round(r))
    except Exception:
        return "<span style='color:#999;'>—</span>"

    filled = "★" * r_stars
    empty = "★" * (5 - r_stars)

    return (
        f"<span style='font-size:{font_px}px; line-height:1; white-space:nowrap;'>"
        f"<span style='color:#f5a623;'>{filled}</span>"
        f"<span style='color:#d0d0d0;'>{empty}</span>"
        "</span>"
    )


def rating_inline_html_number_and_stars(rating) -> str:
    """
    For book cards + details:
    Show integer number (e.g. 3) + stars after it (no "/5").
    """
    if rating is None or pd.isna(rating):
        return "<span style='color:#999;'>—</span>"

    try:
        r_num = float(rating)
        r_num = max(0.0, min(5.0, r_num))
        r_int = int(round(r_num))
    except Exception:
        return "<span style='color:#999;'>—</span>"

    stars = _stars_html_from_value(r_int, font_px=18)
    return (
        "<span style='font-size:18px; line-height:1; white-space:nowrap;'>"
        f"<span style='color:#111; font-weight:600; margin-right:8px;'>{r_int}</span>"
        f"{stars}"
        "</span>"
    )


def amazon_search_url(title: str, author: str | None = None) -> str:
    q = title.strip() if isinstance(title, str) else ""
    if author and isinstance(author, str) and author.strip():
        q = f"{q} {author.strip()}"
    return "https://www.amazon.com/s?k=" + quote_plus(q)


def kpi_block(df: pd.DataFrame):
    """
    Avg rating: number + yellow stars INLINE.
    - No bold for Avg rating value (requested previously)
    - Stars bigger (requested now)
    """
    c1, c2, c3 = st.columns(3)

    c1.metric("Books", safe_int_len(df))
    c2.metric("Avg price", f"£ {df['price'].mean():.2f}" if len(df) else "—")

    if len(df) and df["rating"].dropna().any():
        avg_r = float(df["rating"].mean())
        num_txt = _format_rating_number_kpi(avg_r)

        # Bigger stars for KPI
        stars_html = _stars_html_from_value(avg_r, font_px=20)

        c3.markdown(
            f"""
            <div style="padding: 0;">
              <div style="font-size: 1.05rem; color: rgba(49, 51, 63, 0.6); margin-bottom: 0.25rem;">
                Avg rating
              </div>
              <div style="font-size: 2.2rem; font-weight: 400; line-height: 1.1; display:flex; align-items:baseline; gap:10px;">
                <span>{num_txt}</span>
                <span style="transform: translateY(-2px);">{stars_html}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        c3.metric("Avg rating", "—")


def rating_distribution_chart(df: pd.DataFrame):
    rating_counts = df["rating"].value_counts().sort_index().reset_index()
    rating_counts.columns = ["rating", "count"]
    rating_counts["rating_label"] = rating_counts["rating"].astype(int).astype(str) + " ⭐"

    chart = (
        alt.Chart(rating_counts)
        .mark_bar()
        .encode(
            x=alt.X("rating_label:O", title="Rating", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("count:Q", title="Books"),
            tooltip=["rating_label", "count"],
        )
        .properties(height=380)
    )
    st.altair_chart(chart, use_container_width=True)


def segment_chart_and_drilldown(df: pd.DataFrame):
    st.markdown("### Segmentation")

    seg_df = segment_books(df)

    seg_counts = seg_df.groupby(["price_bucket", "rating_bucket"]).size().reset_index(name="count")

    seg_counts["price_bucket_rank"] = seg_counts["price_bucket"].apply(
        lambda s: 0 if str(s).startswith("Low Price") else 1 if str(s).startswith("Mid Price") else 2
    )

    bars = (
        alt.Chart(seg_counts)
        .mark_bar()
        .encode(
            x=alt.X(
                "price_bucket:O",
                title="Price segment",
                sort=alt.SortField(field="price_bucket_rank", order="ascending"),
                axis=alt.Axis(labelAngle=0),
            ),
            xOffset=alt.XOffset("rating_bucket:O"),
            y=alt.Y("count:Q", title="Books"),
            color=alt.Color("rating_bucket:O", title="Rating segment"),
            tooltip=[
                alt.Tooltip("price_bucket:O", title="Price segment"),
                alt.Tooltip("rating_bucket:O", title="Rating segment"),
                alt.Tooltip("count:Q", title="Books"),
            ],
        )
    )

    labels = (
        alt.Chart(seg_counts)
        .mark_text(dy=-10, fontSize=14)
        .encode(
            x=alt.X(
                "price_bucket:O",
                sort=alt.SortField(field="price_bucket_rank", order="ascending"),
            ),
            xOffset=alt.XOffset("rating_bucket:O"),
            y=alt.Y("count:Q"),
            text=alt.Text("count:Q"),
        )
    )

    st.altair_chart((bars + labels).properties(height=420), use_container_width=True)

    st.markdown("#### Drill-down: pick a segment → view matching books")

    price_opts = ["(all)"] + seg_counts.sort_values("price_bucket_rank")["price_bucket"].drop_duplicates().tolist()

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        sel_price_bucket = st.selectbox("Price segment", price_opts, index=0, key="drill_price_bucket")
    with c2:
        sel_rating_bucket = st.selectbox(
            "Rating segment", ["(all)", "High Rating", "Low Rating"], index=0, key="drill_rating_bucket"
        )
    with c3:
        st.caption("Tip: Select both segments to narrow down the table below.")

    drill = seg_df.copy()
    if sel_price_bucket != "(all)":
        drill = drill[drill["price_bucket"] == sel_price_bucket]
    if sel_rating_bucket != "(all)":
        drill = drill[drill["rating_bucket"] == sel_rating_bucket]

    cols = [
        c
        for c in ["title", "category", "price", "rating", "availability", "author", "publish_year", "upc"]
        if c in drill.columns
    ]
    st.dataframe(
        drill.sort_values(["rating", "price"], ascending=[False, True])[cols].head(200),
        use_container_width=True,
    )


def init_state():
    if "favorites" not in st.session_state:
        st.session_state["favorites"] = set()
    if "detail_upc" not in st.session_state:
        st.session_state["detail_upc"] = None


def toggle_favorite(upc: str):
    favs = st.session_state["favorites"]
    if upc in favs:
        favs.remove(upc)
    else:
        favs.add(upc)
    st.session_state["favorites"] = favs


def _fmt_year(y):
    if y is None or (isinstance(y, float) and pd.isna(y)) or pd.isna(y):
        return "—"
    try:
        return str(int(y))
    except Exception:
        return "—"


def show_book_detail(df: pd.DataFrame, upc: str):
    row = df[df["upc"] == upc]
    if row.empty:
        st.error("Book not found (UPC not in DataFrame).")
        return

    b = row.iloc[0]

    c1, c2 = st.columns([1, 8])
    with c1:
        if st.button("← Back", key="detail_back"):
            st.session_state["detail_upc"] = None
            st.rerun()
    with c2:
        st.subheader("Book details")

    is_fav = upc in st.session_state["favorites"]
    fav_label = "⭐ Remove Favorite" if is_fav else "⭐ Add Favorite"
    if st.button(fav_label, key=f"detail_fav_{upc}"):
        toggle_favorite(upc)
        st.rerun()

    left, right = st.columns([1, 2])
    with left:
        cover_url = b.get("cover_url", None)
        if cover_url and pd.notna(cover_url):
            st.image(cover_url, use_container_width=True)
            st.markdown(f"[Open cover link]({cover_url})")
        else:
            st.info("No cover available.")

    with right:
        title = b.get("title", "")
        author = b.get("author", None)

        st.markdown(f"### {title}")
        st.write(f"**UPC:** {b.get('upc','—')}")
        st.write(f"**Category:** {b.get('category','—')}")
        st.write(
            f"**Price:** £ {b.get('price', 0):.2f}"
            if pd.notna(b.get("price", None))
            else "**Price:** —"
        )

        st.markdown(
            f"**Rating:** {rating_inline_html_number_and_stars(b.get('rating', None))}",
            unsafe_allow_html=True,
        )

        st.write(f"**Author:** {author if author else '—'}")
        st.write(f"**Publish year:** {_fmt_year(b.get('publish_year', None))}")
        st.write(f"**Availability:** {b.get('availability','—')}")

        st.link_button("🛒 View on Amazon", amazon_search_url(str(title), str(author) if author else None))

    st.markdown("### Description")
    desc = b.get("description", "")
    if desc and isinstance(desc, str) and desc.strip():
        st.write(desc)
    else:
        st.caption("No description available.")


# -----------------------------
# Streamlit App
# -----------------------------
st.set_page_config(page_title="BookScout", layout="wide")
st.title("📚 BookScout – Book analytics dashboard")

init_state()
processor = DataProcessor()

colA, colB = st.columns([1, 5])
with colA:
    if st.button("🔄 Refresh (scrape again)"):
        with st.spinner("Scraping in progress..."):
            run_scrape()
        st.cache_data.clear()
        st.success("Data updated!")
        st.rerun()

df = load_books_df_cached()

if df.empty:
    st.warning("No data in the database. Click Refresh to scrape.")
    st.stop()

required_cols = {"title", "category", "price", "rating", "availability", "upc"}
missing = required_cols - set(df.columns)
if missing:
    st.error(f"Missing columns in df: {sorted(list(missing))}")
    st.stop()

st.sidebar.header("Filters")

with st.sidebar.form("filter_form"):
    all_categories = sorted([c for c in df["category"].dropna().unique().tolist() if c])
    sel_categories = st.multiselect("Category", options=all_categories, default=st.session_state.get("f_categories", []))

    all_ratings = sorted(df["rating"].dropna().unique().tolist())
    sel_ratings = st.multiselect("Rating (stars)", options=all_ratings, default=st.session_state.get("f_ratings", []))

    min_price = float(df["price"].min())
    max_price = float(df["price"].max())
    default_range = st.session_state.get("f_price_range", (min_price, max_price))
    price_range = st.slider("Price range (£)", min_value=min_price, max_value=max_price, value=default_range)

    title_query = st.text_input("Search by title", value=st.session_state.get("f_title_query", ""))

    apply_btn = st.form_submit_button("✅ Apply filters")

if apply_btn:
    st.session_state["f_categories"] = sel_categories
    st.session_state["f_ratings"] = sel_ratings
    st.session_state["f_price_range"] = price_range
    st.session_state["f_title_query"] = title_query

sel_categories = st.session_state.get("f_categories", [])
sel_ratings = st.session_state.get("f_ratings", [])
price_range = st.session_state.get("f_price_range", (float(df["price"].min()), float(df["price"].max())))
title_query = st.session_state.get("f_title_query", "")

filtered = processor.filter_df(
    df=df,
    categories=sel_categories,
    price_min=price_range[0],
    price_max=price_range[1],
    ratings=sel_ratings,
    title_query=title_query,
)

tab_overview, tab_analyses, tab_books, tab_compare = st.tabs(["Overview", "Analyses", "Books", "Compare"])

with tab_overview:
    st.subheader("Overview")
    kpi_block(filtered)
    st.divider()

    st.markdown("### Prices by category (avg / min / max)")
    price_stats = (
        filtered.groupby("category")["price"]
        .agg(avg="mean", min="min", max="max")
        .reset_index()
        .sort_values("avg", ascending=False)
    )

    if price_stats.empty:
        st.info("No data for the current filters.")
    else:
        top_n = st.slider("Top categories by avg price", 5, 50, 20, key="ov_top_n")
        ps = price_stats.head(top_n).copy()
        ps_long = ps.melt(id_vars=["category"], value_vars=["avg", "min", "max"], var_name="metric", value_name="price")
        metric_order = ["avg", "min", "max"]

        price_chart = (
            alt.Chart(ps_long)
            .mark_bar()
            .encode(
                x=alt.X(
                    "category:O",
                    title="Category",
                    axis=alt.Axis(
                        labelAngle=-45,
                        labelOverlap=False,   # <-- wichtig: nichts ausblenden
                        labelLimit=0,         # <-- wichtig: nicht abschneiden/ellipsen
                    ),
                ),
                y=alt.Y("price:Q", title="Price (£)", stack=True),
                color=alt.Color("metric:O", title="Metric", sort=metric_order),
                tooltip=[
                    alt.Tooltip("category:O", title="Category"),
                    alt.Tooltip("metric:O", title="Metric"),
                    alt.Tooltip("price:Q", title="Price", format=".2f"),
                ],
            )
            .properties(height=460)
        )
        st.altair_chart(price_chart, use_container_width=True)

    st.divider()

    st.markdown("### Rating distribution")
    if filtered["rating"].dropna().empty:
        st.info("No rating data for the current filters.")
    else:
        rating_distribution_chart(filtered)

    st.divider()

    st.markdown("### Export")
    st.download_button(
        "⬇️ Download CSV",
        data=export_csv_bytes(filtered),
        file_name="bookscout_filtered.csv",
        mime="text/csv",
        disabled=filtered.empty,
    )

    st.markdown("---")
    st.caption("powered by A-Team/ Dream-Team")

with tab_analyses:
    st.subheader("Analyses")
    if filtered.empty:
        st.warning("No data for the current filters.")
    else:
        st.markdown("### Data quality")
        st.caption("Completeness metrics for key fields.")

        dq_all = data_quality_metrics(df)
        dq_f = data_quality_metrics(filtered)

        st.markdown("#### Overall (all data)")
        q1, q2, q3, q4, q5 = st.columns(5)
        q1.metric("Rows", dq_all["total"])
        q2.metric("Cover fill", f"{dq_all['cover_fill']*100:.1f}%")
        q3.metric("Author fill", f"{dq_all['author_fill']*100:.1f}%")
        q4.metric("Year fill", f"{dq_all['year_fill']*100:.1f}%")
        q5.metric("Description fill", f"{dq_all['desc_fill']*100:.1f}%")

        st.markdown("#### Current filters")
        f1, f2, f3, f4, f5 = st.columns(5)
        f1.metric("Rows", dq_f["total"])
        f2.metric("Cover fill", f"{dq_f['cover_fill']*100:.1f}%")
        f3.metric("Author fill", f"{dq_f['author_fill']*100:.1f}%")
        f4.metric("Year fill", f"{dq_f['year_fill']*100:.1f}%")
        f5.metric("Description fill", f"{dq_f['desc_fill']*100:.1f}%")

        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Top 10 most expensive books")
            st.dataframe(
                filtered.sort_values("price", ascending=False)[["title", "category", "price", "rating", "availability"]].head(10),
                use_container_width=True,
            )
        with c2:
            st.markdown("### Top 10 cheapest books")
            st.dataframe(
                filtered.sort_values("price", ascending=True)[["title", "category", "price", "rating", "availability"]].head(10),
                use_container_width=True,
            )

        st.divider()

        st.markdown("### Author analytics (OpenLibrary)")
        top_n_auth = st.slider("Top authors", 5, 30, 10, key="auth_top_n")
        auth = author_analytics(filtered, top_n=top_n_auth)
        st.markdown("**Author stats (books, avg rating, avg price)**")
        st.dataframe(auth["author_stats"], use_container_width=True)

        st.divider()
        segment_chart_and_drilldown(filtered)

        st.divider()
        st.markdown("### Value score (best deals)")
        top_n_value = st.slider("Top N", 5, 50, 15, key="vs_top_n")
        vs = value_score(filtered)
        if vs.empty:
            st.info("Not enough data for Value Score.")
        else:
            st.caption("Value score = rating / log(price + 1). Higher is better.")
            st.dataframe(vs.head(top_n_value), use_container_width=True)

with tab_books:
    st.subheader("Books")

    if st.session_state["detail_upc"]:
        show_book_detail(df=df, upc=st.session_state["detail_upc"])
    else:
        if len(sel_categories) == 0:
            st.info("Select at least **one category** in the sidebar to view books.")
        elif filtered.empty:
            st.warning("No results for the current filters.")
        else:
            c1, c2, c3 = st.columns([2, 2, 3])
            with c1:
                sort_option = st.selectbox("Sort by", ["Price (asc)", "Price (desc)", "Title (A-Z)", "Rating (desc)"], key="tile_sort")
            with c2:
                show_only_favs = st.checkbox("Show favorites only", value=False, key="tile_only_favs")
            with c3:
                st.caption(f"Favorites: {len(st.session_state['favorites'])}")

            show_df = filtered.copy()

            if show_only_favs:
                favs = st.session_state["favorites"]
                show_df = show_df[show_df["upc"].isin(list(favs))]

            if sort_option == "Price (asc)":
                show_df = show_df.sort_values("price", ascending=True)
            elif sort_option == "Price (desc)":
                show_df = show_df.sort_values("price", ascending=False)
            elif sort_option == "Title (A-Z)":
                show_df = show_df.sort_values("title", ascending=True)
            elif sort_option == "Rating (desc)":
                show_df = show_df.sort_values("rating", ascending=False)

            count = len(show_df)
            if count == 0:
                st.warning("No books for this view (maybe no favorites in the current filters).")
            else:
                if count <= 12:
                    max_cards = count
                else:
                    max_cards = st.slider(
                        "Number of books to show",
                        min_value=12,
                        max_value=min(300, count),
                        value=min(60, count),
                        step=12,
                        key="tile_count",
                    )

                show_df = show_df.head(max_cards)

                cols_per_row = 3
                rows = (len(show_df) + cols_per_row - 1) // cols_per_row

                for r in range(rows):
                    cols = st.columns(cols_per_row)
                    for c in range(cols_per_row):
                        idx = r * cols_per_row + c
                        if idx >= len(show_df):
                            break

                        book = show_df.iloc[idx]

                        title = str(book.get("title", ""))
                        price = book.get("price", None)
                        author = book.get("author", None)
                        rating = book.get("rating", None)
                        cover_url = book.get("cover_url", None)
                        availability = book.get("availability", None)
                        year = book.get("publish_year", None)
                        upc = book.get("upc", "")

                        is_fav = upc in st.session_state["favorites"]
                        fav_btn_label = "⭐ Remove Favorite" if is_fav else "⭐ Add Favorite"

                        with cols[c]:
                            with st.container(border=True):
                                left_img, right_txt = st.columns([1, 3])

                                with left_img:
                                    if cover_url and pd.notna(cover_url):
                                        st.image(cover_url, width=90)
                                    else:
                                        st.caption("No cover")

                                with right_txt:
                                    st.markdown(f"**{title}**")
                                    st.write(f"Price: **£ {price:.2f}**" if pd.notna(price) else "Price: —")
                                    st.markdown(f"Rating: {rating_inline_html_number_and_stars(rating)}", unsafe_allow_html=True)
                                    st.write(f"Author: **{author}**" if author and pd.notna(author) else "Author: —")
                                    st.write(f"Publish year: {_fmt_year(year)}")
                                    st.write(f"Availability: {availability}" if availability and pd.notna(availability) else "Availability: —")

                                    b1, b2, b3 = st.columns([1.2, 1.2, 1.2])
                                    with b1:
                                        if st.button(fav_btn_label, key=f"fav_{upc}_{idx}"):
                                            toggle_favorite(upc)
                                            st.rerun()
                                    with b2:
                                        st.link_button("🛒 Amazon", amazon_search_url(title, str(author) if author else None))
                                    with b3:
                                        if st.button("🔎 Details", key=f"details_{upc}_{idx}"):
                                            st.session_state["detail_upc"] = upc
                                            st.rerun()

with tab_compare:
    st.subheader("Compare: Category A vs Category B")

    cats = sorted([c for c in df["category"].dropna().unique().tolist() if c])
    if len(cats) < 2:
        st.info("Not enough categories to compare.")
    else:
        cA, cB = st.columns(2)
        with cA:
            cat_a = st.selectbox("Category A", options=cats, index=0, key="cmp_a")
        with cB:
            cat_b = st.selectbox("Add a Category", options=cats, index=1, key="cmp_b")

        df_a = df[df["category"] == cat_a].copy()
        df_b = df[df["category"] == cat_b].copy()

        a1, a2 = st.columns(2)
        with a1:
            st.markdown(f"### {cat_a}")
            kpi_block(df_a)
            if not df_a.empty:
                rating_distribution_chart(df_a)
        with a2:
            st.markdown(f"### {cat_b}")
            kpi_block(df_b)
            if not df_b.empty:
                rating_distribution_chart(df_b)

        st.divider()

        st.markdown("### Price comparison (boxplot)")
        cmp_df = pd.concat(
            [
                df_a.assign(group=cat_a)[["group", "price"]],
                df_b.assign(group=cat_b)[["group", "price"]],
            ],
            ignore_index=True,
        )

        box = (
            alt.Chart(cmp_df)
            .mark_boxplot(size=240)
            .encode(
                x=alt.X(
                    "group:O",
                    title="Category",
                    axis=alt.Axis(labelAngle=0),
                    scale=alt.Scale(paddingInner=0.15, paddingOuter=0.10),
                ),
                y=alt.Y("price:Q", title="Price (£)"),
                tooltip=["group", alt.Tooltip("price:Q", format=".2f")],
            )
            .properties(height=380)
        )
        st.altair_chart(box, use_container_width=True)
