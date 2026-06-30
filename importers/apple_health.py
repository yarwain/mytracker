"""Import Apple Health export data."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import BinaryIO, TextIO

import duckdb

from importers.db import connect, init_schema, start_import
from importers.paths import DB_PATH

BATCH_SIZE = 5_000


@dataclass(frozen=True)
class ImportStats:
    records: int
    workouts: int
    activity_summaries: int
    import_id: int


def parse_apple_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z")


def parse_apple_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _open_export_xml(export_path: Path) -> tuple[BinaryIO | TextIO, None]:
    if export_path.is_dir():
        for candidate in (
            export_path / "export.xml",
            export_path / "apple_health_export" / "export.xml",
        ):
            if candidate.exists():
                return candidate.open("rb"), None
        msg = f"No export.xml found under {export_path}"
        raise FileNotFoundError(msg)

    if export_path.name == "export.xml" or export_path.suffix.lower() == ".xml":
        return export_path.open("rb"), None

    msg = f"Unsupported Apple Health export path: {export_path}"
    raise FileNotFoundError(msg)


def _find_export_xml_in_zip(archive: zipfile.ZipFile) -> str:
    candidates = [name for name in archive.namelist() if name.endswith("export.xml")]
    if not candidates:
        msg = "No export.xml found in Apple Health zip export"
        raise FileNotFoundError(msg)

    preferred = "apple_health_export/export.xml"
    for name in candidates:
        if name.endswith(preferred):
            return name
    return candidates[0]


def iter_health_elements(stream: BinaryIO | TextIO) -> Iterator[tuple[str, ET.Element]]:
    context = ET.iterparse(stream, events=("end",))
    for _, element in context:
        tag = local_tag(element.tag)
        if tag in {"Record", "Workout", "ActivitySummary"}:
            yield tag, element
        element.clear()


def clear_apple_health_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("DELETE FROM apple_health_records")
    conn.execute("DELETE FROM apple_health_workouts")
    conn.execute("DELETE FROM apple_health_activity_summaries")
    conn.execute("DELETE FROM imports WHERE source = 'apple_health'")


def import_apple_health(
    export_path: Path,
    db_path: Path = DB_PATH,
    *,
    replace: bool = False,
) -> ImportStats:
    """Load Apple Health export XML into DuckDB."""
    export_path = export_path.expanduser().resolve()
    db_path = db_path.expanduser().resolve()

    conn = connect(db_path)
    try:
        init_schema(conn)
        if replace:
            clear_apple_health_tables(conn)

        import_id = start_import(conn, "apple_health", export_path)

        if export_path.suffix.lower() == ".zip":
            with zipfile.ZipFile(export_path) as archive:
                xml_name = _find_export_xml_in_zip(archive)
                with archive.open(xml_name) as stream:
                    stats = _load_elements(conn, stream, import_id)
        else:
            stream, _ = _open_export_xml(export_path)
            try:
                stats = _load_elements(conn, stream, import_id)
            finally:
                stream.close()

        return stats
    finally:
        conn.close()


def _load_elements(
    conn: duckdb.DuckDBPyConnection,
    stream: BinaryIO | TextIO,
    import_id: int,
) -> ImportStats:
    record_batch: list[tuple] = []
    workout_batch: list[tuple] = []
    summary_batch: list[tuple] = []

    record_count = 0
    workout_count = 0
    summary_count = 0

    for tag, element in iter_health_elements(stream):
        if tag == "Record":
            row = _parse_record(element, import_id)
            if row is not None:
                record_batch.append(row)
                record_count += 1
                if len(record_batch) >= BATCH_SIZE:
                    _insert_records(conn, record_batch)
                    record_batch.clear()
        elif tag == "Workout":
            row = _parse_workout(element, import_id)
            if row is not None:
                workout_batch.append(row)
                workout_count += 1
                if len(workout_batch) >= BATCH_SIZE:
                    _insert_workouts(conn, workout_batch)
                    workout_batch.clear()
        elif tag == "ActivitySummary":
            row = _parse_activity_summary(element, import_id)
            if row is not None:
                summary_batch.append(row)
                summary_count += 1
                if len(summary_batch) >= BATCH_SIZE:
                    _insert_activity_summaries(conn, summary_batch)
                    summary_batch.clear()

    if record_batch:
        _insert_records(conn, record_batch)
    if workout_batch:
        _insert_workouts(conn, workout_batch)
    if summary_batch:
        _insert_activity_summaries(conn, summary_batch)

    return ImportStats(
        records=record_count,
        workouts=workout_count,
        activity_summaries=summary_count,
        import_id=import_id,
    )


def _parse_record(element: ET.Element, import_id: int) -> tuple | None:
    record_type = element.get("type")
    start_date = parse_apple_datetime(element.get("startDate"))
    if not record_type or start_date is None:
        return None

    return (
        import_id,
        record_type,
        element.get("unit"),
        parse_float(element.get("value")),
        element.get("sourceName"),
        element.get("sourceVersion"),
        element.get("device"),
        parse_apple_datetime(element.get("creationDate")),
        start_date,
        parse_apple_datetime(element.get("endDate")),
    )


def _parse_workout(element: ET.Element, import_id: int) -> tuple | None:
    activity_type = element.get("workoutActivityType")
    start_date = parse_apple_datetime(element.get("startDate"))
    if not activity_type or start_date is None:
        return None

    return (
        import_id,
        activity_type,
        parse_float(element.get("duration")),
        element.get("durationUnit"),
        parse_float(element.get("totalDistance")),
        element.get("totalDistanceUnit"),
        parse_float(element.get("totalEnergyBurned")),
        element.get("totalEnergyBurnedUnit"),
        element.get("sourceName"),
        element.get("sourceVersion"),
        element.get("device"),
        parse_apple_datetime(element.get("creationDate")),
        start_date,
        parse_apple_datetime(element.get("endDate")),
    )


def _parse_activity_summary(element: ET.Element, import_id: int) -> tuple | None:
    summary_date = parse_apple_date(element.get("dateComponents"))
    if summary_date is None:
        return None

    return (
        import_id,
        summary_date,
        parse_float(element.get("activeEnergyBurned")),
        parse_float(element.get("activeEnergyBurnedGoal")),
        element.get("activeEnergyBurnedUnit"),
        parse_float(element.get("appleMoveTime")),
        parse_float(element.get("appleMoveTimeGoal")),
        parse_float(element.get("appleExerciseTime")),
        parse_float(element.get("appleExerciseTimeGoal")),
        parse_float(element.get("appleStandHours")),
        parse_float(element.get("appleStandHoursGoal")),
    )


def _insert_records(conn: duckdb.DuckDBPyConnection, batch: list[tuple]) -> None:
    conn.executemany(
        """
        INSERT OR IGNORE INTO apple_health_records (
            import_id, type, unit, value, source_name, source_version, device,
            creation_date, start_date, end_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        batch,
    )


def _insert_workouts(conn: duckdb.DuckDBPyConnection, batch: list[tuple]) -> None:
    conn.executemany(
        """
        INSERT OR IGNORE INTO apple_health_workouts (
            import_id, workout_activity_type, duration, duration_unit,
            total_distance, total_distance_unit, total_energy_burned,
            total_energy_burned_unit, source_name, source_version, device,
            creation_date, start_date, end_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        batch,
    )


def _insert_activity_summaries(conn: duckdb.DuckDBPyConnection, batch: list[tuple]) -> None:
    conn.executemany(
        """
        INSERT OR IGNORE INTO apple_health_activity_summaries (
            import_id, summary_date, active_energy_burned, active_energy_burned_goal,
            active_energy_burned_unit, apple_move_time, apple_move_time_goal,
            apple_exercise_time, apple_exercise_time_goal, apple_stand_hours,
            apple_stand_hours_goal
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        batch,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Apple Health export.xml into DuckDB")
    parser.add_argument(
        "export_path",
        type=Path,
        help="Path to export.xml, a folder containing it, or the Apple Health .zip export",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
        help=f"DuckDB file path (default: {DB_PATH})",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing Apple Health rows before importing",
    )
    args = parser.parse_args()

    stats = import_apple_health(args.export_path, args.db, replace=args.replace)
    print(
        "Imported Apple Health data: "
        f"{stats.records} records, "
        f"{stats.workouts} workouts, "
        f"{stats.activity_summaries} activity summaries "
        f"(import_id={stats.import_id})"
    )


if __name__ == "__main__":
    main()
