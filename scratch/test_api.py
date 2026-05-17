import asyncio
import aiohttp

async def main():
    url = "https://open.er-api.com/v6/latest/USD"
    print(f"Fetching free open API: {url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                print(f"Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print("Success! Keys in response:", data.keys())
                    print("Base code:", data.get("base_code"))
                    rates = data.get("rates", {})
                    print("Sample rates:")
                    for cur in ["USD", "EUR", "GBP", "LKR", "JPY"]:
                        print(f"  {cur}: {rates.get(cur)}")
                else:
                    print(f"Error body: {await response.text()}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
