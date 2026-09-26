import logging
from datetime import datetime
from typing import List, Optional
from .base import PlatformAdapter, Order

logger = logging.getLogger(__name__)


class MercariAdapter(PlatformAdapter):
    """Mercari adapter (placeholder for future implementation)"""

    def __init__(self):
        super().__init__("mercari")
        # TODO: Initialize with Mercari API credentials

    async def authenticate(self) -> bool:
        """Authenticate with Mercari API"""
        logger.info("Mercari adapter: authentication not yet implemented")
        return False

    async def fetch_orders(self, since: datetime) -> List[Order]:
        """Fetch fulfilled orders from Mercari"""
        logger.info("Mercari adapter: fetch_orders not yet implemented")
        return []

    async def get_order_details(self, order_id: str) -> Optional[Order]:
        """Get detailed information for a specific Mercari order"""
        logger.info(f"Mercari adapter: get_order_details not yet implemented for {order_id}")
        return None

    async def validate_credentials(self) -> bool:
        """Validate Mercari credentials"""
        return False
