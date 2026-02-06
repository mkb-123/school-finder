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

import argparse
import asyncio
import logging
import pathlib
import sys

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
_DFE_PERFORMANCE_CSV_URL = (
    "https://www.compare-school-performance.service.gov.uk/download-data"
)


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
        # TODO: implement real Ofsted CSV parsing once the actual file
        # format is determined.  The skeleton below demonstrates the Polars
        # read pattern that will be used.
        self._logger.info("TODO: implement Ofsted CSV parsing for %s", self.council)
        try:
            df = pl.read_csv(csv_path, ignore_errors=True, truncate_ragged_lines=True)
            self._logger.info("Ofsted CSV shape: %s, columns: %s", df.shape, df.columns)
        except Exception:
            self._logger.exception("Could not read Ofsted CSV at %s", csv_path)
            return []

        # Expected processing once columns are known:
        #
        #   df = df.filter(pl.col("URN").is_in(list(urn_map.keys())))
        #   records = []
        #   for row in df.iter_rows(named=True):
        #       school_id = urn_map.get(str(row["URN"]))
        #       if school_id is None:
        #           continue
        #       records.append({
        #           "school_id": school_id,
        #           "source": "Ofsted",
        #           "rating": row.get("Overall effectiveness"),
        #           "snippet": row.get("Inspection type"),
        #           "review_date": row.get("Inspection end date"),
        #       })
        #   return records

        return []

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
        # TODO: implement real DfE performance CSV parsing once the actual
        # file format is determined.
        self._logger.info("TODO: implement DfE performance CSV parsing for %s", self.council)
        try:
            df = pl.read_csv(csv_path, ignore_errors=True, truncate_ragged_lines=True)
            self._logger.info("DfE CSV shape: %s, columns: %s", df.shape, df.columns)
        except Exception:
            self._logger.exception("Could not read DfE CSV at %s", csv_path)
            return []

        # Expected processing once columns are known:
        #
        #   df = df.filter(pl.col("URN").cast(str).is_in(list(urn_map.keys())))
        #   records = []
        #   for row in df.iter_rows(named=True):
        #       school_id = urn_map.get(str(row["URN"]))
        #       if school_id is None:
        #           continue
        #       records.append({
        #           "school_id": school_id,
        #           "metric_type": "Progress8",
        #           "metric_value": str(row.get("PROG8SCORE", "")),
        #           "year": row.get("YEAR", 0),
        #           "source_url": _DFE_PERFORMANCE_CSV_URL,
        #       })
        #   return records

        return []

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


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the reviews & performance agent.

    Parameters
    ----------
    argv:
        Argument list.  Defaults to ``sys.argv[1:]`` when ``None``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments containing at least ``council``.
    """
    parser = argparse.ArgumentParser(
        description="Download Ofsted and DfE data for schools in a council.",
    )
    parser.add_argument(
        "--council",
        required=True,
        help='Council name, e.g. "Milton Keynes".',
    )
    parser.add_argument(
        "--cache-dir",
        default="./data/cache",
        help="Directory for cached HTTP responses and CSVs (default: ./data/cache).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between HTTP requests (default: 1.0).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for the reviews & performance agent.

    Parameters
    ----------
    argv:
        Optional argument list for testing; defaults to ``sys.argv[1:]``.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    agent = ReviewsPerformanceAgent(
        council=args.council,
        cache_dir=args.cache_dir,
        delay=args.delay,
    )
    asyncio.run(agent.run())


if __name__ == "__main__":
    sys.exit(main() or 0)
