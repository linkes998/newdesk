from pathlib import Path
from src.newsdesk.style import analyze_style, adapt_to_style, parse_samples
from src.newsdesk.models import Style


def test_analyze_style_empty():
    s = Style.default("test")
    assert s.avg_len == 180
    assert s.ticker_rate == 0.3


def test_analyze_style_with_posts():
    posts = [
        "BTC hits $100k! $BTC $ETH",
        "What do you think about ETH? 你怎么看？",
        "No emoji here, just facts",
    ]
    s = analyze_style("test", posts)
    assert s.avg_len > 0
    assert s.ticker_rate > 0
    assert s.question_rate > 0


def test_adapt_to_style_adds_ticker():
    s = Style("x", 50, 0.0, 0.5, 0.0, [])
    result = adapt_to_style("Just a fact", s, "x")
    assert "$BTC" in result


def test_adapt_to_style_adds_question():
    s = Style("x", 50, 0.0, 0.0, 0.5, [])
    result = adapt_to_style("Just a fact", s, "x")
    assert "你怎么看？" in result


def test_adapt_to_style_truncates_x():
    s = Style("x", 50, 0.0, 0.0, 0.0, [])
    long_text = "\n".join(f"Line {i}" for i in range(20))
    result = adapt_to_style(long_text, s, "x")
    assert len(result.split("\n")) <= 8


def test_adapt_to_style_truncates_okx():
    s = Style("okx", 50, 0.0, 0.0, 0.0, [])
    long_text = "x" * 500
    result = adapt_to_style(long_text, s, "okx")
    assert len(result) <= 473  # 470 + "…"


def test_parse_samples_nonexistent():
    result = parse_samples(Path("/nonexistent/path.txt"))
    assert result == []
