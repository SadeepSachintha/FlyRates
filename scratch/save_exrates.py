import asyncio
import aiohttp
import socket

async def main():
    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    url = "https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        try:
            async with session.get(url, timeout=10) as r:
                if r.status == 200:
                    text = await r.text()
                    with open("scratch/exrates.html", "w", encoding="utf-8") as f:
                        f.write(text)
                    print("Successfully wrote exrates.php to scratch/exrates.html")
                else:
                    print(f"Failed with status: {r.status}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
