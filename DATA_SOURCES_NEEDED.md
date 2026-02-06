# Real Data Sources Needed

This document tracks which features need real data and where to get it.

## ✅ Implemented with Real Data

| Feature | Data Source | Status | Last Updated |
|---------|-------------|--------|--------------|
| **Ofsted Ratings** | GOV.UK Ofsted MI CSV | ✅ Implemented | 2025-01-10 |
| **School Names/Addresses** | GIAS data | ✅ Available | - |
| **URNs** | GIAS data | ✅ Available | - |

## ❌ Features Needing Real Data

### Critical (Affects Parent Decisions)

| Feature | Where to Get Real Data | Priority | Notes |
|---------|------------------------|----------|-------|
| **Performance Data** | [DfE School Performance](https://www.compare-school-performance.service.gov.uk/download-data) | 🔴 CRITICAL | SATs, GCSEs, Progress 8 |
| **Admissions History** | Local authority admissions reports | 🔴 CRITICAL | Places offered, last distance |
| **Ofsted History** | Ofsted MI CSV (historical column) | 🔴 CRITICAL | Currently showing fake trajectory |

### Important (Useful for Parents)

| Feature | Where to Get Real Data | Priority | Notes |
|---------|------------------------|----------|-------|
| **Clubs** | School websites (scraping) | 🟡 HIGH | Breakfast/after-school clubs |
| **Term Dates** | Council websites, school websites | 🟡 HIGH | Academic calendars |
| **Uniform Details** | School websites | 🟡 MEDIUM | Costs, suppliers |
| **Admissions Criteria** | School websites, council sites | 🟡 HIGH | Priority tiers, SIF requirements |

### Nice to Have (Enhancement Features)

| Feature | Where to Get Real Data | Priority | Notes |
|---------|------------------------|----------|-------|
| **Bus Routes** | Council transport dept, schools | 🟢 LOW | School bus services |
| **Parking Info** | Crowd-sourced (user submissions) | 🟢 LOW | Parent ratings |
| **Class Sizes** | School census data, schools | 🟢 MEDIUM | Pupil numbers per year |
| **Holiday Clubs** | School websites, external providers | 🟢 LOW | School holiday provision |

## Data Collection Methods

### 1. Direct Downloads (Preferred)
- **Ofsted**: Download monthly MI CSV
- **Performance**: Download DfE performance tables CSV
- **GIAS**: Download establishment data

### 2. API Integration
- **Postcodes.io**: Already implemented for geocoding ✅
- **TfL/Transport APIs**: For journey planning

### 3. Web Scraping (Last Resort)
- **School Websites**: For clubs, term dates, uniform
- **Council Sites**: For admissions data
- Should implement agents in `src/agents/` directory

### 4. Crowd-Sourced
- **Parking Ratings**: Parent submissions (database ready)
- **Reviews**: Parent feedback

## Implementation Priority

1. ❌ Fix Ofsted trajectory (delete fake historical data) ← DONE
2. ❌ Import real performance data from DfE
3. ❌ Import real admissions data from councils
4. ⚠️ Hide features with no data (show "Data not available")
5. ⚠️ Create web scrapers for clubs/term dates
6. ⚠️ Enable crowd-sourcing for parking/reviews

## Current Status

- **ALL random data generation DISABLED** ✅
- **Real Ofsted ratings imported** ✅ (94 schools)
- **Fake Ofsted history deleted** ✅
- **Features hidden when no data** ⚠️ In Progress

## Rules

1. **NEVER generate random/fake/demo data**
2. If real data is not available, show "No data available"
3. Hide features entirely if they have no real data yet
4. Update this document when implementing new data sources
