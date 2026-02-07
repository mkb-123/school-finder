"""Explore Education Statistics (EES) API client.

Fetches school performance, admissions, and absence data from the DfE's
official REST API at api.education.gov.uk/statistics/v1.

API docs: https://api.education.gov.uk/statistics/docs/reference-v1/endpoints/
Data catalogue: https://explore-education-statistics.service.gov.uk/data-catalogue

The API provides CSV downloads for each dataset. This service downloads the
CSV, parses it with Polars, matches records to schools by URN, and inserts
real data into the database.
"""

from __future__ import annotations

import gzip
import logging
from pathlib import Path

import polars as pl
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models import AdmissionsHistory, School, SchoolPerformance
from src.services.gov_data.base import BaseGovDataService

logger = logging.getLogger(__name__)

# Known dataset IDs from the EES data catalogue.
# These may change when new academic years are published; update as needed.
# Find datasets at: https://explore-education-statistics.service.gov.uk/data-catalogue
DATASETS = {
    "ks2": {
        "id": "2ff21cfc-db60-413e-9b02-47dc91d12740",
        "description": "Key stage 2 attainment (SATs)",
    },
    "ks4": {
        "id": "d7ce19cb-916b-45d6-9dc1-3e581e16fa1a",
        "description": "Key stage 4 institution level (GCSEs, Progress 8)",
    },
    "admissions": {
        "id": "",  # To be populated when dataset ID is confirmed
        "description": "School applications and offers",
    },
}


class EESService(BaseGovDataService):
    """Fetch school data from the Explore Education Statistics API.

    Usage::

        service = EESService()
        stats = service.refresh_performance(council="Milton Keynes")
        stats = service.refresh_admissions(council="Milton Keynes")
    """

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        cache_ttl_hours: int = 168,  # 1 week default
    ) -> None:
        settings = get_settings()
        super().__init__(
            cache_dir=cache_dir or Path("./data/cache/ees"),
            cache_ttl_hours=cache_ttl_hours,
        )
        self._api_base = settings.EES_API_BASE
        self._subscription_key = settings.EES_SUBSCRIPTION_KEY

    def _dataset_csv_url(self, dataset_id: str) -> str:
        """Build the CSV download URL for a dataset."""
        return f"{self._api_base}/data-sets/{dataset_id}/csv"

    def download_dataset(
        self,
        dataset_key: str,
        force: bool = False,
    ) -> Path | None:
        """Download a dataset CSV from the EES API.

        Parameters
        ----------
        dataset_key:
            Key from the DATASETS dict (e.g. "ks2", "ks4", "admissions").
        force:
            Bypass cache.

        Returns
        -------
        Path or None
            Path to downloaded CSV, or None if dataset ID is not configured.
        """
        dataset = DATASETS.get(dataset_key)
        if not dataset or not dataset["id"]:
            self._logger.warning("Dataset '%s' has no configured ID; skipping download", dataset_key)
            return None

        dataset_id = dataset["id"]
        url = self._dataset_csv_url(dataset_id)
        filename = f"ees_{dataset_key}.csv.gz"

        return self.download(url, filename=filename, force=force)

    def _read_ees_csv(self, path: Path) -> pl.DataFrame:
        """Read an EES CSV file (may be gzip-compressed)."""
        try:
            return pl.read_csv(
                path,
                encoding="utf8-lossy",
                ignore_errors=True,
                infer_schema_length=10000,
            )
        except Exception:
            # Try reading as gzip
            with gzip.open(path, "rb") as f:
                return pl.read_csv(
                    f,
                    encoding="utf8-lossy",
                    ignore_errors=True,
                    infer_schema_length=10000,
                )

    def _load_urn_map(self, db_path: str, council: str | None = None) -> dict[str, int]:
        """Load a URN -> school_id mapping from the database."""
        engine = create_engine(f"sqlite:///{db_path}")
        with Session(engine) as session:
            query = session.query(School.id, School.urn).filter(School.urn.is_not(None))
            if council:
                query = query.filter(School.council == council)
            return {str(urn): sid for sid, urn in query.all()}

    # ------------------------------------------------------------------
    # KS2 (SATs) performance data
    # ------------------------------------------------------------------

    def refresh_ks2(
        self,
        council: str | None = None,
        force_download: bool = False,
        db_path: str | None = None,
    ) -> dict[str, int]:
        """Download and import KS2 SATs performance data.

        Returns
        -------
        dict
            Statistics: {imported, skipped, not_found}.
        """
        settings = get_settings()
        db = db_path or settings.SQLITE_PATH

        csv_path = self.download_dataset("ks2", force=force_download)
        if csv_path is None:
            return {"imported": 0, "skipped": 0, "not_found": 0, "error": "no_dataset_id"}

        df = self._read_ees_csv(csv_path)
        self._logger.info("KS2 CSV: %d rows, columns: %s", df.height, df.columns[:10])

        urn_map = self._load_urn_map(db, council)
        return self._import_ks2(db, df, urn_map, council)

    def _import_ks2(
        self,
        db_path: str,
        df: pl.DataFrame,
        urn_map: dict[str, int],
        council: str | None,
    ) -> dict[str, int]:
        """Parse KS2 CSV and insert performance records."""
        stats = {"imported": 0, "skipped": 0, "not_found": 0}

        # Find the URN column
        urn_col = self._find_col(df, ["urn", "URN", "Urn", "school_urn"])
        if not urn_col:
            self._logger.error("No URN column found in KS2 data. Columns: %s", df.columns)
            return stats

        # Find performance columns
        # Common EES KS2 column names:
        reading_col = self._find_col(
            df,
            [
                "pt_read_exp",
                "read_expected",
                "reading_expected_standard",
                "Reading % expected standard",
            ],
        )
        maths_col = self._find_col(
            df,
            [
                "pt_mat_exp",
                "maths_expected",
                "maths_expected_standard",
                "Maths % expected standard",
            ],
        )
        writing_col = self._find_col(
            df,
            [
                "pt_writ_exp",
                "writing_expected",
                "writing_expected_standard",
                "Writing % expected standard",
            ],
        )
        rwm_col = self._find_col(
            df,
            [
                "pt_rwm_exp",
                "rwm_expected",
                "reading_writing_maths_expected",
                "Reading, writing and maths % expected standard",
            ],
        )
        year_col = self._find_col(df, ["time_period", "year", "academic_year"])
        self._logger.info(
            "KS2 columns mapped: urn=%s, reading=%s, maths=%s, rwm=%s, year=%s",
            urn_col,
            reading_col,
            maths_col,
            rwm_col,
            year_col,
        )

        engine = create_engine(f"sqlite:///{db_path}")
        with Session(engine) as session:
            for row in df.iter_rows(named=True):
                urn = str(row.get(urn_col, "")).strip()
                school_id = urn_map.get(urn)
                if school_id is None:
                    stats["not_found"] += 1
                    continue

                year = str(row.get(year_col, "")) if year_col else ""

                metrics_added = 0

                # Reading
                if reading_col and row.get(reading_col):
                    val = str(row[reading_col]).strip()
                    if val and val not in ("", "SUPP", "NE", "NA", "x"):
                        session.add(
                            SchoolPerformance(
                                school_id=school_id,
                                metric_type="SATs_Reading",
                                metric_value=f"Expected standard: {val}%",
                                year=year,
                                source_url="https://explore-education-statistics.service.gov.uk/",
                            )
                        )
                        metrics_added += 1

                # Maths
                if maths_col and row.get(maths_col):
                    val = str(row[maths_col]).strip()
                    if val and val not in ("", "SUPP", "NE", "NA", "x"):
                        session.add(
                            SchoolPerformance(
                                school_id=school_id,
                                metric_type="SATs_Maths",
                                metric_value=f"Expected standard: {val}%",
                                year=year,
                                source_url="https://explore-education-statistics.service.gov.uk/",
                            )
                        )
                        metrics_added += 1

                # Writing
                if writing_col and row.get(writing_col):
                    val = str(row[writing_col]).strip()
                    if val and val not in ("", "SUPP", "NE", "NA", "x"):
                        session.add(
                            SchoolPerformance(
                                school_id=school_id,
                                metric_type="SATs_Writing",
                                metric_value=f"Expected standard: {val}%",
                                year=year,
                                source_url="https://explore-education-statistics.service.gov.uk/",
                            )
                        )
                        metrics_added += 1

                # Combined RWM
                if rwm_col and row.get(rwm_col):
                    val = str(row[rwm_col]).strip()
                    if val and val not in ("", "SUPP", "NE", "NA", "x"):
                        session.add(
                            SchoolPerformance(
                                school_id=school_id,
                                metric_type="SATs",
                                metric_value=f"Expected standard: {val}%",
                                year=year,
                                source_url="https://explore-education-statistics.service.gov.uk/",
                            )
                        )
                        metrics_added += 1

                if metrics_added > 0:
                    stats["imported"] += metrics_added
                else:
                    stats["skipped"] += 1

            session.commit()

        self._logger.info("KS2 import: %s", stats)
        return stats

    # ------------------------------------------------------------------
    # KS4 (GCSE / Progress 8) performance data
    # ------------------------------------------------------------------

    def refresh_ks4(
        self,
        council: str | None = None,
        force_download: bool = False,
        db_path: str | None = None,
    ) -> dict[str, int]:
        """Download and import KS4 GCSE and Progress 8 data.

        Returns
        -------
        dict
            Statistics: {imported, skipped, not_found}.
        """
        settings = get_settings()
        db = db_path or settings.SQLITE_PATH

        csv_path = self.download_dataset("ks4", force=force_download)
        if csv_path is None:
            return {"imported": 0, "skipped": 0, "not_found": 0, "error": "no_dataset_id"}

        df = self._read_ees_csv(csv_path)
        self._logger.info("KS4 CSV: %d rows, columns: %s", df.height, df.columns[:10])

        urn_map = self._load_urn_map(db, council)
        return self._import_ks4(db, df, urn_map, council)

    def _import_ks4(
        self,
        db_path: str,
        df: pl.DataFrame,
        urn_map: dict[str, int],
        council: str | None,
    ) -> dict[str, int]:
        """Parse KS4 CSV and insert performance records."""
        stats = {"imported": 0, "skipped": 0, "not_found": 0}

        urn_col = self._find_col(df, ["urn", "URN", "Urn", "school_urn"])
        if not urn_col:
            self._logger.error("No URN column found in KS4 data. Columns: %s", df.columns)
            return stats

        # Common EES KS4 column names:
        p8_col = self._find_col(
            df,
            [
                "p8score",
                "progress_8_score",
                "Progress 8 score",
                "p8_score",
                "progress8",
            ],
        )
        a8_col = self._find_col(
            df,
            [
                "att8score",
                "attainment_8_score",
                "Attainment 8 score",
                "a8_score",
                "attainment8",
            ],
        )
        gcse_col = self._find_col(
            df,
            [
                "ptl2basics_94",
                "basics_9to4",
                "English and maths 9-4",
                "percentage_9_to_4_english_and_maths",
            ],
        )
        year_col = self._find_col(df, ["time_period", "year", "academic_year"])

        self._logger.info(
            "KS4 columns mapped: urn=%s, p8=%s, a8=%s, gcse=%s, year=%s",
            urn_col,
            p8_col,
            a8_col,
            gcse_col,
            year_col,
        )

        engine = create_engine(f"sqlite:///{db_path}")
        with Session(engine) as session:
            for row in df.iter_rows(named=True):
                urn = str(row.get(urn_col, "")).strip()
                school_id = urn_map.get(urn)
                if school_id is None:
                    stats["not_found"] += 1
                    continue

                year = str(row.get(year_col, "")) if year_col else ""
                metrics_added = 0

                # Progress 8
                if p8_col and row.get(p8_col):
                    val = str(row[p8_col]).strip()
                    if val and val not in ("", "SUPP", "NE", "NA", "x", "null"):
                        try:
                            p8_num = float(val)
                            session.add(
                                SchoolPerformance(
                                    school_id=school_id,
                                    metric_type="Progress8",
                                    metric_value=f"{p8_num:+.2f}",
                                    year=year,
                                    source_url="https://explore-education-statistics.service.gov.uk/",
                                )
                            )
                            metrics_added += 1
                        except ValueError:
                            pass

                # Attainment 8
                if a8_col and row.get(a8_col):
                    val = str(row[a8_col]).strip()
                    if val and val not in ("", "SUPP", "NE", "NA", "x", "null"):
                        try:
                            float(val)  # validate numeric
                            session.add(
                                SchoolPerformance(
                                    school_id=school_id,
                                    metric_type="Attainment8",
                                    metric_value=val,
                                    year=year,
                                    source_url="https://explore-education-statistics.service.gov.uk/",
                                )
                            )
                            metrics_added += 1
                        except ValueError:
                            pass

                # GCSE basics (English & Maths 9-4)
                if gcse_col and row.get(gcse_col):
                    val = str(row[gcse_col]).strip()
                    if val and val not in ("", "SUPP", "NE", "NA", "x", "null"):
                        session.add(
                            SchoolPerformance(
                                school_id=school_id,
                                metric_type="GCSE",
                                metric_value=f"English & Maths 9-4: {val}%",
                                year=year,
                                source_url="https://explore-education-statistics.service.gov.uk/",
                            )
                        )
                        metrics_added += 1

                if metrics_added > 0:
                    stats["imported"] += metrics_added
                else:
                    stats["skipped"] += 1

            session.commit()

        self._logger.info("KS4 import: %s", stats)
        return stats

    # ------------------------------------------------------------------
    # Admissions data
    # ------------------------------------------------------------------

    def refresh_admissions(
        self,
        council: str | None = None,
        force_download: bool = False,
        db_path: str | None = None,
    ) -> dict[str, int]:
        """Download and import school admissions data.

        Returns statistics or an error if the dataset ID is not yet configured.
        The admissions dataset ID must be found in the EES data catalogue and
        added to the DATASETS dict.

        Returns
        -------
        dict
            Statistics: {imported, skipped, not_found} or {error}.
        """
        settings = get_settings()
        db = db_path or settings.SQLITE_PATH

        csv_path = self.download_dataset("admissions", force=force_download)
        if csv_path is None:
            self._logger.warning(
                "Admissions dataset ID not configured. "
                "Find it at: https://explore-education-statistics.service.gov.uk/data-catalogue "
                "and add it to DATASETS['admissions']['id'] in ees.py"
            )
            return {"imported": 0, "error": "no_dataset_id"}

        df = self._read_ees_csv(csv_path)
        self._logger.info("Admissions CSV: %d rows", df.height)

        urn_map = self._load_urn_map(db, council)
        return self._import_admissions(db, df, urn_map)

    def _import_admissions(
        self,
        db_path: str,
        df: pl.DataFrame,
        urn_map: dict[str, int],
    ) -> dict[str, int]:
        """Parse admissions CSV and insert records."""
        stats = {"imported": 0, "skipped": 0, "not_found": 0}

        urn_col = self._find_col(df, ["urn", "URN", "Urn", "school_urn"])
        if not urn_col:
            self._logger.error("No URN column in admissions data")
            return stats

        year_col = self._find_col(df, ["time_period", "year", "academic_year"])
        offers_col = self._find_col(
            df,
            [
                "total_offers",
                "offers_made",
                "number_of_offers",
                "places_offered",
                "total_number_of_offers",
            ],
        )
        apps_col = self._find_col(
            df,
            [
                "total_preferences",
                "applications",
                "total_applications",
                "first_preferences",
                "number_of_1st_preferences",
            ],
        )

        engine = create_engine(f"sqlite:///{db_path}")
        with Session(engine) as session:
            for row in df.iter_rows(named=True):
                urn = str(row.get(urn_col, "")).strip()
                school_id = urn_map.get(urn)
                if school_id is None:
                    stats["not_found"] += 1
                    continue

                year = str(row.get(year_col, "")) if year_col else ""
                places = self._safe_int(row.get(offers_col)) if offers_col else None
                apps = self._safe_int(row.get(apps_col)) if apps_col else None

                if places is None and apps is None:
                    stats["skipped"] += 1
                    continue

                session.add(
                    AdmissionsHistory(
                        school_id=school_id,
                        academic_year=year,
                        places_offered=places,
                        applications_received=apps,
                        last_distance_offered_km=None,  # Not in this dataset
                        waiting_list_offers=None,
                        appeals_heard=None,
                        appeals_upheld=None,
                    )
                )
                stats["imported"] += 1

            session.commit()

        self._logger.info("Admissions import: %s", stats)
        return stats

    # ------------------------------------------------------------------
    # Combined refresh
    # ------------------------------------------------------------------

    def refresh_performance(
        self,
        council: str | None = None,
        force_download: bool = False,
        db_path: str | None = None,
    ) -> dict[str, dict[str, int]]:
        """Refresh both KS2 and KS4 performance data.

        Returns
        -------
        dict
            Nested statistics: {ks2: {...}, ks4: {...}}.
        """
        ks2_stats = self.refresh_ks2(council=council, force_download=force_download, db_path=db_path)
        ks4_stats = self.refresh_ks4(council=council, force_download=force_download, db_path=db_path)
        return {"ks2": ks2_stats, "ks4": ks4_stats}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_col(df: pl.DataFrame, candidates: list[str]) -> str | None:
        """Find the first matching column name from candidates."""
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
        # Also try case-insensitive matching
        col_lower = {c.lower(): c for c in df.columns}
        for candidate in candidates:
            if candidate.lower() in col_lower:
                return col_lower[candidate.lower()]
        return None

    @staticmethod
    def _safe_int(value: object) -> int | None:
        """Convert a value to int, returning None on failure."""
        if value is None:
            return None
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return None
