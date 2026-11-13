"""Reads daily step counts from health app exports.

Supported files:
- Apple Health: the export.zip (or the export.xml inside it) from the Health app.
- Fitbit: the Google Takeout zip, a steps-*.json file from it, or a CSV export.
- Google Fit: the "Daily activity metrics.csv" file from Google Takeout.
- Any other CSV that has a date column and a steps column.

Every reader returns the same thing: total steps for each day.
"""

import io
import json
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pandas as pd


class StepFileError(Exception):
    """Raised when an uploaded file cannot be understood."""


def daily_totals(dates, steps):
    """Add up steps by day and return them in date order."""
    totals = (
        pd.DataFrame(
            {
                "Date": pd.DatetimeIndex(pd.to_datetime(dates)).normalize(),
                "Steps": np.asarray(steps, dtype=float),
            }
        )
        .dropna()
        .groupby("Date")["Steps"]
        .sum()
        .sort_index()
    )
    if totals.empty:
        raise StepFileError("No step counts were found in that file.")
    return totals


# ---------------------------------------------------------------------------
# Apple Health
# ---------------------------------------------------------------------------
def read_apple_health(xml_file):
    """Read step records from Apple Health's export.xml.

    The file can be very large, so it is read one record at a time. A phone
    and a watch both count the same steps, so for each day the device with
    the highest total is used instead of adding the devices together.
    """
    steps_by_day_and_device = {}
    root = None
    for event, element in ET.iterparse(xml_file, events=("start", "end")):
        if root is None:
            root = element
        if event == "end" and element.tag == "Record":
            if element.get("type") == "HKQuantityTypeIdentifierStepCount":
                key = (element.get("startDate")[:10], element.get("sourceName"))
                steps_by_day_and_device[key] = (
                    steps_by_day_and_device.get(key, 0) + float(element.get("value"))
                )
            root.clear()  # Free memory as we go.

    if not steps_by_day_and_device:
        raise StepFileError("No step counts were found in that Apple Health export.")

    records = pd.DataFrame(
        [(day, device, steps) for (day, device), steps in steps_by_day_and_device.items()],
        columns=["Date", "Device", "Steps"],
    )
    best_device_per_day = records.groupby("Date")["Steps"].max()
    return daily_totals(best_device_per_day.index, best_device_per_day.values)


# ---------------------------------------------------------------------------
# Fitbit
# ---------------------------------------------------------------------------
def read_fitbit_json(json_files):
    """Read Fitbit's steps-*.json files from a Google Takeout export."""
    dates, steps = [], []
    for json_file in json_files:
        for entry in json.load(json_file):
            dates.append(entry["dateTime"])
            steps.append(float(entry["value"]))
    return daily_totals(pd.to_datetime(dates, format="%m/%d/%y %H:%M:%S"), steps)


# ---------------------------------------------------------------------------
# CSV files (Fitbit, Google Fit, or any date + steps table)
# ---------------------------------------------------------------------------
def read_csv_steps(csv_file):
    """Read a CSV that has a date column and a steps column."""
    content = csv_file.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig", errors="replace")

    # Some exports (Fitbit) put a title line above the column names.
    for rows_to_skip in (0, 1):
        try:
            table = pd.read_csv(io.StringIO(content), skiprows=rows_to_skip, thousands=",")
        except Exception:
            continue
        date_column = next(
            (c for c in table.columns if "date" in str(c).lower() or "day" in str(c).lower()),
            None,
        )
        steps_column = next((c for c in table.columns if "step" in str(c).lower()), None)
        if date_column is not None and steps_column is not None:
            dates = pd.to_datetime(table[date_column], errors="coerce")
            steps = pd.to_numeric(table[steps_column], errors="coerce")
            return daily_totals(dates, steps)

    raise StepFileError(
        "That CSV needs a column with dates and a column with steps "
        "(for example 'Date' and 'Steps')."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def read_step_file(file_name, file):
    """Work out what kind of export a file is and return daily step totals."""
    name = file_name.lower()
    try:
        if name.endswith(".zip"):
            with zipfile.ZipFile(file) as archive:
                names = archive.namelist()

                apple = [n for n in names if n.lower().endswith("export.xml")]
                if apple:
                    with archive.open(apple[0]) as xml_file:
                        return read_apple_health(xml_file)

                fitbit = [
                    n for n in names
                    if n.lower().split("/")[-1].startswith("steps-") and n.lower().endswith(".json")
                ]
                if fitbit:
                    return read_fitbit_json(archive.open(n) for n in fitbit)

                google_fit = [n for n in names if n.lower().endswith("daily activity metrics.csv")]
                if google_fit:
                    with archive.open(google_fit[0]) as csv_file:
                        return read_csv_steps(csv_file)

            raise StepFileError(
                "That zip file does not look like an Apple Health, Fitbit, or "
                "Google Fit export."
            )
        if name.endswith(".xml"):
            return read_apple_health(file)
        if name.endswith(".json"):
            return read_fitbit_json([file])
        if name.endswith(".csv"):
            return read_csv_steps(file)
    except StepFileError:
        raise
    except Exception as error:
        raise StepFileError("That file could not be read as a health export.") from error

    raise StepFileError("Upload a .zip, .xml, .json, or .csv file.")


def sample_steps(days=300):
    """Made-up daily steps, for trying the Step fund without a health export."""
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=days)
    random = np.random.default_rng(seed=7)
    steps = random.normal(8500, 2800, size=days)
    steps[dates.dayofweek >= 5] *= 1.2  # A bit more walking on weekends.
    return pd.Series(steps.clip(min=800).round(), index=dates, name="Steps").rename_axis("Date")
