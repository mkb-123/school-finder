# Private School Hidden Costs Feature Implementation

## Overview
Implemented the "Private School Hidden Costs" feature from FEATURE_REQUESTS.md, which surfaces costs beyond the headline fee to help parents understand the true annual cost of private education.

## Changes Made

### 1. Database Model Extensions (`src/db/models.py`)
Added the following fields to the `PrivateSchoolDetails` model:

**Per-Term Costs:**
- `lunches_per_term`: Float | None - School lunches (~£200-300/term)
- `lunches_compulsory`: Boolean - Whether lunches are compulsory
- `trips_per_term`: Float | None - School trips and residentials
- `trips_compulsory`: Boolean
- `music_tuition_per_term`: Float | None - Individual music lessons
- `music_tuition_compulsory`: Boolean
- `sports_per_term`: Float | None - Sports fixtures transport
- `sports_compulsory`: Boolean

**Per-Year Costs:**
- `exam_fees_per_year`: Float | None - Exam entry fees (secondary/sixth form)
- `exam_fees_compulsory`: Boolean (default True)
- `textbooks_per_year`: Float | None - Textbooks and materials
- `textbooks_compulsory`: Boolean (default True)
- `uniform_per_year`: Float | None - Uniform from designated suppliers
- `uniform_compulsory`: Boolean (default True)
- `insurance_per_year`: Float | None - School insurance levy
- `insurance_compulsory`: Boolean
- `building_fund_per_year`: Float | None - Development fund contributions
- `building_fund_compulsory`: Boolean

**One-Time Costs:**
- `registration_fee`: Float | None - Registration fee
- `deposit_fee`: Float | None - Deposit (often refundable, typically one term's fee)

**Notes:**
- `hidden_costs_notes`: Text | None - Additional notes about costs

### 2. API Schemas (`src/schemas/school.py`)
Extended `PrivateSchoolDetailsResponse` to include all hidden cost fields.

Added new response models:
- `HiddenCostItem`: Individual cost item with name, amount, frequency, and compulsory flag
- `TrueAnnualCostResponse`: Complete cost breakdown including:
  - Headline fees (termly and annual)
  - List of hidden cost items
  - Calculated totals for compulsory costs, optional costs, and one-time costs
  - True annual cost (headline + compulsory extras)
  - Total with optional extras
  - Notes

### 3. API Endpoint (`src/api/private_schools.py`)
Added new endpoint:
```
GET /api/private-schools/{school_id}/true-cost
```

Returns a cost breakdown for each fee age group (e.g., Nursery, Junior, Senior, Sixth Form).

Calculates:
- **True Annual Cost** = Annual fee + Compulsory hidden costs
- **Total with Optional** = True annual cost + Optional extras
- Separates costs into compulsory vs. optional
- Converts per-term costs to annual (multiplies by 3)
- Identifies one-time costs separately

### 4. Data Population (`src/db/add_hidden_costs.py`)
Created a standalone script to add realistic hidden costs to existing private school records.

The script:
- Generates age-appropriate hidden costs (nursery costs differ from sixth form)
- Uses realistic ranges:
  - Lunches: £150-300/term
  - Trips: £30-250/term (varies by age)
  - Exam fees: £200-800/year (secondary/sixth form only)
  - Textbooks: £50-600/year (increases with age)
  - Music tuition: £150-300/term (optional)
  - Sports: £30-120/term
  - Uniform: £150-600/year
  - Registration: £50-200 (one-time)
  - Deposit: Typically one term's fee
  - Insurance: £50-150/year
  - Building fund: £100-500/year

Usage:
```bash
uv run python -m src.db.add_hidden_costs
```

### 5. Frontend Display (`frontend/src/pages/PrivateSchoolDetail.tsx`)
Extended the private school detail page with:

**Interface Updates:**
- Added all hidden cost fields to the `PrivateDetail` interface

**Helper Function:**
- `calculateTrueAnnualCost()`: Calculates headline fee, compulsory extras, optional extras, and total

**New UI Section: "True Annual Cost"**
- Prominent orange-themed section to highlight these important costs
- Displays cost breakdown cards for each fee age group
- Shows:
  - Headline annual fee
  - Compulsory extras breakdown (itemized)
  - True annual cost (highlighted)
  - Optional extras breakdown (itemized)
  - One-time costs (registration, deposit)
- Clear visual distinction between compulsory and optional costs
- Mobile-responsive grid layout

**Design Rationale:**
- Orange color scheme draws attention to these often-hidden costs
- Compulsory costs are emphasized over optional ones
- Parents can see at a glance what they'll actually pay vs. what's advertised
- One-time costs shown separately for first-year budgeting

## How It Works

1. **Data Storage**: Hidden costs are stored in the `private_school_details` table alongside existing fee information
2. **API Response**: The standard private school detail endpoint includes all cost fields
3. **Cost Calculation**: A dedicated endpoint calculates true annual costs with full breakdown
4. **Frontend Display**: The detail page shows a prominent cost breakdown section
5. **Transparency**: Each cost is flagged as compulsory or optional so parents understand what they must pay

## Testing

To test the feature:

1. **Seed the database** with private schools:
   ```bash
   uv run python -m src.db.seed --council "Milton Keynes"
   ```

2. **Add hidden costs** to the seeded data:
   ```bash
   uv run python -m src.db.add_hidden_costs
   ```

3. **Start the backend**:
   ```bash
   uv run python -m src.main
   ```

4. **Start the frontend**:
   ```bash
   cd frontend && npm run dev
   ```

5. **View a private school**:
   - Navigate to http://localhost:5173/private-schools
   - Click on any private school
   - Scroll to the "True Annual Cost" section
   - See the breakdown of all costs

6. **Test the API directly**:
   ```bash
   curl http://localhost:8000/api/private-schools/1/true-cost
   ```

## Business Value

This feature addresses a major pain point for parents considering private education:
- **Transparency**: Shows the real cost beyond marketing materials
- **Budgeting**: Helps families understand if they can truly afford a school
- **Comparison**: Enables like-for-like comparison across schools
- **Trust**: Builds credibility by surfacing information schools often bury

Common surprise costs this feature reveals:
- Lunches not included (~£600-900/year)
- Compulsory exam fees (£200-800/year for older students)
- Textbooks and materials (£100-600/year)
- Uniform from expensive designated suppliers (£200-600/year)
- Insurance levies (£50-150/year)
- Building fund "donations" that are effectively compulsory (£100-500/year)

**Result**: Parents can see that a school advertised at £15,000/year might actually cost £18,000+/year when all compulsory extras are included.

## Architecture Notes

- **Repository Pattern**: All data access goes through the abstract repository interface
- **Pydantic Validation**: All API responses are validated
- **Realistic Data**: Seed script generates age-appropriate cost data
- **Extensible**: Easy to add more cost categories in future (e.g., sibling discounts, bursaries)
- **Backward Compatible**: Existing private school records work fine with null cost fields

## Future Enhancements

Possible additions:
1. **Sibling Discounts**: Model how costs reduce with multiple children
2. **Bursary Calculator**: Help families estimate financial aid eligibility
3. **Cost Comparison Tool**: Side-by-side comparison of true costs across shortlisted schools
4. **Historical Trends**: Track how hidden costs increase year-on-year
5. **Export**: Allow parents to export cost breakdown as PDF
6. **Calculator**: Interactive tool to estimate total cost based on child age and optional extras chosen

## Files Modified

- `src/db/models.py`: Extended PrivateSchoolDetails model
- `src/schemas/school.py`: Added hidden cost response schemas
- `src/api/private_schools.py`: Added true-cost endpoint
- `frontend/src/pages/PrivateSchoolDetail.tsx`: Added cost breakdown UI

## Files Created

- `src/db/add_hidden_costs.py`: Script to populate hidden costs for existing records
- `PRIVATE_SCHOOL_HIDDEN_COSTS_IMPLEMENTATION.md`: This documentation

## Commit Message

```
Feature: Add Private School Hidden Costs breakdown

Extends private school details to include itemized hidden costs
beyond the headline fee. Surfaces compulsory vs optional extras,
calculates true annual cost, and displays prominent cost breakdown
on school detail pages. Helps parents understand the real cost of
private education.

- Add 14 hidden cost fields to PrivateSchoolDetails model (lunches,
  trips, exams, textbooks, music, sports, uniform, registration,
  deposit, insurance, building fund)
- Add /api/private-schools/{id}/true-cost endpoint with full breakdown
- Create script to populate realistic hidden costs for test data
- Add "True Annual Cost" section to private school detail page
- Show compulsory vs optional costs with clear visual distinction
- Flag costs by frequency (per term, per year, one-time)

Addresses feature request: Private School Hidden Costs
