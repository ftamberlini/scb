from app.runtime import MISSING, BoundedTTLCache, SlidingWindowRateLimiter


def test_bounded_cache_evicts_oldest_entry():
    cache = BoundedTTLCache(max_entries=2, ttl_seconds=60)
    cache.set("first", 1)
    cache.set("second", 2)
    cache.set("third", 3)
    assert cache.get("first") is MISSING
    assert cache.get("second") == 2
    assert len(cache) == 2


def test_rate_limiter_rejects_requests_over_limit():
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("client")
    assert limiter.allow("client")
    assert not limiter.allow("client")
