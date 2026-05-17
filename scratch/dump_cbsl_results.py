import asyncio
import aiohttp
import socket

async def main():
    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    url = "https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates_results.php"
    
    data = {
        "lookupPage": "lookup_daily_exchange_rates.php",
        "startRange": "2006-11-11",
        "rangeType": "dates",
        "txtStart": "2026-05-15",
        "txtEnd": "2026-05-15"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://www.cbsl.gov.lk",
        "Referer": "https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates.php"
    }
    
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        print(f"POSTing to: {url}")
        try:
            async with session.post(url, data=data, timeout=15) as r:
                if r.status == 200:
                    text = await r.text()
                    print(f"Response length: {len(text)}")
                    print("\n--- FIRST 3000 CHARACTERS ---")
                    print(text[:3000])
                else:
                    print(f"POST request failed.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
