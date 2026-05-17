import asyncio
import aiohttp
import socket
import re

async def main():
    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    url = "https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        print(f"Fetching: {url}")
        try:
            async with session.get(url, timeout=10) as r:
                if r.status == 200:
                    text = await r.text()
                    print(f"Length of response: {len(text)}")
                    
                    # Print first 2000 characters
                    print("\n--- FIRST 2000 CHARACTERS ---")
                    print(text[:2000])
                    
                    # Print any table tags or scripts
                    print("\n--- DETECTED TAGS / PATTERNS ---")
                    print("Table tags:", re.findall(r'<table[^>]*>', text, re.IGNORECASE))
                    print("Script tags:", re.findall(r'<script[^>]*>', text, re.IGNORECASE))
                    
                    # Let's search for USD or Euro or LKR
                    for term in ["USD", "LKR", "Dollar", "Euro", "GBP", "AUD", "JPY"]:
                        matches = list(re.finditer(term, text, re.IGNORECASE))
                        print(f"Occurrences of '{term}': {len(matches)}")
                else:
                    print(f"Failed: {r.status}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
