import socket
import aiohttp
import logging
from typing import Optional
from core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_CURRENCIES = {
    "USD", "GBP", "EUR", "AED", "SAR", 
    "AUD", "INR", "JPY", "CNY", "QAR", "LKR"
}

class FXService:
    def __init__(self):
        self.api_key = settings.fx_api_key
        # Using ExchangeRate-API as an example.
        self.base_url = f"https://v6.exchangerate-api.com/v6/{self.api_key}"

    def is_valid_currency(self, currency: str) -> bool:
        """Validates if the currency is supported in Phase 1."""
        return currency.upper() in ALLOWED_CURRENCIES

    async def get_rate(self, base_currency: str, target_currency: str) -> Optional[float]:
        """Fetches the real-time exchange rate."""
        base_currency = base_currency.upper()
        target_currency = target_currency.upper()

        if not self.is_valid_currency(base_currency) or not self.is_valid_currency(target_currency):
            logger.warning(f"Invalid currency pair requested: {base_currency}/{target_currency}")
            return None
            
        if not self.api_key:
            logger.error("FX_API_KEY is not set.")
            return None

        url = f"{self.base_url}/pair/{base_currency}/{target_currency}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("conversion_rate")
                    else:
                        logger.error(f"Failed to fetch rate. Status: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Exception during API call: {e}")
            return None

fx_service = FXService()
