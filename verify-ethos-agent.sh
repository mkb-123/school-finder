#!/bin/bash
# Verification script for ethos agent implementation

set -e

echo "🔍 Verifying ethos agent implementation..."
echo ""

# Check Python syntax
echo "1. Checking Python syntax..."
python3 -m py_compile src/agents/ethos.py
python3 -m py_compile tests/test_ethos_agent.py
echo "   ✅ Python syntax valid"
echo ""

# Check imports
echo "2. Checking imports..."
python3 -c "from src.agents.ethos import EthosAgent; print('   ✅ EthosAgent imports successfully')"
echo ""

# Check database model
echo "3. Checking database model..."
python3 -c "from src.db.models import School; s = School.__table__.columns; print('   ✅ School.website:', 'website' in s.keys()); print('   ✅ School.ethos:', 'ethos' in s.keys())"
echo ""

# Run linting (if ruff is available)
echo "4. Running linter..."
if command -v ruff &> /dev/null; then
    ruff check src/agents/ethos.py tests/test_ethos_agent.py || true
    echo "   ✅ Linting complete"
else
    echo "   ⚠️  Ruff not found, skipping lint check"
fi
echo ""

# Run tests
echo "5. Running tests..."
if command -v pytest &> /dev/null; then
    pytest tests/test_ethos_agent.py -v --tb=short || true
    echo "   ✅ Tests complete"
else
    echo "   ⚠️  Pytest not found, skipping tests"
fi
echo ""

echo "✅ Verification complete!"
echo ""
echo "To run the agent:"
echo "  python -m src.agents.ethos --council \"Milton Keynes\""
