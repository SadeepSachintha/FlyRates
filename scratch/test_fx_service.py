import asyncio
import os
import json
import time
from services.fx_service import fx_service, CACHE_FILE

async def test_fx_service():
    print("==================================================")
    print("        VERIFYING NEW FXSERVICE ARCHITECTURE")
    print("==================================================")

    # 1. Clean up existing rate cache to test cold startup
    if os.path.exists(CACHE_FILE):
        print(f"Removing existing cache file: {CACHE_FILE}")
        os.remove(CACHE_FILE)
    
    # Reload empty cache
    fx_service.load_cache()
    print("Cache has been cleared in memory and on disk.\n")

    # 2. Test cold fetch of USD -> LKR (should trigger CBSL scraping)
    print("--- 1. Cold Fetch USD -> LKR (CBSL Scraper check) ---")
    start_time = time.time()
    rate_usd = await fx_service.get_rate("USD", "LKR")
    elapsed = time.time() - start_time
    print(f"USD -> LKR Rate: {rate_usd} (Fetched in {elapsed:.4f} seconds)")
    assert rate_usd is not None and rate_usd > 200, f"Expected valid LKR rate, got: {rate_usd}"
    print("Cold fetch PASSED.\n")

    # 3. Test subsequent fetches for other currencies (should all be instant Cache HITs!)
    print("--- 2. Instant Cache Hits for EUR, GBP, AUD, JPY ---")
    currencies = ["EUR", "GBP", "AUD", "JPY", "INR", "CNY", "SAR", "AED"]
    for cur in currencies:
        start_time = time.time()
        rate = await fx_service.get_rate(cur, "LKR")
        elapsed = time.time() - start_time
        print(f"  {cur} -> LKR Rate: {rate} (Cache HIT resolved in {elapsed * 1000:.4f} ms)")
        assert rate is not None and rate > 0, f"Expected valid rate for {cur}, got: {rate}"
        assert elapsed < 0.05, f"Expected cache hit to resolve instantly, took {elapsed:.4f}s"
    print("Instant Cache Hits PASSED.\n")

    # 4. Check persistence on disk
    print("--- 3. Disk Cache Persistence (rate_cache.json) ---")
    assert os.path.exists(CACHE_FILE), "Cache file should be saved on disk"
    with open(CACHE_FILE, "r") as f:
        cache_data = json.load(f)
    print(f"Cache file contains {len(cache_data)} entries.")
    print("Sample cache content keys:", list(cache_data.keys())[:5])
    print("Cache Persistence PASSED.\n")

    # 5. Test cross-rate bridge derivation (USD -> EUR)
    print("--- 4. Bridge Rate Calculation (USD -> EUR) ---")
    start_time = time.time()
    cross_rate = await fx_service.get_rate("USD", "EUR")
    elapsed = time.time() - start_time
    # Should be mathematically derived: USD_LKR / EUR_LKR = 324.7184 / 378.3294 = ~0.858
    usd_lkr = cache_data.get("USD_LKR", {}).get("rate")
    eur_lkr = cache_data.get("EUR_LKR", {}).get("rate")
    expected_cross = usd_lkr / eur_lkr
    print(f"Derived USD -> EUR Rate: {cross_rate} (Expected: {expected_cross})")
    print(f"Resolved in {elapsed * 1000:.4f} ms")
    assert abs(cross_rate - expected_cross) < 1e-4, "Derived rate mismatch"
    print("Bridge Rate Calculation PASSED.\n")

    # 6. Test Cache Expiration and Stale Fallback
    print("--- 5. Cache Expiration & Stale Fallback ---")
    # Manually expire the cache in memory by setting timestamps to 0
    for key in fx_service.cache:
        fx_service.cache[key]["timestamp"] = 0
    
    # We will simulate a network/scraping failure by temporarily breaking CBSL URL
    original_fetch = fx_service.fetch_cbsl_rates
    async def broken_fetch():
        print("    [Simulated Scraper Failure]")
        return False
    fx_service.fetch_cbsl_rates = broken_fetch

    print("Cache is expired. External scraper is simulated as down.")
    start_time = time.time()
    stale_rate = await fx_service.get_rate("USD", "LKR")
    elapsed = time.time() - start_time
    print(f"Stale Fallback USD -> LKR Rate: {stale_rate} (Resolved in {elapsed:.4f}s)")
    assert stale_rate == rate_usd, "Stale rate should equal last fetched rate"
    print("Stale Fallback PASSED.\n")

    # Restore original methods
    fx_service.fetch_cbsl_rates = original_fetch

    print("==================================================")
    print("           ALL FXSERVICE TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(test_fx_service())
