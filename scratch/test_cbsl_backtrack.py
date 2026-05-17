import asyncio
import aiohttp
from html.parser import HTMLParser
import socket
from datetime import datetime, timedelta

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

async def fetch_cbsl_rates_for_date(session, date_str):
    url = "https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates_results.php"
    
    data = [
        ("lookupPage", "lookup_daily_exchange_rates.php"),
        ("startRange", "2006-11-11"),
        ("rangeType", "dates"),
        ("txtStart", date_str),
        ("txtEnd", date_str),
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
    
    async with session.post(url, data=data, timeout=10) as r:
        if r.status == 200:
            text = await r.text()
            parser = CBSLTableParser()
            parser.feed(text)
            return parser.tables
        return []

async def get_latest_cbsl_rates():
    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        # Start with today and go backwards up to 7 days
        today = datetime.now()
        
        for i in range(8):
            query_date = today - timedelta(days=i)
            date_str = query_date.strftime("%Y-%m-%d")
            print(f"Trying date: {date_str}...")
            
            tables = await fetch_cbsl_rates_for_date(session, date_str)
            
            # Check if we parsed tables and at least one table has data rows (length > 1)
            has_data = False
            rates_dict = {}
            
            if tables:
                for table in tables:
                    cleaned_rows = []
                    for row in table:
                        row_cleaned = [item.strip() for item in row if item.strip()]
                        if row_cleaned:
                            cleaned_rows.append(row_cleaned)
                    
                    if len(cleaned_rows) > 1:
                        # We have a header row and a data row!
                        # E.g. Header: ['Date', '1 USD -> LKR', '1 LKR -> USD']
                        # Data: ['2026-05-15', '324.7184', '0.0031']
                        header = cleaned_rows[0]
                        data_row = cleaned_rows[1]
                        
                        # Extract currency code from header, e.g. "1  USD  -> LKR"
                        import re
                        match = re.search(r'1\s+([A-Z]{3})\s+->', header[1])
                        if match and len(data_row) >= 2:
                            cur_code = match.group(1)
                            try:
                                rate_val = float(data_row[1])
                                rates_dict[cur_code] = rate_val
                                has_data = True
                            except ValueError:
                                pass
            
            if has_data:
                print(f"SUCCESS! Found valid rates for date {date_str}:")
                for cur, val in rates_dict.items():
                    print(f"  {cur}: {val} LKR")
                return rates_dict
            else:
                print(f"No rates found for {date_str}.")
                
        print("Failed to find any CBSL rates in the last 7 days.")
        return {}

async def main():
    await get_latest_cbsl_rates()

if __name__ == "__main__":
    asyncio.run(main())
