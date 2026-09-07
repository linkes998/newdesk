from unittest.mock import MagicMock

from src.newsdesk.models import Event, Style
from src.newsdesk.output import drafts_for, _template_draft


def test_drafts_for_template_mode():
    event = Event("Test News", "Summary here", "https://example.com", 5.0, ["crypto"])
    styles = {
        "x": Style.default("x"),
        "binance": Style.default("binance"),
        "okx": Style.default("okx"),
    }
    result = drafts_for(event, styles, llm_client=None)
    assert "x" in result
    assert "binance" in result
    assert "okx" in result
    assert all(len(v) > 0 for v in result.values())


def test_drafts_for_llm_mode():
    event = Event("Test News", "Summary here", "https://example.com", 5.0, ["crypto"])
    styles = {
        "x": Style.default("x"),
        "binance": Style.default("binance"),
        "okx": Style.default("okx"),
    }
    mock_client = MagicMock()
    mock_client.generate.return_value = "LLM generated content for this platform"
    mock_client._default_model = "test-model"

    result = drafts_for(event, styles, llm_client=mock_client)
    assert mock_client.generate.call_count == 3
    assert all(len(v) > 0 for v in result.values())


def test_drafts_for_llm_failure_fallback():
    event = Event("Test News", "Summary here", "https://example.com", 5.0, ["crypto"])
    styles = {
        "x": Style.default("x"),
        "binance": Style.default("binance"),
        "okx": Style.default("okx"),
    }
    mock_client = MagicMock()
    mock_client.generate.side_effect = Exception("API down")
    mock_client._default_model = "test-model"

    result = drafts_for(event, styles, llm_client=mock_client)
    assert all(len(v) > 0 for v in result.values())


def test_template_draft_x():
    event = Event("Bitcoin ETF Approved", "SEC approves spot Bitcoin ETF", "https://example.com", 7.0, ["crypto"])
    result = _template_draft(event, "x")
    assert "Bitcoin ETF Approved" in result
    assert "不是投资建议" in result


def test_template_draft_binance():
    event = Event("Bitcoin ETF Approved", "SEC approves spot Bitcoin ETF", "https://example.com", 7.0, ["crypto"])
    result = _template_draft(event, "binance")
    assert "先说结论" in result
    assert "$BTC $ETH" in result


def test_template_draft_okx():
    event = Event("Bitcoin ETF Approved", "SEC approves spot Bitcoin ETF", "https://example.com", 7.0, ["crypto"])
    result = _template_draft(event, "okx")
    assert "刚刷到" in result
    assert "#OKX星球话题来啦" in result
