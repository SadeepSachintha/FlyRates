import asyncio
import aiohttp
import socket
import re

async def main():
    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    url = "https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        print(f"Fetching: {url}")
        try:
            async with session.get(url, timeout=10) as r:
                print(f"Status: {r.status}")
                if r.status == 200:
                    text = await r.text()
                    print(f"Total length: {len(text)}")
                    
                    # Search for tables, classes, or terms
                    tables = re.findall(r'<table[^>]*>', text, re.IGNORECASE)
                    print(f"Number of <table...> tags found: {len(tables)}")
                    for t in tables[:10]:
                        print("  Table tag:", t)
                        
                    # Let's search for "USD" or "United States" or "LKR"
                    for term in ["USD", "LKR", "Dollar", "Euro", "GBP", "AUD", "JPY", "iframe"]:
                        matches = list(re.finditer(term, text, re.IGNORECASE))
                        print(f"Occurrences of '{term}': {len(matches)}")
                        if matches:
                            # Print context for first match
                            idx = matches[0].start()
                            context = text[max(0, idx-100):min(len(text), idx+100)]
                            print(f"  First match context: {repr(context)}")
                else:
                    print(f"Failed: {r.status}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
