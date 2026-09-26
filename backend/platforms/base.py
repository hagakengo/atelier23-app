from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Order:
    """Platform-agnostic order object"""
    order_id: str
    item_title: str
    sold_price: float
    sold_at: datetime
    item_id: Optional[str] = None
    quantity: int = 1
    platform: str = "unknown"


class PlatformAdapter(ABC):
    """Base class for platform adapters (eBay, Amazon, Mercari, etc.)"""

    def __init__(self, platform_name: str):
        self.platform_name = platform_name

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the platform"""
        pass

    @abstractmethod
    async def fetch_orders(self, since: datetime) -> List[Order]:
        """Fetch orders from the platform since the given datetime"""
        pass

    @abstractmethod
    async def get_order_details(self, order_id: str) -> Optional[Order]:
        """Get detailed information for a specific order"""
        pass

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Validate that credentials are valid"""
        pass
