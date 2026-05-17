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
                if r.status == 200:
                    text = await r.text()
                    
                    # Find all iframe tags and print their attributes, especially src
                    iframes = re.findall(r'<iframe[^>]*src="([^"]+)"[^>]*>', text, re.IGNORECASE)
                    print(f"Found {len(iframes)} iframes with src:")
                    for idx, src in enumerate(iframes):
                        print(f"  Iframe {idx+1}: {src}")
                        
                    # Also let's print the entire iframe tags to be sure we get everything
                    iframe_tags = re.findall(r'<iframe[^>]*>', text, re.IGNORECASE)
                    print(f"\nAll iframe tags:")
                    for idx, tag in enumerate(iframe_tags):
                        print(f"  Iframe Tag {idx+1}: {tag}")
                else:
                    print(f"Failed: {r.status}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
