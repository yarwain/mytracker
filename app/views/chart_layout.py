"""Streamlit layout helpers for chart sections."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import altair as alt
import streamlit as st


@contextmanager
def chart_panel(title: str, *, subtitle: str | None = None) -> Iterator[None]:
    """Render a bordered chart card with a compact header."""
    with st.container(border=True):
        st.markdown(f"**{title}**")
        if subtitle:
            st.caption(subtitle)
        yield


def render_chart(chart: alt.Chart) -> None:
    """Render an Altair chart at full container width."""
    st.altair_chart(chart, use_container_width=True)


def render_data_table(df: pd.DataFrame, *, sort_by: list[str] | None = None) -> None:
    """Render a compact always-visible data table below a chart."""
    if df.empty:
        return

    st.markdown("**Data table**")
    table = df.copy()
    if sort_by:
        table = table.sort_values(sort_by)
    st.dataframe(table, use_container_width=True, hide_index=True)


def filter_toolbar() -> None:
    """Render a compact section label for control rows."""
    st.markdown("**Controls**")
