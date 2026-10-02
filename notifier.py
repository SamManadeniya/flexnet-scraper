import logging
import httpx
from typing import Any, Dict, List, Optional
import config

logger = logging.getLogger(__name__)

class WebhookNotifier:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or config.GOOGLE_SHEETS_WEBHOOK_URL

    async def send_summary(self, summary_data: Dict[str, Any]) -> bool:
        """Send a scrape run summary to the Google Sheets / Apps Script webhook."""
        if not self.webhook_url:
            return False

        payload = {
            "type": "scrape_summary",
            "source": "Flexnet Japan Scraper",
            **summary_data
        }

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.post(self.webhook_url, json=payload)
                if response.status_code in [200, 201, 302]:
                    logger.info("Successfully sent scrape summary to Google Sheets webhook.")
                    return True
                else:
                    logger.warning(f"Google Sheets webhook returned status code: {response.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"Failed to deliver webhook notification: {e}")
            return False

    async def send_new_cars(self, cars: List[Dict[str, Any]]) -> bool:
        """Send individual new car records to the Google Sheets webhook."""
        if not self.webhook_url or not cars:
            return False

        payload = {
            "type": "new_vehicles",
            "count": len(cars),
            "vehicles": [
                {
                    "kanri_code": c.get("kanri_code"),
                    "title": c.get("title"),
                    "total_price": c.get("total_price"),
                    "year": c.get("model_year"),
                    "mileage": c.get("mileage_raw"),
                    "store": c.get("store_name"),
                    "url": c.get("detail_url")
                }
                for c in cars[:100] # Cap batch to avoid giant payloads
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.post(self.webhook_url, json=payload)
                return response.status_code in [200, 201, 302]
        except Exception as e:
            logger.warning(f"Failed to deliver new cars to webhook: {e}")
            return False

notifier = WebhookNotifier()
