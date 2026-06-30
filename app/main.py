from pathlib import Path

import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "health.duckdb"


def main() -> None:
    st.set_page_config(page_title="MyTracker", layout="wide")
    st.title("MyTracker")
    st.caption("Health statistics from Apple Health, Garmin, and FatSecret")

    if not DB_PATH.exists():
        st.info(f"No database yet. Import data to create `{DB_PATH}`.")
        return

    st.success(f"Connected to `{DB_PATH}`")


if __name__ == "__main__":
    main()
