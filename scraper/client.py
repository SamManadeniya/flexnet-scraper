import asyncio
import logging
import random
from typing import Optional
import httpx
import config

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
]

class FlexnetHttpClient:
    def __init__(self, concurrency: int = config.DEFAULT_CONCURRENCY):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=config.TIMEOUT_SECONDS,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=30)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    def _get_headers(self, referer: Optional[str] = None) -> dict:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1"
        }
        if referer:
            headers["Referer"] = referer
        else:
            headers["Referer"] = config.SEARCH_URL
        return headers

    async def get(self, url: str, referer: Optional[str] = None) -> Optional[str]:
        """Fetch URL with retries, exponential backoff and polite delay."""
        if not self.client:
            raise RuntimeError("FlexnetHttpClient must be used within 'async with' context")

        async with self.semaphore:
            for attempt in range(1, config.MAX_RETRIES + 1):
                try:
                    # Random small jitter delay to avoid exact pattern detection
                    await asyncio.sleep(config.REQUEST_DELAY_SECONDS + random.uniform(0.1, 0.3))
                    
                    response = await self.client.get(
                        url,
                        headers=self._get_headers(referer=referer)
                    )

                    if response.status_code == 200:
                        return response.text
                    elif response.status_code == 429:
                        wait_time = attempt * 3.0
                        logger.warning(f"Rate limited (429) on {url}. Backing off for {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    elif response.status_code in [404, 410]:
                        logger.warning(f"Vehicle or page not found ({response.status_code}): {url}")
                        return None
                    else:
                        logger.warning(f"HTTP {response.status_code} for {url} on attempt {attempt}")

                except (httpx.RequestError, httpx.TimeoutException) as e:
                    logger.warning(f"Network error on attempt {attempt} for {url}: {e}")
                    await asyncio.sleep(attempt * 1.5)

            logger.error(f"Failed to fetch {url} after {config.MAX_RETRIES} attempts.")
            return None
