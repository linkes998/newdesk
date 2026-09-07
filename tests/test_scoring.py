def test_score_event_crypto_only():
    from src.newsdesk.scoring import score_event
    score, tags = score_event("Bitcoin hits new high", "BTC breaks $100k resistance")
    assert "crypto" in tags
    assert "ai" not in tags
    assert score > 0


def test_score_event_ai_only():
    from src.newsdesk.scoring import score_event
    score, tags = score_event("OpenAI releases GPT-5", "Anthropic launches Claude 3.5")
    assert "ai" in tags
    assert "crypto" not in tags
    assert score > 0


def test_score_event_cross_tag():
    from src.newsdesk.scoring import score_event
    score, tags = score_event("AI agents trade crypto on-chain", "Autonomous agents execute DeFi swaps")
    assert "crypto" in tags
    assert "ai" in tags
    assert score >= 4.5


def test_score_event_skipped():
    from src.newsdesk.scoring import score_event
    score, tags = score_event("Guaranteed returns airdrop code", "Free crypto giveaway")
    assert score == 0
    assert tags == []


def test_score_event_no_match():
    from src.newsdesk.scoring import score_event
    score, tags = score_event("Local bakery opens new location", "Best sourdough in town")
    assert score < 2
    assert tags == []


def test_collect_events_returns_top_n():
    from src.newsdesk.scoring import collect_events
    events = collect_events()
    assert len(events) <= 8
    assert all(e.score >= 2 for e in events)
    assert events == sorted(events, key=lambda e: e.score, reverse=True)


def test_collect_events_deduplication():
    from src.newsdesk.scoring import collect_events
    events = collect_events()
    titles = [e.title[:40] for e in events]
    assert len(titles) == len(set(titles))
