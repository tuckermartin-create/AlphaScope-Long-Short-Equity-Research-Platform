"""Saves AlphaScope's data in the viewer's own browser.

Files written on the server would be lost whenever a hosted app restarts or is
updated, and would be shared by everyone who opens the app. Browser storage
belongs to one viewer and survives reloads, restarts, and updates.
"""

from pathlib import Path

import pandas as pd
import streamlit.components.v1 as components


_browser_storage = components.declare_component(
    "browser_storage", path=str(Path(__file__).with_name("browser_storage"))
)


def sync(data):
    """Write `data` to the browser and return what was stored when the page opened.

    Pass None until the stored data has been loaded. Returns None until the
    browser has answered, then {"available": bool, "data": dict}.
    """
    return _browser_storage(data=data, key="browser_storage", default=None)


# ---------------------------------------------------------------------------
# Converting tables to and from plain JSON values
# ---------------------------------------------------------------------------
def table_to_records(table, date_columns):
    """A table as a list of plain dictionaries, with dates as text."""
    if table is None:
        return None
    records = table.copy()
    for column in date_columns:
        records[column] = pd.to_datetime(records[column]).dt.strftime("%Y-%m-%d")
    return records.to_dict("records")


def records_to_table(records, columns, date_columns):
    """The reverse of table_to_records."""
    table = pd.DataFrame(records or [], columns=columns)
    for column in date_columns:
        table[column] = pd.to_datetime(table[column]).dt.date
    return table


def steps_to_dict(steps):
    """Daily steps as {"2026-11-01": 8500, ...}."""
    if steps is None:
        return None
    return {day.strftime("%Y-%m-%d"): float(count) for day, count in steps.items()}


def dict_to_steps(values):
    """The reverse of steps_to_dict."""
    if not values:
        return None
    steps = pd.Series(values, dtype=float)
    steps.index = pd.to_datetime(steps.index)
    return steps.sort_index().rename("Steps").rename_axis("Date")
