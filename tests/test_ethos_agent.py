"""Tests for the ethos agent."""

from __future__ import annotations

import pytest

from src.agents.ethos import EthosAgent


class TestEthosAgent:
    """Test suite for EthosAgent."""

    def test_ethos_agent_initialization(self):
        """Test that EthosAgent can be initialized."""
        agent = EthosAgent(council="Milton Keynes", cache_dir="./data/cache", delay=0.5)
        assert agent.council == "Milton Keynes"
        assert agent.delay == 0.5

    def test_clean_ethos_removes_prefixes(self):
        """Test that _clean_ethos removes common prefixes."""
        agent = EthosAgent(council="Test")

        text = "Our ethos is: We believe in nurturing every child to reach their full potential."
        result = agent._clean_ethos(text)
        assert result == "We believe in nurturing every child to reach their full potential."

        text = "At Test School, we are committed to excellence."
        result = agent._clean_ethos(text)
        assert result == "we are committed to excellence."

    def test_clean_ethos_truncates_long_text(self):
        """Test that _clean_ethos truncates text longer than 500 chars."""
        agent = EthosAgent(council="Test")

        long_text = "A" * 600
        result = agent._clean_ethos(long_text)
        assert len(result) <= 500
        assert result.endswith("...")

    def test_clean_ethos_preserves_short_text(self):
        """Test that _clean_ethos preserves short text."""
        agent = EthosAgent(council="Test")

        text = "Nurturing every child to reach their full potential."
        result = agent._clean_ethos(text)
        assert result == text

    def test_generate_fallback_ethos(self):
        """Test that _generate_fallback_ethos creates a valid fallback."""
        agent = EthosAgent(council="Test")

        result = agent._generate_fallback_ethos("Test Primary School")
        assert "Test Primary School" in result
        assert "education" in result
        assert len(result) > 30
        assert len(result) <= 500

    @pytest.mark.asyncio
    async def test_parse_ethos_from_meta_description(self):
        """Test that _parse_ethos can extract from meta description tag."""
        agent = EthosAgent(council="Test")

        html = """
        <html>
        <head>
            <meta name="description" content="We are a thriving school community committed to excellence.">
        </head>
        <body>
            <h1>Welcome</h1>
        </body>
        </html>
        """

        soup = agent.parse_html(html)
        result = agent._parse_ethos(soup)
        assert result is not None
        assert "thriving school" in result
        assert "excellence" in result

    @pytest.mark.asyncio
    async def test_parse_ethos_from_heading_with_keywords(self):
        """Test that _parse_ethos can extract from headings with ethos keywords."""
        agent = EthosAgent(council="Test")

        html = """
        <html>
        <body>
            <h2>Our Ethos</h2>
            <p>We believe in fostering curiosity, creativity, and critical thinking in every child.</p>
        </body>
        </html>
        """

        soup = agent.parse_html(html)
        result = agent._parse_ethos(soup)
        assert result is not None
        assert "fostering curiosity" in result or "curiosity" in result

    @pytest.mark.asyncio
    async def test_parse_ethos_from_paragraph_with_keywords(self):
        """Test that _parse_ethos can extract from paragraphs with ethos keywords."""
        agent = EthosAgent(council="Test")

        html = """
        <html>
        <body>
            <div>
                <p>Our mission is to inspire and empower every student to reach their full potential.</p>
            </div>
        </body>
        </html>
        """

        soup = agent.parse_html(html)
        result = agent._parse_ethos(soup)
        assert result is not None
        assert "inspire" in result or "empower" in result

    @pytest.mark.asyncio
    async def test_parse_ethos_returns_none_for_no_ethos(self):
        """Test that _parse_ethos returns None when no ethos found."""
        agent = EthosAgent(council="Test")

        html = """
        <html>
        <body>
            <h1>School News</h1>
            <p>Today is a sunny day.</p>
        </body>
        </html>
        """

        soup = agent.parse_html(html)
        result = agent._parse_ethos(soup)
        assert result is None
