"""Import Apple Health export data."""

from __future__ import annotations

import argparse
import logging
import time
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import BinaryIO, TextIO

import duckdb

from importers.db import bulk_insert_ignore, connect, init_schema, start_import
from importers.paths import DB_PATH

logger = logging.getLogger(__name__)

BATCH_SIZE = 50_000
PARSE_LOG_INTERVAL = 100_000

RECORD_COLUMNS = [
    "import_id",
    "type",
    "unit",
    "value",
    "value_text",
    "source_name",
    "source_version",
    "device",
    "creation_date",
    "start_date",
    "end_date",
]

WORKOUT_COLUMNS = [
    "import_id",
    "workout_activity_type",
    "duration",
    "duration_unit",
    "total_distance",
    "total_distance_unit",
    "total_energy_burned",
    "total_energy_burned_unit",
    "source_name",
    "source_version",
    "device",
    "creation_date",
    "start_date",
    "end_date",
]

ACTIVITY_SUMMARY_COLUMNS = [
    "import_id",
    "summary_date",
    "active_energy_burned",
    "active_energy_burned_goal",
    "active_energy_burned_unit",
    "apple_move_time",
    "apple_move_time_goal",
    "apple_exercise_time",
    "apple_exercise_time_goal",
    "apple_stand_hours",
    "apple_stand_hours_goal",
]

NUTRITION_COLUMNS = [
    "import_id",
    "source_name",
    "source_version",
    "creation_date",
    "start_date",
    "end_date",
    "carbohydrates",
    "carbohydrates_unit",
    "fibre",
    "fibre_unit",
    "protein",
    "protein_unit",
    "sodium",
    "sodium_unit",
    "total_fat",
    "total_fat_unit",
]

NUTRITION_TYPE_MAP: dict[str, tuple[str, str]] = {
    "HKQuantityTypeIdentifierDietaryCarbohydrates": ("carbohydrates", "carbohydrates_unit"),
    "HKQuantityTypeIdentifierDietaryFiber": ("fibre", "fibre_unit"),
    "HKQuantityTypeIdentifierDietaryProtein": ("protein", "protein_unit"),
    "HKQuantityTypeIdentifierDietarySodium": ("sodium", "sodium_unit"),
    "HKQuantityTypeIdentifierDietaryFatTotal": ("total_fat", "total_fat_unit"),
}


@dataclass
class NutritionEntry:
    import_id: int
    source_name: str | None = None
    source_version: str | None = None
    creation_date: datetime | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    carbohydrates: float | None = None
    carbohydrates_unit: str | None = None
    fibre: float | None = None
    fibre_unit: str | None = None
    protein: float | None = None
    protein_unit: str | None = None
    sodium: float | None = None
    sodium_unit: str | None = None
    total_fat: float | None = None
    total_fat_unit: str | None = None


@dataclass(frozen=True)
class ImportStats:
    records: int
    workouts: int
    activity_summaries: int
    nutrition: int
    import_id: int
    elapsed_seconds: float


def configure_logging(*, verbose: bool = False) -> None:
    root = logging.getLogger("importers")
    if root.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    )
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)


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


def parse_record_value(value: str | None) -> tuple[float | None, str | None]:
    """Return numeric and text values for quantity vs category records."""
    if value is None or value == "":
        return None, None
    try:
        return float(value), None
    except ValueError:
        return None, value


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _open_export_xml(export_path: Path) -> tuple[BinaryIO | TextIO, None]:
    if export_path.is_dir():
        for candidate in (
            export_path / "export.xml",
            export_path / "apple_health_export" / "export.xml",
        ):
            if candidate.exists():
                logger.info("Reading XML file %s", candidate)
                return candidate.open("rb"), None
        msg = f"No export.xml found under {export_path}"
        raise FileNotFoundError(msg)

    if export_path.name == "export.xml" or export_path.suffix.lower() == ".xml":
        logger.info("Reading XML file %s", export_path)
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
    logger.info("Clearing existing Apple Health tables")
    conn.execute("DELETE FROM apple_health_records")
    conn.execute("DELETE FROM apple_health_workouts")
    conn.execute("DELETE FROM apple_health_activity_summaries")
    conn.execute("DELETE FROM apple_nutrition")
    conn.execute("DELETE FROM imports WHERE source = 'apple_health'")


def import_apple_health(
    export_path: Path,
    db_path: Path = DB_PATH,
    *,
    replace: bool = False,
    log: bool = False,
    verbose: bool = False,
) -> ImportStats:
    """Load Apple Health export XML into DuckDB."""
    if log:
        configure_logging(verbose=verbose)

    export_path = export_path.expanduser().resolve()
    db_path = db_path.expanduser().resolve()
    started = time.perf_counter()

    logger.info("Import starting: export=%s db=%s replace=%s", export_path, db_path, replace)

    conn = connect(db_path)
    try:
        init_schema(conn)
        if replace:
            clear_apple_health_tables(conn)

        import_id = start_import(conn, "apple_health", export_path)

        if export_path.suffix.lower() == ".zip":
            with zipfile.ZipFile(export_path) as archive:
                xml_name = _find_export_xml_in_zip(archive)
                logger.info("Reading %s from zip %s", xml_name, export_path)
                with archive.open(xml_name) as stream:
                    stats = _load_elements(conn, stream, import_id)
        else:
            stream, _ = _open_export_xml(export_path)
            try:
                stats = _load_elements(conn, stream, import_id)
            finally:
                stream.close()

        elapsed = time.perf_counter() - started
        logger.info(
            "Import finished in %.1fs: %s records, %s workouts, "
            "%s activity summaries, %s nutrition entries (import_id=%s)",
            elapsed,
            f"{stats.records:,}",
            f"{stats.workouts:,}",
            f"{stats.activity_summaries:,}",
            f"{stats.nutrition:,}",
            stats.import_id,
        )
        return ImportStats(
            records=stats.records,
            workouts=stats.workouts,
            activity_summaries=stats.activity_summaries,
            nutrition=stats.nutrition,
            import_id=stats.import_id,
            elapsed_seconds=elapsed,
        )
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
    nutrition_pending: dict[tuple, NutritionEntry] = {}

    record_count = 0
    workout_count = 0
    summary_count = 0
    nutrition_count = 0
    elements_seen = 0
    last_progress_log = time.perf_counter()

    logger.info("Parsing export.xml (batch size %s)", f"{BATCH_SIZE:,}")

    for tag, element in iter_health_elements(stream):
        elements_seen += 1

        if tag == "Record":
            record_type = element.get("type")
            if record_type in NUTRITION_TYPE_MAP:
                if _merge_nutrition_record(element, import_id, nutrition_pending):
                    if len(nutrition_pending) >= BATCH_SIZE:
                        nutrition_count += _flush_nutrition(
                            conn, nutrition_pending, record_count, workout_count
                        )
                continue

            row = _parse_record(element, import_id)
            if row is not None:
                record_batch.append(row)
                record_count += 1
                if len(record_batch) >= BATCH_SIZE:
                    _insert_records(conn, record_batch, record_count, workout_count)
                    record_batch.clear()
        elif tag == "Workout":
            row = _parse_workout(element, import_id)
            if row is not None:
                workout_batch.append(row)
                workout_count += 1
                if len(workout_batch) >= BATCH_SIZE:
                    _insert_workouts(conn, workout_batch, record_count, workout_count)
                    workout_batch.clear()
        elif tag == "ActivitySummary":
            row = _parse_activity_summary(element, import_id)
            if row is not None:
                summary_batch.append(row)
                summary_count += 1
                if len(summary_batch) >= BATCH_SIZE:
                    _insert_activity_summaries(conn, summary_batch)
                    summary_batch.clear()

        if elements_seen % PARSE_LOG_INTERVAL == 0:
            _log_parse_progress(
                elements_seen,
                record_count,
                workout_count,
                summary_count,
                nutrition_count,
                last_progress_log,
            )
            last_progress_log = time.perf_counter()

    if record_batch:
        _insert_records(conn, record_batch, record_count, workout_count)
    if workout_batch:
        _insert_workouts(conn, workout_batch, record_count, workout_count)
    if summary_batch:
        _insert_activity_summaries(conn, summary_batch)
    if nutrition_pending:
        nutrition_count += _flush_nutrition(
            conn, nutrition_pending, record_count, workout_count
        )

    logger.info(
        "Parsing complete: %s elements, %s records, %s workouts, "
        "%s activity summaries, %s nutrition entries",
        f"{elements_seen:,}",
        f"{record_count:,}",
        f"{workout_count:,}",
        f"{summary_count:,}",
        f"{nutrition_count:,}",
    )

    return ImportStats(
        records=record_count,
        workouts=workout_count,
        activity_summaries=summary_count,
        nutrition=nutrition_count,
        import_id=import_id,
        elapsed_seconds=0.0,
    )


def _log_parse_progress(
    elements_seen: int,
    record_count: int,
    workout_count: int,
    summary_count: int,
    nutrition_count: int,
    last_log_started: float,
) -> None:
    elapsed = time.perf_counter() - last_log_started
    logger.info(
        "Parse progress: %s elements in last %.1fs | "
        "totals: records=%s workouts=%s summaries=%s nutrition=%s",
        f"{PARSE_LOG_INTERVAL:,}",
        elapsed,
        f"{record_count:,}",
        f"{workout_count:,}",
        f"{summary_count:,}",
        f"{nutrition_count:,}",
    )


def _merge_nutrition_record(
    element: ET.Element,
    import_id: int,
    pending: dict[tuple, NutritionEntry],
) -> bool:
    record_type = element.get("type")
    if record_type not in NUTRITION_TYPE_MAP:
        return False

    start_date = parse_apple_datetime(element.get("startDate"))
    if start_date is None:
        return False

    end_date = parse_apple_datetime(element.get("endDate"))
    source_name = element.get("sourceName")
    key = (start_date, end_date, source_name)

    entry = pending.get(key)
    if entry is None:
        entry = NutritionEntry(
            import_id=import_id,
            source_name=source_name,
            source_version=element.get("sourceVersion"),
            creation_date=parse_apple_datetime(element.get("creationDate")),
            start_date=start_date,
            end_date=end_date,
        )
        pending[key] = entry

    value_field, unit_field = NUTRITION_TYPE_MAP[record_type]
    setattr(entry, value_field, parse_float(element.get("value")))
    setattr(entry, unit_field, element.get("unit"))
    return True


def _nutrition_to_tuple(entry: NutritionEntry) -> tuple:
    return (
        entry.import_id,
        entry.source_name,
        entry.source_version,
        entry.creation_date,
        entry.start_date,
        entry.end_date,
        entry.carbohydrates,
        entry.carbohydrates_unit,
        entry.fibre,
        entry.fibre_unit,
        entry.protein,
        entry.protein_unit,
        entry.sodium,
        entry.sodium_unit,
        entry.total_fat,
        entry.total_fat_unit,
    )


def _parse_record(element: ET.Element, import_id: int) -> tuple | None:
    record_type = element.get("type")
    start_date = parse_apple_datetime(element.get("startDate"))
    if not record_type or start_date is None:
        return None

    numeric_value, text_value = parse_record_value(element.get("value"))

    return (
        import_id,
        record_type,
        element.get("unit"),
        numeric_value,
        text_value,
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


def _insert_records(
    conn: duckdb.DuckDBPyConnection,
    batch: list[tuple],
    total_records: int,
    total_workouts: int,
) -> None:
    bulk_insert_ignore(
        conn,
        "apple_health_records",
        RECORD_COLUMNS,
        batch,
        dedup_columns=[
            "type",
            "start_date",
            "end_date",
            "value",
            "value_text",
            "source_name",
        ],
    )
    logger.info(
        "Progress after records write: parsed records=%s workouts=%s",
        f"{total_records:,}",
        f"{total_workouts:,}",
    )


def _insert_workouts(
    conn: duckdb.DuckDBPyConnection,
    batch: list[tuple],
    total_records: int,
    total_workouts: int,
) -> None:
    bulk_insert_ignore(
        conn,
        "apple_health_workouts",
        WORKOUT_COLUMNS,
        batch,
        dedup_columns=["workout_activity_type", "start_date", "end_date", "source_name"],
    )
    logger.info(
        "Progress after workouts write: parsed records=%s workouts=%s",
        f"{total_records:,}",
        f"{total_workouts:,}",
    )


def _insert_activity_summaries(conn: duckdb.DuckDBPyConnection, batch: list[tuple]) -> None:
    bulk_insert_ignore(
        conn,
        "apple_health_activity_summaries",
        ACTIVITY_SUMMARY_COLUMNS,
        batch,
        dedup_columns=["summary_date"],
    )


def _flush_nutrition(
    conn: duckdb.DuckDBPyConnection,
    pending: dict[tuple, NutritionEntry],
    total_records: int,
    total_workouts: int,
) -> int:
    entries = list(pending.values())
    pending.clear()
    _insert_nutrition(conn, entries, total_records, total_workouts)
    return len(entries)


def _insert_nutrition(
    conn: duckdb.DuckDBPyConnection,
    entries: Iterable[NutritionEntry],
    total_records: int,
    total_workouts: int,
) -> None:
    batch = [_nutrition_to_tuple(entry) for entry in entries]
    if not batch:
        return

    bulk_insert_ignore(
        conn,
        "apple_nutrition",
        NUTRITION_COLUMNS,
        batch,
        dedup_columns=["start_date", "end_date", "source_name"],
    )
    logger.info(
        "Progress after nutrition write: parsed records=%s workouts=%s nutrition=%s",
        f"{total_records:,}",
        f"{total_workouts:,}",
        f"{len(batch):,}",
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
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    stats = import_apple_health(
        args.export_path,
        args.db,
        replace=args.replace,
        log=True,
        verbose=args.verbose,
    )
    print(
        "Imported Apple Health data: "
        f"{stats.records:,} records, "
        f"{stats.workouts:,} workouts, "
        f"{stats.activity_summaries:,} activity summaries, "
        f"{stats.nutrition:,} nutrition entries "
        f"(import_id={stats.import_id}, {stats.elapsed_seconds:.1f}s)"
    )


if __name__ == "__main__":
    main()
