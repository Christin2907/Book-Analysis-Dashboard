import pandas as pd


class DataProcessor:
    def to_dataframe(self, books: list) -> pd.DataFrame:
        df = pd.DataFrame(books)
        for col in ("price", "rating"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def filter_df(self, df: pd.DataFrame, categories: list, price_min: float, price_max: float, ratings: list, title_query: str):
        out = df.copy()
        if categories:
            out = out[out["category"].isin(categories)]

        out = out[out["price"].between(price_min, price_max)]

        if ratings:
            out = out[out["rating"].isin(ratings)]

        if title_query:
            out = out[out["title"].str.contains(title_query, case=False, na=False)]

        return out

    def price_stats_by_category(self, df: pd.DataFrame) -> pd.DataFrame:
        return (
            df.groupby("category")["price"]
            .agg(["mean", "min", "max"])
            .reset_index()
            .sort_values("mean", ascending=False)
        )