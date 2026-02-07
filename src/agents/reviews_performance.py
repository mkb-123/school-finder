"""Agent 3: Reviews & Performance Agent.

Downloads publicly available Ofsted management information and DfE school
performance CSVs, processes them with **Polars**, matches records to
schools by URN, and stores results in the ``school_performance`` and
``school_reviews`` tables.

Usage
-----
::

    python -m src.agents.reviews_performance --council "Milton Keynes"
"""

from __future__ import annotations

import logging
import pathlib

import polars as pl
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.db.models import School, SchoolPerformance, SchoolReview

logger = logging.getLogger(__name__)

# Public download URLs for Ofsted and DfE datasets.
_OFSTED_MI_CSV_URL = (
    "https://www.gov.uk/government/statistical-data-sets/"
    "monthly-management-information-ofsteds-school-inspections-outcomes"
)
_DFE_PERFORMANCE_CSV_URL = "https://www.compare-school-performance.service.gov.uk/download-data"


class ReviewsPerformanceAgent(BaseAgent):
    """Collect Ofsted ratings and DfE performance data for schools.

    The agent:

    1. Downloads the Ofsted management information CSV.
    2. Downloads the DfE school performance CSV.
    3. Reads both files with Polars and filters to the configured council.
    4. Matches rows to existing schools by URN.
    5. Persists results into ``school_performance`` and ``school_reviews``.

    Parameters
    ----------
    council:
        Council name, e.g. ``"Milton Keynes"``.
    cache_dir:
        Directory for cached HTTP responses and downloaded CSVs.
    delay:
        Seconds to wait between HTTP requests.
    """

    def __init__(
        self,
        council: str,
        cache_dir: str = "./data/cache",
        delay: float = 1.0,
    ) -> None:
        super().__init__(council=council, cache_dir=cache_dir, delay=delay)
        self._csv_dir = self.cache_dir / "csv"
        self._csv_dir.mkdir(parents=True, exist_ok=True)

    async def run(self) -> None:
        """Execute the reviews & performance data-collection pipeline.

        Steps
        -----
        1. Load the URN-to-school_id mapping from the database.
        2. Download and process the Ofsted CSV.
        3. Download and process the DfE performance CSV.
        4. Persist matched records.
        """
        self._logger.info("Starting reviews & performance agent for council=%r", self.council)

        urn_map = self._load_urn_map()
        if not urn_map:
            self._logger.warning("No schools with URNs found in DB for council=%r", self.council)
            return

        self._logger.info("Loaded %d school URNs for council=%r", len(urn_map), self.council)

        # --- Ofsted data ---
        ofsted_records = await self._process_ofsted(urn_map)
        if ofsted_records:
            self._save_reviews(ofsted_records)
            self._logger.info("Saved %d Ofsted review records", len(ofsted_records))

        # --- DfE performance data ---
        performance_records = await self._process_performance(urn_map)
        if performance_records:
            self._save_performance(performance_records)
            self._logger.info("Saved %d performance records", len(performance_records))

    # ------------------------------------------------------------------
    # Database reads
    # ------------------------------------------------------------------

    def _load_urn_map(self) -> dict[str, int]:
        """Load a mapping of URN -> school_id for the configured council.

        Returns
        -------
        dict[str, int]
            Keys are URN strings, values are the database primary key.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            stmt = select(School.id, School.urn).where(
                School.council == self.council,
                School.urn.is_not(None),
            )
            rows = session.execute(stmt).all()

        return {str(urn): school_id for school_id, urn in rows}

    # ------------------------------------------------------------------
    # Ofsted processing
    # ------------------------------------------------------------------

    async def _process_ofsted(self, urn_map: dict[str, int]) -> list[dict[str, object]]:
        """Download and parse the Ofsted management information CSV.

        Parameters
        ----------
        urn_map:
            Mapping of URN strings to database school IDs.

        Returns
        -------
        list[dict[str, object]]
            Review records ready for persistence.
        """
        csv_path = self._csv_dir / "ofsted_mi.csv"

        if not csv_path.exists():
            self._logger.info("Downloading Ofsted MI CSV...")
            try:
                content = await self.fetch_page(_OFSTED_MI_CSV_URL)
                # The URL above is the landing page.  In a full implementation
                # we would parse it to find the actual CSV download link.
                # For now, write the page content so the skeleton runs.
                csv_path.write_text(content, encoding="utf-8")
            except Exception:
                self._logger.exception("Failed to download Ofsted CSV")
                return []

        return self._parse_ofsted_csv(csv_path, urn_map)

    def _parse_ofsted_csv(self, csv_path: pathlib.Path, urn_map: dict[str, int]) -> list[dict[str, object]]:
        """Read the Ofsted CSV with Polars and extract review records.

        Parameters
        ----------
        csv_path:
            Path to the downloaded CSV file.
        urn_map:
            Mapping of URN strings to database school IDs.

        Returns
        -------
        list[dict[str, object]]
            Dicts with keys matching :class:`~src.db.models.SchoolReview` columns.
        """
        self._logger.info("Parsing Ofsted CSV for %s", self.council)
        try:
            df = pl.read_csv(csv_path, ignore_errors=True, truncate_ragged_lines=True)
            self._logger.info("Ofsted CSV shape: %s, columns: %s", df.shape, df.columns)
        except Exception:
            self._logger.exception("Could not read Ofsted CSV at %s", csv_path)
            return []

        # Find the URN column (flexible matching)
        urn_col = self._find_column(df, ["URN", "urn", "Urn", "LAESTAB"])
        if not urn_col:
            self._logger.error("Could not find URN column in Ofsted CSV")
            return []

        # Find rating and date columns
        rating_col = self._find_column(
            df, ["Overall effectiveness", "OverallEffectiveness", "Overall Effectiveness", "Rating"]
        )
        date_col = self._find_column(
            df, ["Inspection end date", "InspectionEndDate", "Inspection date", "InspectionDate"]
        )
        type_col = self._find_column(df, ["Inspection type", "InspectionType", "Type"])
        la_col = self._find_column(df, ["Local authority", "LocalAuthority", "LA", "Local Authority"])

        # Filter to our URNs and council if possible
        try:
            df_filtered = df.filter(pl.col(urn_col).cast(str).is_in(list(urn_map.keys())))
            if la_col and self.council:
                council_lower = self.council.lower()
                df_filtered = df_filtered.filter(pl.col(la_col).str.to_lowercase().str.contains(council_lower))
        except Exception as e:
            self._logger.warning("Could not filter CSV: %s", e)
            df_filtered = df

        self._logger.info("Found %d matching schools in Ofsted CSV", len(df_filtered))

        # Extract records
        records = []
        for row in df_filtered.iter_rows(named=True):
            urn_str = str(row.get(urn_col, "")).strip()
            school_id = urn_map.get(urn_str)
            if school_id is None:
                continue

            rating = row.get(rating_col) if rating_col else None
            snippet = row.get(type_col) if type_col else None
            review_date = row.get(date_col) if date_col else None

            records.append(
                {
                    "school_id": school_id,
                    "source": "Ofsted",
                    "rating": rating,
                    "snippet": snippet,
                    "review_date": review_date,
                }
            )

        return records

    def _find_column(self, df: pl.DataFrame, candidates: list[str]) -> str | None:
        """Find the first matching column name from a list of candidates."""
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
        return None

    # ------------------------------------------------------------------
    # DfE performance processing
    # ------------------------------------------------------------------

    async def _process_performance(self, urn_map: dict[str, int]) -> list[dict[str, object]]:
        """Download and parse the DfE school performance CSV.

        Parameters
        ----------
        urn_map:
            Mapping of URN strings to database school IDs.

        Returns
        -------
        list[dict[str, object]]
            Performance records ready for persistence.
        """
        csv_path = self._csv_dir / "dfe_performance.csv"

        if not csv_path.exists():
            self._logger.info("Downloading DfE performance CSV...")
            try:
                content = await self.fetch_page(_DFE_PERFORMANCE_CSV_URL)
                csv_path.write_text(content, encoding="utf-8")
            except Exception:
                self._logger.exception("Failed to download DfE performance CSV")
                return []

        return self._parse_performance_csv(csv_path, urn_map)

    def _parse_performance_csv(
        self,
        csv_path: pathlib.Path,
        urn_map: dict[str, int],
    ) -> list[dict[str, object]]:
        """Read the DfE performance CSV with Polars and extract records.

        Parameters
        ----------
        csv_path:
            Path to the downloaded CSV file.
        urn_map:
            Mapping of URN strings to database school IDs.

        Returns
        -------
        list[dict[str, object]]
            Dicts with keys matching :class:`~src.db.models.SchoolPerformance`
            columns.
        """
        self._logger.info("Parsing DfE performance CSV for %s", self.council)
        try:
            df = pl.read_csv(csv_path, ignore_errors=True, truncate_ragged_lines=True)
            self._logger.info("DfE CSV shape: %s, columns: %s", df.shape, df.columns)
        except Exception:
            self._logger.exception("Could not read DfE CSV at %s", csv_path)
            return []

        # Find the URN column
        urn_col = self._find_column(df, ["URN", "urn", "Urn", "LAESTAB"])
        if not urn_col:
            self._logger.error("Could not find URN column in DfE CSV")
            return []

        # Find performance metric columns (primary and secondary)
        year_col = self._find_column(df, ["YEAR", "Year", "year", "Academic year"])

        # Primary school metrics (KS2)
        ks2_reading_col = self._find_column(df, ["KS2_reading_expected", "KS2READINGEXP", "Reading expected"])
        ks2_writing_col = self._find_column(df, ["KS2_writing_expected", "KS2WRITINGEXP", "Writing expected"])
        ks2_maths_col = self._find_column(df, ["KS2_maths_expected", "KS2MATHSEXP", "Maths expected"])

        # Secondary school metrics (KS4)
        prog8_col = self._find_column(df, ["PROG8SCORE", "Progress 8", "Progress8"])
        att8_col = self._find_column(df, ["ATT8SCORE", "Attainment 8", "Attainment8"])
        ebacc_col = self._find_column(df, ["EBACCAPS", "EBacc APS", "EBaccAPS"])

        # Filter to our URNs
        try:
            df_filtered = df.filter(pl.col(urn_col).cast(str).is_in(list(urn_map.keys())))
        except Exception as e:
            self._logger.warning("Could not filter CSV: %s", e)
            df_filtered = df

        self._logger.info("Found %d matching schools in DfE CSV", len(df_filtered))

        # Extract records
        records = []
        for row in df_filtered.iter_rows(named=True):
            urn_str = str(row.get(urn_col, "")).strip()
            school_id = urn_map.get(urn_str)
            if school_id is None:
                continue

            year = int(row.get(year_col, 0)) if year_col else 0

            # Add all available metrics for this school
            if ks2_reading_col and row.get(ks2_reading_col):
                records.append(
                    {
                        "school_id": school_id,
                        "metric_type": "KS2_reading_expected",
                        "metric_value": str(row.get(ks2_reading_col, "")),
                        "year": year,
                        "source_url": _DFE_PERFORMANCE_CSV_URL,
                    }
                )
            if ks2_writing_col and row.get(ks2_writing_col):
                records.append(
                    {
                        "school_id": school_id,
                        "metric_type": "KS2_writing_expected",
                        "metric_value": str(row.get(ks2_writing_col, "")),
                        "year": year,
                        "source_url": _DFE_PERFORMANCE_CSV_URL,
                    }
                )
            if ks2_maths_col and row.get(ks2_maths_col):
                records.append(
                    {
                        "school_id": school_id,
                        "metric_type": "KS2_maths_expected",
                        "metric_value": str(row.get(ks2_maths_col, "")),
                        "year": year,
                        "source_url": _DFE_PERFORMANCE_CSV_URL,
                    }
                )
            if prog8_col and row.get(prog8_col):
                records.append(
                    {
                        "school_id": school_id,
                        "metric_type": "Progress8",
                        "metric_value": str(row.get(prog8_col, "")),
                        "year": year,
                        "source_url": _DFE_PERFORMANCE_CSV_URL,
                    }
                )
            if att8_col and row.get(att8_col):
                records.append(
                    {
                        "school_id": school_id,
                        "metric_type": "Attainment8",
                        "metric_value": str(row.get(att8_col, "")),
                        "year": year,
                        "source_url": _DFE_PERFORMANCE_CSV_URL,
                    }
                )
            if ebacc_col and row.get(ebacc_col):
                records.append(
                    {
                        "school_id": school_id,
                        "metric_type": "EBacc_APS",
                        "metric_value": str(row.get(ebacc_col, "")),
                        "year": year,
                        "source_url": _DFE_PERFORMANCE_CSV_URL,
                    }
                )

        return records

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_reviews(self, records: list[dict[str, object]]) -> None:
        """Write parsed Ofsted review records to the ``school_reviews`` table.

        Parameters
        ----------
        records:
            Review dicts as returned by :meth:`_parse_ofsted_csv`.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            for record in records:
                review = SchoolReview(
                    school_id=record["school_id"],
                    source=str(record.get("source", "Ofsted")),
                    rating=record.get("rating"),
                    snippet=record.get("snippet"),
                    review_date=record.get("review_date"),
                )
                session.add(review)
            session.commit()
            self._logger.info("Committed %d review rows", len(records))

    def _save_performance(self, records: list[dict[str, object]]) -> None:
        """Write parsed performance records to the ``school_performance`` table.

        Parameters
        ----------
        records:
            Performance dicts as returned by :meth:`_parse_performance_csv`.
        """
        settings = get_settings()
        engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

        with Session(engine) as session:
            for record in records:
                perf = SchoolPerformance(
                    school_id=record["school_id"],
                    metric_type=str(record.get("metric_type", "")),
                    metric_value=str(record.get("metric_value", "")),
                    year=int(record.get("year", 0)),
                    source_url=record.get("source_url"),
                )
                session.add(perf)
            session.commit()
            self._logger.info("Committed %d performance rows", len(records))


if __name__ == "__main__":
    from src.agents.base_agent import run_agent_cli

    run_agent_cli(ReviewsPerformanceAgent, "Download Ofsted and DfE data for schools in a council.")
