"""Re-run the clubs agent only for schools that have no club data.

Usage:
    uv run python scripts/rerun_missing_clubs.py
"""

import asyncio
import logging

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from src.agents.clubs import ClubsAgent
from src.config import get_settings
from src.db.models import School

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")

    # Find schools with websites but no club data
    with Session(engine) as session:
        stmt = text("""
            SELECT s.id, s.name, s.website
            FROM schools s
            WHERE s.website IS NOT NULL AND s.website != ''
            AND s.id NOT IN (SELECT DISTINCT school_id FROM school_clubs)
            ORDER BY s.name
        """)
        rows = session.execute(stmt).all()

    if not rows:
        logger.info("All schools with websites have club data already!")
        return

    logger.info("Found %d schools without club data. Re-running agent for these.", len(rows))

    agent = ClubsAgent(council="Milton Keynes", delay=0.3)

    for school_id, school_name, school_website in rows:
        if not school_website:
            continue
        logger.info("Re-checking: %s (id=%d)", school_name, school_id)
        clubs = await agent._discover_clubs(school_id, school_name, school_website)
        if clubs:
            agent._replace_clubs_in_db(school_id, clubs)
            logger.info("Found %d clubs for %s", len(clubs), school_name)
        else:
            logger.info("Still no clubs for %s", school_name)


if __name__ == "__main__":
    asyncio.run(main())
