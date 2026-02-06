# Ralph Wiggum Use Cases for School Finder

Pre-built prompts for running Ralph Wiggum loops on this project. Copy and paste these into `/ralph-loop`.

## Data Seeding

### Seed Milton Keynes schools from GIAS
```
/ralph-loop "Download the GIAS establishments CSV, seed all Milton Keynes schools into the SQLite database, and verify the data is correct. Check that lat/lng, Ofsted ratings, age ranges, and gender policies are populated. Fix any parsing errors or missing data. Use Polars for CSV processing. Run the seed script and report the count of schools inserted." --completion-promise "SEED_COMPLETE" --max-iterations 20
```

### Seed Ofsted inspection data
```
/ralph-loop "Download the latest Ofsted inspection data CSV, match it to schools in the database by URN, and update ofsted_rating and ofsted_date fields. Verify all rated schools have correct data. Use Polars for CSV processing." --completion-promise "OFSTED_COMPLETE" --max-iterations 15
```

## Agent Development

### Build and test the term times agent
```
/ralph-loop "Build src/agents/term_times.py - the term times data collection agent. It should scrape Milton Keynes Council's term dates page and individual academy websites. Parse dates into the school_term_dates model. Write tests in tests/test_agents/test_term_times.py with mocked HTTP responses. Run tests until they all pass." --completion-promise "TERM_AGENT_COMPLETE" --max-iterations 30
```

### Build and test the clubs agent
```
/ralph-loop "Build src/agents/clubs.py - the breakfast and after-school clubs agent. Scrape school websites for wraparound care pages. Extract club names, types, days, times, costs. Write tests with mocked HTTP. Store results via the repository layer. Run tests until they all pass." --completion-promise "CLUBS_AGENT_COMPLETE" --max-iterations 30
```

### Build and test the reviews/performance agent
```
/ralph-loop "Build src/agents/reviews_performance.py - scrapes Ofsted reports and DfE performance tables. Extract SATs results, GCSE results, Progress 8, Attainment 8 scores. Write tests with mocked HTTP. Run tests until they all pass." --completion-promise "REVIEWS_AGENT_COMPLETE" --max-iterations 30
```

## Full Phase Implementation

### Phase 2: Map & Catchment
```
/ralph-loop "Implement Phase 2 from CLAUDE.md: Leaflet map integration with school pins, catchment radius circles, Ofsted colour-coded pins (Outstanding=green, Good=blue, RI=amber, Inadequate=red), and filter controls. Build both the frontend React components and the API endpoints they need. Run lint and tests after each change. Use the existing repository layer." --completion-promise "PHASE2_COMPLETE" --max-iterations 50
```

### Phase 3: Constraints & Filtering
```
/ralph-loop "Implement Phase 3 from CLAUDE.md: constraint panel UI (child age, gender, school type, faith), server-side filtering in the repository layer, and URL-based filter state for shareable links. Write tests for edge cases like gender-specific schools and age range overlaps. Run all tests until green." --completion-promise "PHASE3_COMPLETE" --max-iterations 40
```

### Phase 10: Decision Support Page
```
/ralph-loop "Implement Phase 10 from CLAUDE.md: the Decision Support page. Build the weighted scoring engine in src/services/decision.py, pros/cons auto-generation, the frontend DecisionSupport.tsx page with 'what if' scenario controls, shortlist in localStorage, and PDF export. Write tests for the scoring algorithm. Run all tests until green." --completion-promise "DECISION_COMPLETE" --max-iterations 50
```

## Test Coverage

### Get full test suite green
```
/ralph-loop "Run the full test suite with pytest. Fix every failing test. If tests are missing for critical logic (catchment calculations, filter application, API endpoints), write them. Do not skip or delete tests. Keep running pytest until every test passes with 0 failures." --completion-promise "ALL_TESTS_GREEN" --max-iterations 30
```

### Lint and format the entire codebase
```
/ralph-loop "Run ruff check src/ tests/ and ruff format --check src/ tests/. Fix every issue. Re-run until there are zero errors and zero warnings." --completion-promise "LINT_CLEAN" --max-iterations 15
```

## Tips

- **Set max-iterations** to avoid runaway loops. 20-30 is good for most tasks, 50 for full phases.
- **Be specific about 'done'** - Ralph works best when you can precisely describe what completion looks like.
- **Cancel anytime** with `/cancel-ralph`.
- **Check progress** by reading the transcript - Ralph logs its iteration count.
