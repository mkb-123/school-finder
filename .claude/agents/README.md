# Claude AI Specialist Agents

This directory contains specialist agent configurations for Claude AI to intelligently find and extract school data from various UK government and public sources.

## Available Agents

### 1. Ofsted Specialist (`ofsted-specialist.md`)
**Purpose**: Find official Ofsted inspection ratings and reports

**Data Sources**:
- Ofsted Data View (reports.ofsted.gov.uk)
- Ofsted Management Information CSV
- Individual school Ofsted reports

**Use Cases**:
- Find current Ofsted rating for a specific school
- Download latest inspection data for all schools in a council
- Verify Ofsted ratings in database against official sources
- Extract detailed inspection judgements from reports

**Example Prompt**:
```
You are an Ofsted Specialist Agent. Find the current Ofsted rating for Caroline Haslett Primary School (URN 110394) in Milton Keynes. Use the Ofsted Data View at reports.ofsted.gov.uk and provide the rating, inspection date, and report URL.
```

---

### 2. Clubs Specialist (`clubs-specialist.md`)
**Purpose**: Find breakfast clubs, after-school clubs, and wraparound care

**Data Sources**:
- School websites (wraparound care pages)
- Council childcare directories
- Third-party childcare provider websites
- School prospectuses and handbooks

**Use Cases**:
- Find all clubs offered at a specific school
- Extract club times, costs, and booking methods
- Compare club offerings across multiple schools
- Identify schools with early breakfast clubs for working parents

**Example Prompt**:
```
You are a Clubs Specialist Agent. Find all breakfast and after-school clubs at Caroline Haslett Primary School, Milton Keynes. Extract club names, times, costs, and how parents can book. Search the school website and council childcare directory.
```

---

### 3. Term Times Specialist (`term-times-specialist.md`)
**Purpose**: Extract school term dates and holiday schedules

**Data Sources**:
- Council term dates pages (for maintained schools)
- Individual school websites (for academies)
- Academy trust websites
- School calendar downloads (ICS files)

**Use Cases**:
- Get term dates for a specific school
- Extract council-wide standard term dates
- Compare holiday lengths between schools
- Identify INSET days when schools are closed

**Example Prompt**:
```
You are a Term Times Specialist Agent. Find the term dates for all Milton Keynes maintained schools for the 2025/2026 academic year. Get the dates from the Milton Keynes Council website and list all terms, half-terms, and INSET days.
```

---

### 4. Performance & Reviews Specialist (`performance-specialist.md`)
**Purpose**: Find academic performance data and parent reviews

**Data Sources**:
- DfE Performance Tables (compare-school-performance.service.gov.uk)
- Ofsted detailed inspection reports
- Parent review sites (SchoolGuide, Mumsnet)
- Council family information services

**Use Cases**:
- Get latest SATs/GCSE results for a school
- Extract Progress 8 scores for secondary schools
- Compare performance across multiple schools
- Find parent reviews and ratings
- Analyze historical performance trends

**Example Prompt**:
```
You are a Performance & Reviews Specialist Agent. Get the latest Key Stage 2 SATs results for Caroline Haslett Primary School (URN 110394). Include reading, writing, maths results and compare to national averages. Also find any parent reviews for this school.
```

---

### 5. UX Design Specialist (`ux-design-specialist.md`)
**Purpose**: World-class user experience design — make every page intuitive, beautiful, and effortless

**Expertise**:
- Progressive disclosure and visual hierarchy
- Mobile-first responsive design
- Micro-interactions and transitions
- Accessibility (WCAG 2.1 AA)
- Empty states, error states, and loading states
- Copy and microcopy review
- Comparison workflow optimisation
- Map UX (pin density, zoom, info panels)

**Use Cases**:
- Review a page for visual hierarchy, information density, and mobile responsiveness
- Audit a component for accessibility compliance
- Walk through a user flow and identify friction points
- Critique copy and microcopy for parent-friendliness
- Ensure design system consistency across pages

**Example Prompt**:
```
You are the UX Design Specialist Agent (see .claude/agents/ux-design-specialist.md). Review the SchoolDetail.tsx page for visual hierarchy, information density, and mobile responsiveness. Identify the top 5 UX issues and provide specific fixes.
```

---

## How to Use These Agents

### Method 1: Direct Task Tool Usage

In a Claude Code conversation, use the Task tool to invoke a specialist agent:

```
Use the Task tool with subagent_type="general-purpose" and provide the agent's specialty and task.
```

Example:
```
/task "You are an Ofsted Specialist Agent (see .claude/agents/ofsted-specialist.md). Find the current Ofsted rating for Caroline Haslett Primary School URN 110394."
```

### Method 2: Ralph Wiggum Loop

Add to `.claude/ralph-wiggum/USE_CASES.md`:

```bash
/ralph-loop "You are an Ofsted Specialist Agent. Download the latest Ofsted MI CSV, extract ratings for all Milton Keynes schools, and update the database ofsted_rating and ofsted_date fields. Verify all updates." --completion-promise "OFSTED_UPDATED" --max-iterations 20
```

### Method 3: Natural Language Request

Simply ask Claude Code in natural language, and it will recognize the task and use the appropriate specialist agent:

```
"Can you find the Ofsted rating for Caroline Haslett Primary School?"
```

Claude will automatically reference the Ofsted specialist agent configuration and search accordingly.

---

## Agent Design Principles

All specialist agents follow these principles:

1. **Authoritative Sources First**: Always use official UK government sources (Ofsted, DfE, GIAS) as primary sources
2. **URN-Based Matching**: Use Unique Reference Numbers (URN) for reliable school identification
3. **Data Validation**: Cross-reference multiple sources and flag outdated or suspicious data
4. **Structured Output**: Return data in JSON format for easy database integration
5. **Source Attribution**: Always include source URLs for verification
6. **Graceful Fallbacks**: If primary source fails, try secondary sources or manual search strategies

---

## Integration with School Finder Database

Each agent is designed to output data that maps directly to the School Finder database schema:

- **Ofsted Agent** → `schools.ofsted_rating`, `schools.ofsted_date`
- **Clubs Agent** → `school_clubs` table
- **Term Times Agent** → `school_term_dates` table
- **Performance Agent** → `school_performance`, `school_reviews` tables
- **UX Design Agent** → `frontend/src/pages/*.tsx`, `frontend/src/components/*.tsx` (reviews, not data)

The agents provide structured JSON output that can be directly inserted or used to update the SQLite database via the repository layer.

---

## Tips for Best Results

1. **Always provide URN when known** - it's the most reliable identifier
2. **Specify the council/location** - helps narrow searches and validate results
3. **Request specific data fields** - the more specific your prompt, the better the output
4. **Ask for source URLs** - enables verification and manual checking
5. **Use for verification** - great for checking database data against official sources
6. **Combine agents** - e.g., "Find Ofsted rating AND performance data AND clubs for school X"

---

## Future Agent Ideas

Potential additional specialist agents:
- **SEND Specialist** - Find special educational needs provisions
- **Admissions Specialist** - Extract admissions policies and criteria
- **Transport Specialist** - Find school bus routes and transport links
- **Catchment Specialist** - Determine catchment areas from council maps
- **League Table Specialist** - Create custom rankings based on multiple criteria

---

## Contributing

To add a new specialist agent:

1. Create a new `.md` file in this directory
2. Follow the template structure used by existing agents
3. Define: Purpose, Data Sources, Capabilities, Search Strategies, Output Format
4. Add usage examples and integration notes
5. Update this README with the new agent
6. Test with real prompts to ensure Claude can use it effectively
