import os
import json
import time
import socket
import logging
import aiohttp
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Tuple
from html.parser import HTMLParser
from core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_CURRENCIES = {
    "USD", "GBP", "EUR", "AED", "SAR", 
    "AUD", "INR", "JPY", "CNY", "QAR", "LKR"
}

# Resolve cache file path relative to this script's directory (resolves to project root/rate_cache.json)
CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rate_cache.json")
CACHE_TTL = 3600  # Cache duration in seconds (1 hour)

class CBSLTableParser(HTMLParser):
    """Custom light-weight HTML parser to extract tables from CBSL exrates results."""
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_cell = []
        self.in_table = False
        self.in_row = False
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
            self.current_table = []
        elif tag == 'tr' and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag in ('td', 'th') and self.in_row:
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag):
        if tag == 'table' and self.in_table:
            self.in_table = False
            self.tables.append(self.current_table)
        elif tag == 'tr' and self.in_row:
            self.in_row = False
            self.current_table.append(self.current_row)
        elif tag in ('td', 'th') and self.in_cell:
            self.in_cell = False
            text = "".join(self.current_cell).strip().replace('\n', ' ')
            self.current_row.append(text)

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell.append(data)


class FXService:
    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self.load_cache()

    def is_valid_currency(self, currency: str) -> bool:
        """Validates if the currency is supported."""
        return currency.upper() in ALLOWED_CURRENCIES

    def load_cache(self):
        """Loads rates cache from persistent JSON file on disk."""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                logger.info(f"Loaded {len(self.cache)} FX rates from cache file: {CACHE_FILE}")
            except Exception as e:
                logger.warning(f"Could not load persistent cache file: {e}")
                self.cache = {}
        else:
            self.cache = {}

    def save_cache(self):
        """Saves current rates cache to persistent JSON file on disk."""
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=4)
            logger.debug(f"Saved cache containing {len(self.cache)} rates to {CACHE_FILE}")
        except Exception as e:
            logger.warning(f"Could not save persistent cache file: {e}")

    def update_cache_entry(self, base: str, target: str, rate: float):
        """Helper to add or update an entry in the cache with the current timestamp."""
        key = f"{base.upper()}_{target.upper()}"
        self.cache[key] = {
            "rate": rate,
            "timestamp": time.time()
        }

    def get_cached_rate(self, base: str, target: str) -> Optional[float]:
        """Checks if a rate exists in the cache and is still valid (not expired)."""
        key = f"{base.upper()}_{target.upper()}"
        if key in self.cache:
            entry = self.cache[key]
            age = time.time() - entry.get("timestamp", 0)
            if age < CACHE_TTL:
                logger.debug(f"Cache HIT for rate {key}: {entry['rate']} (Age: {int(age)}s)")
                return entry["rate"]
            else:
                logger.debug(f"Cache EXPIRED for rate {key} (Age: {int(age)}s)")
        return None

    def get_stale_rate(self, base: str, target: str) -> Optional[float]:
        """Fallback to retrieve an expired cached rate in case all external sources fail."""
        key = f"{base.upper()}_{target.upper()}"
        if key in self.cache:
            entry = self.cache[key]
            logger.warning(f"Using STALE fallback rate for {key}: {entry['rate']}")
            return entry["rate"]
        return None

    async def fetch_cbsl_rates(self) -> bool:
        """
        Scrapes LKR exchange rates directly from the official Central Bank of Sri Lanka website.
        Fetches all major currencies in exactly one request and handles date backtracking for weekends/holidays.
        """
        url = "https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates_results.php"
        
        # Build form checkboxes for all allowed currencies to query them at once
        data_params = [
            ("lookupPage", "lookup_daily_exchange_rates.php"),
            ("startRange", "2006-11-11"),
            ("rangeType", "dates"),
            ("chk_cur[]", "USD~US Dollar"),
            ("chk_cur[]", "EUR~Euro"),
            ("chk_cur[]", "GBP~Sterling Pound"),
            ("chk_cur[]", "AUD~Australian Dollar"),
            ("chk_cur[]", "JPY~Japanese Yen"),
            ("chk_cur[]", "AED~UAE  Dirham"),
            ("chk_cur[]", "SAR~Saudi Arabian Riyal"),
            ("chk_cur[]", "INR~Indian Rupee"),
            ("chk_cur[]", "CNY~Chinese Yuan (Renminbi)"),
            ("chk_cur[]", "QAR~Qatar Riyal"),
            ("submit_button", "Submit")
        ]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin": "https://www.cbsl.gov.lk",
            "Referer": "https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates.php"
        }
        
        # Force IPv4 TCPConnector to bypass HF Spaces DNS/routing bugs
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        
        try:
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                today = datetime.now()
                
                # Backtrack up to 7 days to handle weekends/holidays when CBSL does not publish rates
                for i in range(8):
                    query_date = today - timedelta(days=i)
                    date_str = query_date.strftime("%Y-%m-%d")
                    logger.info(f"Scraping CBSL rates for date: {date_str}...")
                    
                    # Update date parameters dynamically in our form payload list
                    post_data = []
                    for k, v in data_params:
                        if k == "txtStart" or k == "txtEnd":
                            continue
                        post_data.append((k, v))
                    post_data.append(("txtStart", date_str))
                    post_data.append(("txtEnd", date_str))
                    
                    try:
                        async with session.post(url, data=post_data, timeout=10) as response:
                            if response.status == 200:
                                html_text = await response.text()
                                parser = CBSLTableParser()
                                parser.feed(html_text)
                                
                                has_parsed_any = False
                                for table in parser.tables:
                                    cleaned_rows = []
                                    for row in table:
                                        row_cleaned = [item.strip() for item in row if item.strip()]
                                        if row_cleaned:
                                            cleaned_rows.append(row_cleaned)
                                    
                                    # Each table contains [Header row, Data row]
                                    if len(cleaned_rows) > 1:
                                        header = cleaned_rows[0]
                                        data_row = cleaned_rows[1]
                                        
                                        # Parse currency, e.g. "1  USD  -> LKR"
                                        match = re.search(r'1\s+([A-Z]{3})\s+->', header[1])
                                        if match and len(data_row) >= 2:
                                            cur_code = match.group(1).upper()
                                            try:
                                                rate_val = float(data_row[1])
                                                # Save base_LKR rates in cache
                                                self.update_cache_entry(cur_code, "LKR", rate_val)
                                                # Also calculate LKR_base reciprocal
                                                self.update_cache_entry("LKR", cur_code, 1.0 / rate_val if rate_val > 0 else 0.0)
                                                has_parsed_any = True
                                            except ValueError:
                                                pass
                                
                                if has_parsed_any:
                                    logger.info(f"Successfully scraped CBSL rates for LKR on {date_str}.")
                                    self.save_cache()
                                    return True
                            else:
                                logger.warning(f"CBSL scrape post failed with status: {response.status}")
                    except Exception as e:
                        logger.error(f"Error making POST request to CBSL for {date_str}: {e}")
                        
                logger.warning("Failed to find any active exchange rates from CBSL in the last 7 days.")
                return False
        except Exception as e:
            logger.error(f"Global exception in fetch_cbsl_rates: {e}")
            return False

    async def get_rate(self, base_currency: str, target_currency: str) -> Optional[float]:
        """
        Retrieves real-time exchange rate with support for in-memory caching,
        disk persistence, CBSL web scraping, bridge-rate conversions, and robust multi-tiered fallbacks.
        """
        base = base_currency.upper()
        target = target_currency.upper()

        if not self.is_valid_currency(base) or not self.is_valid_currency(target):
            logger.warning(f"Invalid currency pair requested: {base}/{target}")
            return None

        # 1. Check Identity rate (e.g. USD -> USD)
        if base == target:
            return 1.0

        # 2. Check Cache
        cached_rate = self.get_cached_rate(base, target)
        if cached_rate is not None:
            return cached_rate

        # 3. Check if we can derive the rate mathematically using LKR as a bridge from cache.
        #    For any non-LKR conversion, if we have USD_LKR and EUR_LKR, rate(USD->EUR) = rate(USD->LKR) / rate(EUR->LKR)
        if base != "LKR" and target != "LKR":
            base_lkr = self.get_cached_rate(base, "LKR")
            target_lkr = self.get_cached_rate(target, "LKR")
            if base_lkr is not None and target_lkr is not None and target_lkr > 0:
                derived = base_lkr / target_lkr
                self.update_cache_entry(base, target, derived)
                logger.info(f"Derived cross rate {base}->{target} from cached LKR rates: {derived}")
                return derived

        # 4. Cache MISS: Retrieve fresh rates.
        # Since we are fully using web scraping, any cache miss should trigger CBSL scraper.
        # CBSL scraper fetches all rates (against LKR) and populates them into the cache.
        logger.info(f"Cache miss for {base}->{target}. Launching CBSL Web Scraper...")
        cbsl_success = await self.fetch_cbsl_rates()
        if cbsl_success:
            # Try to get rate directly from cache (if either is LKR)
            res = self.get_cached_rate(base, target)
            if res is not None:
                return res
            # Or try to derive cross rate mathematically if both are non-LKR
            if base != "LKR" and target != "LKR":
                base_lkr = self.get_cached_rate(base, "LKR")
                target_lkr = self.get_cached_rate(target, "LKR")
                if base_lkr is not None and target_lkr is not None and target_lkr > 0:
                    derived = base_lkr / target_lkr
                    self.update_cache_entry(base, target, derived)
                    self.save_cache()
                    logger.info(f"Derived cross rate {base}->{target} after CBSL scrape: {derived}")
                    return derived

        # 5. Total Failure: Fallback to stale/expired cached rate if it exists
        logger.warning(f"All live FX sources failed for {base}->{target}. Attempting stale cache fallback...")
        stale_rate = self.get_stale_rate(base, target)
        if stale_rate is not None:
            return stale_rate

        # If we failed to get a direct stale rate, try to compute it from stale LKR rates
        if base != "LKR" and target != "LKR":
            base_lkr_stale = self.get_stale_rate(base, "LKR")
            target_lkr_stale = self.get_stale_rate(target, "LKR")
            if base_lkr_stale is not None and target_lkr_stale is not None and target_lkr_stale > 0:
                derived = base_lkr_stale / target_lkr_stale
                self.update_cache_entry(base, target, derived)
                self.save_cache()
                logger.warning(f"Derived stale cross rate {base}->{target} from stale LKR rates: {derived}")
                return derived

        # 6. Absolute Failure: No rates available
        logger.critical(f"No rates available in memory, disk, or APIs for {base}->{target}!")
        return None

fx_service = FXService()
