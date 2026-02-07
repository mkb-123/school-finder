"""Unified CLI for refreshing school data from government sources.

Usage::

    # Refresh everything for a council
    python -m src.services.gov_data refresh --council "Milton Keynes"

    # Refresh specific sources
    python -m src.services.gov_data refresh --source gias --council "Milton Keynes"
    python -m src.services.gov_data refresh --source ofsted --council "Milton Keynes"
    python -m src.services.gov_data refresh --source performance --council "Milton Keynes"
    python -m src.services.gov_data refresh --source admissions --council "Milton Keynes"

    # Force re-download (bypass cache)
    python -m src.services.gov_data refresh --council "Milton Keynes" --force
"""

from __future__ import annotations

import argparse
import logging
import sys

from src.services.gov_data.ees import EESService
from src.services.gov_data.gias import GIASService
from src.services.gov_data.ofsted import OfstedService

ALL_SOURCES = ("gias", "ofsted", "performance", "admissions")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.services.gov_data",
        description="Refresh school data from UK government sources.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    refresh = sub.add_parser("refresh", help="Fetch latest data and update the database")
    refresh.add_argument(
        "--council",
        required=True,
        help='Council name, e.g. "Milton Keynes".',
    )
    refresh.add_argument(
        "--source",
        choices=ALL_SOURCES,
        default=None,
        help="Specific source to refresh. Omit to refresh all.",
    )
    refresh.add_argument(
        "--force",
        action="store_true",
        help="Force re-download, bypassing cache.",
    )
    refresh.add_argument(
        "--db",
        default=None,
        help="Override database path.",
    )

    return parser.parse_args(argv)


def _refresh_gias(council: str, force: bool, db_path: str | None) -> None:
    print(f"\n{'=' * 60}")
    print("GIAS - School Register")
    print(f"{'=' * 60}")
    service = GIASService()
    stats = service.refresh(council=council, force_download=force, db_path=db_path)
    print(f"  Inserted: {stats['inserted']}")
    print(f"  Updated:  {stats['updated']}")
    print(f"  Total:    {stats['total']}")
    print(f"  With coordinates: {stats['with_coordinates']}")


def _refresh_ofsted(council: str, force: bool, db_path: str | None) -> None:
    print(f"\n{'=' * 60}")
    print("Ofsted - Inspection Ratings")
    print(f"{'=' * 60}")
    service = OfstedService()
    stats = service.refresh(council=council, force_download=force, db_path=db_path)
    print(f"  Updated:   {stats['updated']}")
    print(f"  Skipped:   {stats['skipped']}")
    print(f"  Not found: {stats['not_found']}")


def _refresh_performance(council: str, force: bool, db_path: str | None) -> None:
    print(f"\n{'=' * 60}")
    print("EES - School Performance (KS2 + KS4)")
    print(f"{'=' * 60}")
    service = EESService()
    stats = service.refresh_performance(council=council, force_download=force, db_path=db_path)
    for key, sub_stats in stats.items():
        print(f"  {key.upper()}:")
        for k, v in sub_stats.items():
            print(f"    {k}: {v}")


def _refresh_admissions(council: str, force: bool, db_path: str | None) -> None:
    print(f"\n{'=' * 60}")
    print("EES - Admissions Data")
    print(f"{'=' * 60}")
    service = EESService()
    stats = service.refresh_admissions(council=council, force_download=force, db_path=db_path)
    for k, v in stats.items():
        print(f"  {k}: {v}")


_REFRESH_FUNCS = {
    "gias": _refresh_gias,
    "ofsted": _refresh_ofsted,
    "performance": _refresh_performance,
    "admissions": _refresh_admissions,
}


def main(argv: list[str] | None = None) -> None:
    _setup_logging()
    args = _parse_args(argv)

    if args.command == "refresh":
        council = args.council
        force = args.force
        db_path = args.db

        print("School Finder - Government Data Refresh")
        print(f"  Council: {council}")
        if args.source:
            print(f"  Source:  {args.source}")
        else:
            print(f"  Source:  all ({', '.join(ALL_SOURCES)})")
        print(f"  Force:   {force}")

        sources = [args.source] if args.source else list(ALL_SOURCES)
        for source in sources:
            func = _REFRESH_FUNCS[source]
            try:
                func(council, force, db_path)
            except Exception as exc:
                print(f"\n  ERROR refreshing {source}: {exc}")
                logging.getLogger(__name__).exception("Refresh failed for %s", source)

        print(f"\n{'=' * 60}")
        print("Refresh complete.")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    sys.exit(main() or 0)
