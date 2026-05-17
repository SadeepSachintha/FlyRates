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
    url = "https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates_results.php"
    
    # Use rangeType="range" and rangeValue="1" (Latest 1 day)
    data = [
        ("lookupPage", "lookup_daily_exchange_rates.php"),
        ("startRange", "2006-11-11"),
        ("rangeType", "range"),
        ("rangeValue", "1"),
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
    
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        print(f"POSTing to: {url} with Quick Date parameters...")
        try:
            async with session.post(url, data=data, timeout=15) as r:
                print(f"Status: {r.status}")
                if r.status == 200:
                    text = await r.text()
                    print(f"Response length: {len(text)}")
                    
                    parser = CBSLTableParser()
                    parser.feed(text)
                    print(f"Parsed {len(parser.tables)} tables.")
                    
                    for idx, table in enumerate(parser.tables):
                        print(f"\n--- Table {idx+1} ---")
                        for r_idx, row in enumerate(table):
                            row_cleaned = [item.strip() for item in row if item.strip()]
                            if row_cleaned:
                                print(f"  Row {r_idx+1}: {row_cleaned}")
                else:
                    print(f"POST request failed.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
