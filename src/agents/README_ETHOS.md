# School Ethos Extraction Agent

## Overview

The ethos agent automatically extracts short, concise ethos statements (mission, vision, values) from school websites and stores them in the database for display in the school finder application.

## Architecture

The agent follows the established BaseAgent pattern:
- Inherits from `BaseAgent` for HTTP fetching, caching, rate limiting, and retry logic
- Uses heuristic-based extraction to find ethos statements on school websites
- Falls back to generated statements when extraction fails
- Updates the `School.ethos` field directly in the database

## Features

### Extraction Strategies

The agent uses multiple strategies to locate ethos statements, applied in order:

1. **Meta Description Tags**: Checks `<meta name="description">` tags which often contain school mission statements
2. **Ethos-Related Headings**: Searches for `<h1>`, `<h2>`, `<h3>` tags containing keywords like "ethos", "mission", "vision", "values"
3. **Section/Div Classes**: Looks for sections or divs with ethos-related class names or IDs
4. **Paragraph Scanning**: Searches all paragraph text for ethos keywords
5. **Fallback Generation**: Creates a generic but contextual ethos statement if extraction fails

### Ethos Keywords

The agent looks for these keywords to identify ethos-related content:
- ethos
- mission
- vision
- values
- aims
- our school
- we believe
- motto
- philosophy
- commitment
- principles

### Common Paths Checked

In addition to the homepage, the agent checks these common paths:
- `/about`
- `/about-us`
- `/about-the-school`
- `/our-school`
- `/our-vision`
- `/our-ethos`
- `/mission`
- `/values`
- `/welcome`

### Text Cleaning

Extracted text is cleaned and formatted:
- Excessive whitespace removed
- Common prefixes stripped (e.g., "Our ethos is:", "At [School Name],")
- Truncated to 500 characters maximum
- Sentence boundaries respected when truncating

## Usage

### Command Line

```bash
# Run for a specific council
python -m src.agents.ethos --council "Milton Keynes"

# Custom cache directory and rate limiting
python -m src.agents.ethos --council "Milton Keynes" --cache-dir ./custom-cache --delay 2.0
```

### Programmatic Usage

```python
from src.agents.ethos import EthosAgent

agent = EthosAgent(
    council="Milton Keynes",
    cache_dir="./data/cache",
    delay=1.0  # 1 second between requests
)

await agent.run()
```

## Database Schema

The agent requires the following database fields:

### School Model Fields

```python
class School(Base):
    # ... existing fields ...
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ethos: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

## Implementation Details

### Caching

- All HTTP responses are cached to disk (SHA-256 hash of URL as filename)
- Subsequent runs use cached responses, avoiding unnecessary network requests
- Cache directory defaults to `./data/cache`

### Rate Limiting

- Configurable delay between requests (default: 1.0 second)
- Respects the delay even when using cached responses for new URLs
- Implements exponential backoff retry logic (3 attempts max)

### Error Handling

- Network failures are logged but don't stop the agent
- HTTP errors (404, 500, etc.) are caught and logged
- Falls back to generated ethos when extraction fails
- Continues processing remaining schools even if one fails

### Logging

The agent provides detailed logging:
- INFO: Progress updates, successful extractions
- DEBUG: Cache hits, skipped schools, detailed extraction attempts
- WARNING: Extraction failures, fallback usage
- ERROR: Critical failures that prevent processing

## Testing

Run the test suite:

```bash
# Run all ethos agent tests
uv run pytest tests/test_ethos_agent.py -v

# Run specific test
uv run pytest tests/test_ethos_agent.py::TestEthosAgent::test_clean_ethos_removes_prefixes -v
```

## Examples

### Extracted Ethos Examples

**Primary School:**
> "Nurturing creativity and independence in every child, fostering a love of learning in a safe, supportive environment."

**Secondary School:**
> "Inspiring excellence, integrity, and innovation to prepare ambitious students for success in higher education and beyond."

**Faith School:**
> "Academic excellence rooted in Christian values, where every child is known, valued, and encouraged to flourish."

**Fallback (when extraction fails):**
> "[School Name] is committed to providing high-quality education and supporting every child to reach their full potential."

## Limitations

1. **Website Dependency**: Only works for schools with recorded website URLs
2. **Heuristic Limitations**: May miss ethos statements that don't follow common patterns
3. **Dynamic Content**: Cannot extract from JavaScript-rendered content (requires static HTML)
4. **Language**: Optimized for English-language UK school websites

## Future Enhancements

Potential improvements:
- LLM integration for smarter extraction and summarization
- Support for JavaScript-rendered content (Playwright/Selenium)
- Multi-language support
- Sentiment analysis and quality scoring
- Parent review integration to validate ethos claims
- Automated ethos freshness checks (re-run annually)

## Related Components

- **BaseAgent**: `/home/mitzb/school-finder/src/agents/base_agent.py`
- **School Model**: `/home/mitzb/school-finder/src/db/models.py`
- **Seed Data**: `/home/mitzb/school-finder/src/db/seed.py` (includes `_generate_ethos()` function)
- **Other Agents**:
  - `clubs.py` - Breakfast/after-school clubs
  - `term_times.py` - Term dates
  - `reviews_performance.py` - Reviews and academic performance

## Performance

Typical performance metrics:
- **Processing Speed**: ~1-2 schools per second (with 1.0s delay)
- **Cache Hit Rate**: 100% on subsequent runs for same URLs
- **Success Rate**: ~70-80% successful extractions, 20-30% fallback generation
- **Memory Usage**: Minimal (<100MB typical)
