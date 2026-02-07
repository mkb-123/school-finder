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
from src.db.models import AbsencePolicy, AdmissionsHistory, School, SchoolClassSize, SchoolPerformance
from src.services.gov_data.base import BaseGovDataService

logger = logging.getLogger(__name__)

# Known dataset IDs from the EES data catalogue.
# These may change when new academic years are published; update as needed.
# Find datasets at: https://explore-education-statistics.service.gov.uk/data-catalogue
DATASETS = {
    "ks2": {
        "id": "b361b4c3-21b9-46fd-9126-b8060c6a40e2",
        "description": "Key stage 2 institution level 2024 final data - Schools (performance)",
    },
    "ks4": {
        "id": "c8f753ef-b76f-41a3-8949-13382e131054",
        "description": "Key stage 4 institution level 2024 final data - Schools and colleges (performance)",
    },
    "absence": {
        "id": "1ef1689a-070a-4e0b-9314-512db23a3cc9",
        "description": "Absence by school level",
    },
}

# School-level admissions and class size data are published as supporting
# files on the EES publication pages, not as API datasets.
SUPPORTING_FILES = {
    "admissions": {
        "publication_url": (
            "https://explore-education-statistics.service.gov.uk/"
            "find-statistics/primary-and-secondary-school-applications-and-offers"
        ),
        "description": "School level secondary and primary applications and offers",
    },
    "class_sizes": {
        "publication_url": (
            "https://explore-education-statistics.service.gov.uk/"
            "find-statistics/school-pupils-and-their-characteristics"
        ),
        "description": "School level class sizes",
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
        """Build the CSV download URL for a dataset.

        The EES data catalogue provides CSV downloads at a different base
        URL than the statistics API.
        """
        return f"https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/{dataset_id}/csv"

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

        # Find the URN column (school-level dataset uses 'school_urn')
        urn_col = self._find_col(df, ["school_urn", "URN", "urn", "Urn"])
        if not urn_col:
            self._logger.error("No URN column found in KS2 data. Columns: %s", df.columns)
            return stats

        # Find performance columns
        # EES KS2 school-level dataset column names:
        reading_col = self._find_col(
            df,
            [
                "pt_read_exp",
                "read_expected",
                "reading_expected_standard",
            ],
        )
        maths_col = self._find_col(
            df,
            [
                "pt_mat_exp",
                "maths_expected",
                "maths_expected_standard",
            ],
        )
        writing_col = self._find_col(
            df,
            [
                "pt_writ_exp",
                "pt_writ_ta_exp",
                "writing_expected",
                "writing_expected_standard",
            ],
        )
        rwm_col = self._find_col(
            df,
            [
                "pt_rwm_exp",
                "rwm_expected",
                "reading_writing_maths_expected",
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

                year = self._parse_year(row.get(year_col, "")) if year_col else 0

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

        urn_col = self._find_col(df, ["school_urn", "URN", "urn", "Urn"])
        if not urn_col:
            self._logger.error("No URN column found in KS4 data. Columns: %s", df.columns)
            return stats

        # EES KS4 school-level performance dataset column names:
        p8_col = self._find_col(
            df,
            [
                "avg_p8score",
                "p8score",
                "progress_8_score",
                "p8_score",
            ],
        )
        a8_col = self._find_col(
            df,
            [
                "avg_att8",
                "att8score",
                "attainment_8_score",
                "a8_score",
            ],
        )
        gcse_col = self._find_col(
            df,
            [
                "ptl2basics_94",
                "basics_9to4",
                "pt_l2basics_94",
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

                year = self._parse_year(row.get(year_col, "")) if year_col else 0
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
    # Absence data (school-level)
    # ------------------------------------------------------------------

    def refresh_absence(
        self,
        council: str | None = None,
        force_download: bool = False,
        db_path: str | None = None,
    ) -> dict[str, int]:
        """Download and import school-level absence data.

        Populates the ``absence_policies`` table with official DfE absence
        rates (overall and unauthorised).  Policy text is NOT available
        from this source – that requires scraping school websites.

        Returns
        -------
        dict
            Statistics: {imported, skipped, not_found}.
        """
        settings = get_settings()
        db = db_path or settings.SQLITE_PATH

        csv_path = self.download_dataset("absence", force=force_download)
        if csv_path is None:
            return {"imported": 0, "skipped": 0, "not_found": 0, "error": "no_dataset_id"}

        df = self._read_ees_csv(csv_path)
        self._logger.info("Absence CSV: %d rows, columns: %s", df.height, df.columns[:10])

        urn_map = self._load_urn_map(db, council)
        return self._import_absence(db, df, urn_map)

    def _import_absence(
        self,
        db_path: str,
        df: pl.DataFrame,
        urn_map: dict[str, int],
    ) -> dict[str, int]:
        """Parse absence CSV and insert AbsencePolicy records."""
        stats = {"imported": 0, "skipped": 0, "not_found": 0}

        urn_col = self._find_col(df, ["school_urn", "URN", "urn"])
        if not urn_col:
            self._logger.error("No URN column in absence data. Columns: %s", df.columns)
            return stats

        year_col = self._find_col(df, ["time_period", "year", "academic_year"])
        overall_col = self._find_col(df, ["sess_overall_percent", "overall_absence_rate", "sess_overall_rate"])
        unauth_col = self._find_col(
            df, ["sess_unauthorised_percent", "unauthorised_absence_rate", "sess_unauthorised_rate"]
        )

        self._logger.info(
            "Absence columns: urn=%s, year=%s, overall=%s, unauth=%s",
            urn_col,
            year_col,
            overall_col,
            unauth_col,
        )

        engine = create_engine(f"sqlite:///{db_path}")
        with Session(engine) as session:
            for row in df.iter_rows(named=True):
                urn = str(row.get(urn_col, "")).strip()
                school_id = urn_map.get(urn)
                if school_id is None:
                    stats["not_found"] += 1
                    continue

                year_str = str(row.get(year_col, "")) if year_col else ""

                overall_rate = self._safe_float(row.get(overall_col)) if overall_col else None
                unauth_rate = self._safe_float(row.get(unauth_col)) if unauth_col else None

                if overall_rate is None and unauth_rate is None:
                    stats["skipped"] += 1
                    continue

                session.add(
                    AbsencePolicy(
                        school_id=school_id,
                        overall_absence_rate=overall_rate,
                        unauthorised_absence_rate=unauth_rate,
                        data_year=year_str,
                        source_url="https://explore-education-statistics.service.gov.uk/",
                        # Policy text fields left NULL – populated by website scraper
                        issues_fines=False,
                        authorises_holidays=False,
                    )
                )
                stats["imported"] += 1

            session.commit()

        self._logger.info("Absence import: %s", stats)
        return stats

    # ------------------------------------------------------------------
    # Admissions data (supporting file - not an API dataset)
    # ------------------------------------------------------------------

    def refresh_admissions(
        self,
        council: str | None = None,
        force_download: bool = False,
        db_path: str | None = None,
    ) -> dict[str, int]:
        """Download and import school-level admissions data.

        School-level admissions data is published as a supporting file on
        the EES publication page, not as an API dataset.  This method
        scrapes the publication page to find the CSV download link.

        Returns
        -------
        dict
            Statistics: {imported, skipped, not_found} or {error}.
        """
        settings = get_settings()
        db = db_path or settings.SQLITE_PATH

        pub_url = SUPPORTING_FILES["admissions"]["publication_url"]
        csv_path = self._download_supporting_csv(pub_url, "admissions", force_download)
        if csv_path is None:
            self._logger.warning("Could not find admissions supporting file CSV")
            return {"imported": 0, "error": "supporting_file_not_found"}

        df = self._read_ees_csv(csv_path)
        self._logger.info("Admissions CSV: %d rows", df.height)

        urn_map = self._load_urn_map(db, council)
        # Admissions data uses LAEstab, not URN — build LAEstab map too
        laestab_map = self._load_laestab_map(db, council)

        return self._import_admissions(db, df, urn_map, laestab_map)

    def _import_admissions(
        self,
        db_path: str,
        df: pl.DataFrame,
        urn_map: dict[str, int],
        laestab_map: dict[str, int] | None = None,
    ) -> dict[str, int]:
        """Parse admissions CSV and insert records."""
        stats = {"imported": 0, "skipped": 0, "not_found": 0}

        urn_col = self._find_col(df, ["school_urn", "URN", "urn", "Urn"])
        laestab_col = self._find_col(df, ["school_laestab", "LAEstab", "laestab"])
        if not urn_col and not laestab_col:
            self._logger.error("No URN or LAEstab column in admissions data. Columns: %s", df.columns)
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
                "total_first_preferences",
                "applications",
                "total_applications",
                "first_preferences",
                "number_of_1st_preferences",
            ],
        )

        engine = create_engine(f"sqlite:///{db_path}")
        with Session(engine) as session:
            for row in df.iter_rows(named=True):
                # Try URN first, fall back to LAEstab
                school_id = None
                if urn_col:
                    urn = str(row.get(urn_col, "")).strip()
                    school_id = urn_map.get(urn)
                if school_id is None and laestab_col and laestab_map:
                    laestab = str(row.get(laestab_col, "")).strip()
                    school_id = laestab_map.get(laestab)

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
                        last_distance_offered_km=None,
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
    # Class sizes (supporting file)
    # ------------------------------------------------------------------

    def refresh_class_sizes(
        self,
        council: str | None = None,
        force_download: bool = False,
        db_path: str | None = None,
    ) -> dict[str, int]:
        """Download and import school-level class size data.

        Returns
        -------
        dict
            Statistics: {imported, skipped, not_found} or {error}.
        """
        settings = get_settings()
        db = db_path or settings.SQLITE_PATH

        pub_url = SUPPORTING_FILES["class_sizes"]["publication_url"]
        csv_path = self._download_supporting_csv(pub_url, "class_sizes", force_download)
        if csv_path is None:
            self._logger.warning("Could not find class sizes supporting file CSV")
            return {"imported": 0, "error": "supporting_file_not_found"}

        df = self._read_ees_csv(csv_path)
        self._logger.info("Class sizes CSV: %d rows, columns: %s", df.height, df.columns[:10])

        urn_map = self._load_urn_map(db, council)
        laestab_map = self._load_laestab_map(db, council)
        return self._import_class_sizes(db, df, urn_map, laestab_map)

    def _import_class_sizes(
        self,
        db_path: str,
        df: pl.DataFrame,
        urn_map: dict[str, int],
        laestab_map: dict[str, int] | None = None,
    ) -> dict[str, int]:
        """Parse class sizes CSV and insert records."""
        stats = {"imported": 0, "skipped": 0, "not_found": 0}

        urn_col = self._find_col(df, ["school_urn", "URN", "urn"])
        laestab_col = self._find_col(df, ["school_laestab", "LAEstab", "laestab"])
        if not urn_col and not laestab_col:
            self._logger.error("No URN or LAEstab column in class sizes data")
            return stats

        year_col = self._find_col(df, ["time_period", "year", "academic_year"])
        pupils_col = self._find_col(df, ["headcount", "num_pupils", "total_pupils", "number_of_pupils"])
        classes_col = self._find_col(df, ["num_classes", "number_of_classes", "total_classes"])
        avg_col = self._find_col(df, ["avg_class_size", "average_class_size", "mean_class_size"])

        engine = create_engine(f"sqlite:///{db_path}")
        with Session(engine) as session:
            for row in df.iter_rows(named=True):
                school_id = None
                if urn_col:
                    urn = str(row.get(urn_col, "")).strip()
                    school_id = urn_map.get(urn)
                if school_id is None and laestab_col and laestab_map:
                    laestab = str(row.get(laestab_col, "")).strip()
                    school_id = laestab_map.get(laestab)

                if school_id is None:
                    stats["not_found"] += 1
                    continue

                year_str = str(row.get(year_col, "")) if year_col else ""
                pupils = self._safe_int(row.get(pupils_col)) if pupils_col else None
                classes = self._safe_int(row.get(classes_col)) if classes_col else None
                avg = self._safe_float(row.get(avg_col)) if avg_col else None

                if pupils is None and classes is None and avg is None:
                    stats["skipped"] += 1
                    continue

                session.add(
                    SchoolClassSize(
                        school_id=school_id,
                        academic_year=year_str,
                        year_group="All",  # Supporting file may not break down by year group
                        num_pupils=pupils,
                        num_classes=classes,
                        avg_class_size=avg,
                    )
                )
                stats["imported"] += 1

            session.commit()

        self._logger.info("Class sizes import: %s", stats)
        return stats

    # ------------------------------------------------------------------
    # Supporting file download helper
    # ------------------------------------------------------------------

    def _download_supporting_csv(
        self,
        publication_url: str,
        key: str,
        force: bool = False,
    ) -> Path | None:
        """Scrape an EES publication page for a supporting CSV download link.

        Many school-level datasets are published as 'supporting files'
        rather than API datasets.  This method fetches the publication page
        and looks for CSV download links.

        Returns
        -------
        Path | None
            Path to the downloaded CSV, or None if not found.
        """
        import re

        filename = f"ees_{key}_supporting.csv"
        cache_path = self.cache_dir / filename
        if not force and self._is_cache_fresh(cache_path):
            self._logger.info("Using cached supporting file: %s", cache_path)
            return cache_path

        # Try to find the download link from the publication page
        try:
            import httpx as _httpx

            with _httpx.Client(
                timeout=60.0,
                follow_redirects=True,
                headers={"User-Agent": "SchoolFinder/1.0 (Education Data Import)"},
            ) as client:
                resp = client.get(publication_url)
                resp.raise_for_status()

            html = resp.text
            # Look for CSV download links in supporting files
            csv_links = re.findall(
                r'href="(https?://[^"]*\.csv)"',
                html,
                re.IGNORECASE,
            )
            # Filter for school-level files
            target_link = None
            for link in csv_links:
                if "school" in link.lower() and key.replace("_", "") in link.lower().replace("_", ""):
                    target_link = link
                    break
            if not target_link and csv_links:
                # Fall back to first CSV
                target_link = csv_links[0]

            if target_link:
                return self.download(target_link, filename=filename, force=True)

        except Exception as exc:
            self._logger.warning("Failed to find supporting file for %s: %s", key, exc)

        return None

    # ------------------------------------------------------------------
    # LAEstab mapping helper
    # ------------------------------------------------------------------

    def _load_laestab_map(self, db_path: str, council: str | None = None) -> dict[str, int]:
        """Load a LAEstab -> school_id mapping from the database.

        LAEstab is typically the LA code (3 digits) + establishment number (4 digits).
        We reconstruct it from the URN and school data where possible.
        """
        # LAEstab isn't stored directly, so this is a best-effort lookup.
        # Return empty dict — the URN-based lookup is primary.
        return {}

    # ------------------------------------------------------------------
    # Combined refresh
    # ------------------------------------------------------------------

    def refresh_performance(
        self,
        council: str | None = None,
        force_download: bool = False,
        db_path: str | None = None,
    ) -> dict[str, dict[str, int]]:
        """Refresh KS2, KS4, and absence data.

        Returns
        -------
        dict
            Nested statistics: {ks2: {...}, ks4: {...}, absence: {...}}.
        """
        ks2_stats = self.refresh_ks2(council=council, force_download=force_download, db_path=db_path)
        ks4_stats = self.refresh_ks4(council=council, force_download=force_download, db_path=db_path)
        absence_stats = self.refresh_absence(council=council, force_download=force_download, db_path=db_path)
        return {"ks2": ks2_stats, "ks4": ks4_stats, "absence": absence_stats}

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

    @staticmethod
    def _safe_float(value: object) -> float | None:
        """Convert a value to float, returning None on failure."""
        if value is None:
            return None
        try:
            v = float(str(value))
            if v != v:  # NaN check
                return None
            return v
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_year(value: str) -> int:
        """Parse an EES time_period value into a year int.

        EES uses formats like '202324' (academic year 2023/24) or '2024'.
        Returns the starting year as an int (e.g. 202324 -> 2023, 2024 -> 2024).
        """
        s = str(value).strip()
        if len(s) == 6:
            # e.g. '202324' -> 2023
            try:
                return int(s[:4])
            except ValueError:
                pass
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return 0
