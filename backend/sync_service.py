import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
from platforms import EBayAdapter, AmazonAdapter, MercariAdapter, PlatformAdapter
from main import SaleRecord, SyncHistory, PendingSales, SessionLocal

logger = logging.getLogger(__name__)


class SyncService:
    """Service to synchronize sales from multiple platforms"""

    def __init__(self):
        self.adapters = {
            "ebay": EBayAdapter(),
            "amazon": AmazonAdapter(),
            "mercari": MercariAdapter(),
        }

    async def sync_all_platforms(self):
        """Synchronize sales from all configured platforms"""
        db = SessionLocal()
        try:
            for platform_name, adapter in self.adapters.items():
                await self.sync_platform(platform_name, adapter, db)
        finally:
            db.close()

    async def sync_platform(self, platform_name: str, adapter: PlatformAdapter, db: Session):
        """Synchronize sales from a specific platform"""
        try:
            # Get last sync time
            sync_history = db.query(SyncHistory).filter(
                SyncHistory.platform == platform_name
            ).first()

            since = datetime.now() - timedelta(days=1)
            if sync_history and sync_history.last_sync_time:
                since = sync_history.last_sync_time

            logger.info(f"Syncing {platform_name} since {since}")

            # Validate credentials
            if not await adapter.validate_credentials():
                logger.error(f"Failed to validate credentials for {platform_name}")
                self._update_sync_history(db, platform_name, "failed", "Invalid credentials")
                return

            # Fetch orders
            orders = await adapter.fetch_orders(since)
            logger.info(f"Fetched {len(orders)} orders from {platform_name}")

            # Process each order
            synced_count = 0
            for order in orders:
                if self._create_or_match_sale(db, order):
                    synced_count += 1

            # Update sync history
            self._update_sync_history(db, platform_name, "success", None, synced_count)
            logger.info(f"Successfully synced {synced_count} orders from {platform_name}")

        except Exception as e:
            logger.error(f"Error syncing {platform_name}: {str(e)}")
            self._update_sync_history(db, platform_name, "failed", str(e))

    def _create_or_match_sale(self, db: Session, order) -> bool:
        """Create or match a sale record for an order"""
        try:
            # Check if order already exists
            existing = db.query(SaleRecord).filter(
                SaleRecord.platform_order_id == f"{order.platform}:{order.order_id}"
            ).first()

            if existing:
                logger.info(f"Order {order.platform}:{order.order_id} already exists")
                return False

            # Try to match with existing card by name
            from main import Card
            matching_card = db.query(Card).filter(
                Card.name.ilike(f"%{order.item_title}%")
            ).first()

            if matching_card:
                # Create sale record with card match
                sale = SaleRecord(
                    card_id=matching_card.id,
                    sold_price=order.sold_price,
                    actual_profit=order.sold_price - matching_card.total_fees,
                    sold_at=order.sold_at,
                    platform=order.platform,
                    platform_order_id=f"{order.platform}:{order.order_id}",
                    platform_item_id=order.item_id,
                    sync_status="auto",
                    ebay_fee=matching_card.ebay_fee if order.platform == "ebay" else 0,
                    paypal_fee=matching_card.paypal_fee if order.platform == "ebay" else 0,
                    total_fees=matching_card.total_fees if order.platform == "ebay" else 0,
                )
                db.add(sale)
                db.commit()
                logger.info(f"Created sale record for {order.platform} order {order.order_id}")
                return True
            else:
                # Create pending sale for manual matching
                pending = PendingSales(
                    platform=order.platform,
                    platform_order_id=f"{order.platform}:{order.order_id}",
                    item_title=order.item_title,
                    sold_price=order.sold_price,
                    sold_at=order.sold_at,
                    status="pending"
                )
                db.add(pending)
                db.commit()
                logger.info(f"Created pending sale for {order.platform} order {order.order_id}")
                return False

        except Exception as e:
            logger.error(f"Error creating/matching sale: {str(e)}")
            return False

    def _update_sync_history(
        self,
        db: Session,
        platform: str,
        status: str,
        error_message: str = None,
        synced_count: int = 0
    ):
        """Update sync history for a platform"""
        try:
            sync_history = db.query(SyncHistory).filter(
                SyncHistory.platform == platform
            ).first()

            if not sync_history:
                sync_history = SyncHistory(platform=platform)
                db.add(sync_history)

            sync_history.last_sync_time = datetime.now()
            sync_history.next_sync_time = datetime.now() + timedelta(hours=6)  # Next sync in 6 hours
            sync_history.status = status
            sync_history.error_message = error_message
            sync_history.synced_count = synced_count
            sync_history.updated_at = datetime.now()

            db.commit()
            logger.info(f"Updated sync history for {platform}: {status}")

        except Exception as e:
            logger.error(f"Error updating sync history: {str(e)}")
