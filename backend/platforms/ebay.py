import os
import logging
from datetime import datetime
from typing import List, Optional
import requests
from .base import PlatformAdapter, Order

logger = logging.getLogger(__name__)


class EBayAdapter(PlatformAdapter):
    """eBay API adapter for order synchronization"""

    def __init__(self):
        super().__init__("ebay")
        self.api_key = os.getenv("EBAY_API_KEY")
        self.api_secret = os.getenv("EBAY_API_SECRET")
        self.refresh_token = os.getenv("EBAY_REFRESH_TOKEN")
        self.access_token = None
        self.token_expiry = None
        self.base_url = "https://api.ebay.com"

    async def authenticate(self) -> bool:
        """Authenticate and get access token using refresh token"""
        if not all([self.api_key, self.api_secret, self.refresh_token]):
            logger.error("eBay credentials not configured")
            return False

        try:
            token_url = f"{self.base_url}/identity/v1/oauth2/token"

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {self._encode_credentials()}"
            }

            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "scope": "https://api.ebay.com/oauth/api_scope/sell.fulfillment"
            }

            response = requests.post(token_url, headers=headers, data=data, timeout=10)
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            self.token_expiry = datetime.now().timestamp() + expires_in

            logger.info("eBay authentication successful")
            return True

        except Exception as e:
            logger.error(f"eBay authentication failed: {str(e)}")
            return False

    async def fetch_orders(self, since: datetime) -> List[Order]:
        """Fetch fulfilled orders from eBay since the given time"""
        if not self.access_token:
            if not await self.authenticate():
                return []

        try:
            # eBay Orders API endpoint
            orders_url = f"{self.base_url}/sell/fulfillment/v1/order"

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            # Filter for fulfilled orders since the given time
            iso_time = since.isoformat()
            filter_param = f"orderfulfillmentstatus:{{FULFILLED}} AND createdat:[{iso_time} TO *]"

            params = {
                "filter": filter_param,
                "limit": 200,
                "offset": 0
            }

            orders = []
            offset = 0

            while True:
                params["offset"] = offset
                response = requests.get(orders_url, headers=headers, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()
                order_summaries = data.get("orders", [])

                if not order_summaries:
                    break

                for order_summary in order_summaries:
                    order = self._parse_order(order_summary)
                    if order:
                        orders.append(order)

                # Check if there are more pages
                total = data.get("total", 0)
                offset += len(order_summaries)
                if offset >= total:
                    break

            logger.info(f"Fetched {len(orders)} orders from eBay")
            return orders

        except Exception as e:
            logger.error(f"Failed to fetch eBay orders: {str(e)}")
            return []

    async def get_order_details(self, order_id: str) -> Optional[Order]:
        """Get detailed information for a specific eBay order"""
        if not self.access_token:
            if not await self.authenticate():
                return None

        try:
            url = f"{self.base_url}/sell/fulfillment/v1/order/{order_id}"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            return self._parse_order(response.json())

        except Exception as e:
            logger.error(f"Failed to fetch eBay order details for {order_id}: {str(e)}")
            return None

    async def validate_credentials(self) -> bool:
        """Validate eBay credentials"""
        return await self.authenticate()

    def _encode_credentials(self) -> str:
        """Encode API key and secret for Basic auth"""
        import base64
        credentials = f"{self.api_key}:{self.api_secret}"
        return base64.b64encode(credentials.encode()).decode()

    def _parse_order(self, order_data: dict) -> Optional[Order]:
        """Parse eBay order response into Order object"""
        try:
            order_id = order_data.get("orderId")
            if not order_id:
                return None

            # Get line items (items in the order)
            line_items = order_data.get("lineItems", [])
            if not line_items:
                return None

            item = line_items[0]  # Use first item for now
            total_price = float(order_data.get("pricingSummary", {}).get("total", {}).get("value", 0))
            create_date = order_data.get("creationDate", datetime.now().isoformat())

            return Order(
                order_id=order_id,
                item_title=item.get("title", "Unknown"),
                sold_price=total_price,
                sold_at=datetime.fromisoformat(create_date.replace('Z', '+00:00')),
                item_id=item.get("itemId"),
                quantity=item.get("quantity", 1),
                platform="ebay"
            )

        except Exception as e:
            logger.error(f"Failed to parse eBay order: {str(e)}")
            return None
