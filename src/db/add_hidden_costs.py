"""Add hidden costs to existing PrivateSchoolDetails records.

Run this script after seeding to populate hidden cost fields.
Usage: uv run python -m src.db.add_hidden_costs
"""

import random
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.models import PrivateSchoolDetails

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "schools.db"


def add_hidden_costs_to_private_schools(db_path: str = str(DEFAULT_DB_PATH)) -> int:
    """Add realistic hidden costs to all PrivateSchoolDetails records."""
    engine = create_engine(f"sqlite:///{db_path}")
    session = Session(engine)

    try:
        details = session.query(PrivateSchoolDetails).all()
        if not details:
            print("No private school details found.")
            return 0

        count = 0
        for detail in details:
            fee_age_group = detail.fee_age_group or ""

            # Determine age category
            is_nursery = "Nursery" in fee_age_group or "Early Years" in fee_age_group
            is_infant_prep = "Infant" in fee_age_group or "Reception" in fee_age_group or "Pre-prep" in fee_age_group
            is_primary = "Primary" in fee_age_group or "Prep" in fee_age_group or "Junior" in fee_age_group
            is_secondary = "Secondary" in fee_age_group or "Senior" in fee_age_group
            is_sixth_form = "Sixth Form" in fee_age_group

            # Lunches (typically £200-300 per term, often not included)
            detail.lunches_per_term = float(random.randint(200, 300) if not is_nursery else random.randint(150, 250))
            detail.lunches_compulsory = random.choice([False, False, True])  # 1/3 compulsory

            # Trips (varies by age, £50-200 per term)
            if is_nursery or is_infant_prep:
                detail.trips_per_term = float(random.randint(30, 80))
            elif is_primary:
                detail.trips_per_term = float(random.randint(50, 150))
            else:  # secondary/sixth form
                detail.trips_per_term = float(random.randint(100, 250))
            detail.trips_compulsory = False

            # Exam fees (only for secondary and sixth form)
            if is_secondary:
                detail.exam_fees_per_year = float(random.randint(200, 500))
                detail.exam_fees_compulsory = True
            elif is_sixth_form:
                detail.exam_fees_per_year = float(random.randint(400, 800))
                detail.exam_fees_compulsory = True
            else:
                detail.exam_fees_per_year = None
                detail.exam_fees_compulsory = True

            # Textbooks (more for older pupils)
            if is_nursery or is_infant_prep:
                detail.textbooks_per_year = float(random.randint(50, 150))
            elif is_primary:
                detail.textbooks_per_year = float(random.randint(100, 250))
            elif is_secondary:
                detail.textbooks_per_year = float(random.randint(200, 400))
            else:  # sixth form
                detail.textbooks_per_year = float(random.randint(300, 600))
            detail.textbooks_compulsory = True

            # Music tuition (optional, per term)
            if not is_nursery:
                detail.music_tuition_per_term = float(random.randint(150, 300))
                detail.music_tuition_compulsory = False
            else:
                detail.music_tuition_per_term = None
                detail.music_tuition_compulsory = False

            # Sports fixtures and transport (per term)
            if is_primary or is_secondary or is_sixth_form:
                detail.sports_per_term = float(random.randint(30, 120))
                detail.sports_compulsory = False
            else:
                detail.sports_per_term = None
                detail.sports_compulsory = False

            # Uniform (per year, varies widely)
            if is_nursery or is_infant_prep:
                detail.uniform_per_year = float(random.randint(150, 300))
            elif is_primary:
                detail.uniform_per_year = float(random.randint(200, 400))
            else:  # secondary/sixth form
                detail.uniform_per_year = float(random.randint(300, 600))
            detail.uniform_compulsory = True

            # Registration fee (one-time, typically £50-200)
            detail.registration_fee = float(random.randint(50, 200))

            # Deposit (one-time, often refundable, typically one term's fee)
            detail.deposit_fee = detail.termly_fee if detail.termly_fee else 0.0

            # Insurance (per year, often optional)
            detail.insurance_per_year = float(random.randint(50, 150))
            detail.insurance_compulsory = random.choice([False, False, True])  # 1/3 compulsory

            # Building/development fund (per year, often optional but encouraged)
            detail.building_fund_per_year = float(random.randint(100, 500))
            detail.building_fund_compulsory = random.choice([False, False, False, True])  # 1/4 compulsory

            detail.hidden_costs_notes = "Costs shown are estimates. Contact the school for exact figures."

            count += 1

        session.commit()
        print(f"Added hidden costs to {count} private school detail records.")
        return count

    finally:
        session.close()


if __name__ == "__main__":
    add_hidden_costs_to_private_schools()
