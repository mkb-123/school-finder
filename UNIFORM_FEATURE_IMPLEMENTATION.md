# Uniform Cost & Appearance Feature Implementation

## Summary

Implemented the "Uniform Cost & Appearance" feature from FEATURE_REQUESTS.md. This feature helps parents understand what the school uniform looks like and how much it will cost, flagging expensive branded requirements versus affordable generic options.

## Changes Made

### 1. Database Model (`src/db/models.py`)
- Added `SchoolUniform` table with fields for:
  - Description, style, and colors
  - Supplier requirements (specific vs. generic)
  - Cost breakdown for each item type (polo shirts, jumpers, trousers/skirts, PE kit, bag, coat, other items)
  - Total cost estimate
  - Affordability flag (`is_expensive`)
  - Notes field for additional information
- Added relationship to `School` model

### 2. Repository Layer
- **Base Interface** (`src/db/base.py`): Added `SchoolUniform` import and `get_uniform_for_school()` abstract method
- **SQLite Implementation** (`src/db/sqlite_repo.py`): Implemented `get_uniform_for_school()` method

### 3. API Schema (`src/schemas/school.py`)
- Added `UniformResponse` Pydantic model
- Updated `SchoolDetailResponse` to include uniform list field

### 4. API Endpoint (`src/api/schools.py`)
- Updated `get_school()` endpoint to fetch and include uniform data in response

### 5. Database Seeding (`src/db/seed.py`)
- Added `_generate_test_uniforms()` function that creates realistic uniform data:
  - Mix of affordable (supermarket alternatives acceptable) and expensive (specific supplier required) uniforms
  - Cost variations based on whether branded or generic
  - Realistic item costs (polo shirts, jumpers, trousers, PE kit, bags, coats)
  - Secondary schools more likely to have expensive branded requirements
- Integrated into main seeding process as step 11/11

### 6. Frontend Component (`frontend/src/components/UniformTab.tsx`)
- Created dedicated UniformTab component with:
  - Affordability indicator (green for affordable, amber for expensive)
  - Uniform details section (description, style, colors, supplier info)
  - Detailed cost breakdown showing:
    - Individual item costs with quantities
    - Total estimated cost
    - Clear pricing information
  - Responsive design with Tailwind CSS

### 7. Frontend Integration (Pending)
To complete the frontend integration, the following changes need to be made to `/home/mitzb/school-finder/frontend/src/pages/SchoolDetail.tsx`:

1. Add the `Uniform` interface (lines 43-63)
2. Update `SchoolDetail` interface to include `uniform: Uniform[]`
3. Add "Uniform" to the TABS array (after "Overview")
4. Import UniformTab component
5. Add the Uniform tab rendering case

Example code to add:
```typescript
// Add near other imports
import UniformTab from "../components/UniformTab";

// Add to TABS array (line ~63)
const TABS = [
  "Overview",
  "Uniform",
  "Clubs",
  // ... rest of tabs
] as const;

// Add in tab content section (around line 726)
{activeTab === "Uniform" && (
  <UniformTab uniform={school.uniform ?? []} />
)}
```

## Testing Required

1. Run database seeding:
```bash
uv run python -m src.db.seed --council "Milton Keynes"
```

2. Verify uniform data is created in the database

3. Test API endpoint:
```bash
curl http://localhost:8000/api/schools/{school_id}
```

4. Verify uniform data appears in response

5. Complete frontend integration and test UI:
   - Navigate to school detail page
   - Click "Uniform" tab
   - Verify affordable/expensive indicator
   - Check cost breakdown display
   - Test supplier website link (if present)

## Architecture Patterns Followed

- Repository pattern for data access
- Pydantic schemas for API validation
- Separation of concerns (models, schemas, API, services)
- Consistent with existing codebase patterns
- Realistic seed data generation using random but deterministic values
- Frontend component isolation and reusability

## Feature Highlights

- Clear distinction between affordable and expensive uniforms
- Detailed cost breakdown helps parents budget accurately
- Supplier information included for specific requirements
- Responsive, accessible UI design
- Realistic seed data for testing
