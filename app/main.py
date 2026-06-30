from importers.paths import DB_PATH

import streamlit as st


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
