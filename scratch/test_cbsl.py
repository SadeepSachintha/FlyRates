import asyncio
import aiohttp
from html.parser import HTMLParser
import socket

class CBSLTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_cell = []
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.cell_type = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
            self.current_table = []
        elif tag == 'tr' and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag in ('td', 'th') and self.in_row:
            self.in_cell = True
            self.cell_type = tag
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

async def main():
    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    
    urls = [
        "https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates",
        "https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates/daily-cbsl-exchange-rates",
        "https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates/daily-indicative-exchange-rates"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        for url in urls:
            print(f"\n======================================")
            print(f"Fetching: {url}")
            try:
                async with session.get(url, timeout=10) as r:
                    print(f"Status: {r.status}")
                    if r.status == 200:
                        text = await r.text()
                        
                        parser = CBSLTableParser()
                        parser.feed(text)
                        
                        print(f"Parsed {len(parser.tables)} tables.")
                        for idx, table in enumerate(parser.tables):
                            print(f"\n--- Table {idx+1} ---")
                            # Print first 10 rows
                            for r_idx, row in enumerate(table[:10]):
                                print(f"  Row {r_idx+1}: {row}")
                            if len(table) > 10:
                                print(f"  ... ({len(table) - 10} more rows)")
                    else:
                        print(f"Failed with status: {r.status}")
            except Exception as e:
                print(f"Error fetching {url}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
