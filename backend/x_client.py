import os
import logging
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class BufferClient:
    """Buffer API client for X (Twitter) scheduling"""

    def __init__(self, access_token: str = None):
        self.access_token = access_token or os.getenv("BUFFER_ACCESS_TOKEN")
        self.base_url = "https://api.bufferapp.com/1"
        self.profile_id = os.getenv("BUFFER_PROFILE_ID")  # X profile ID from Buffer
        self.session = requests.Session()
        if self.access_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })

    async def schedule_tweet(
        self,
        text: str,
        scheduled_at: datetime = None,
        media_ids: list[str] = None
    ) -> Optional[dict]:
        """
        Schedule a tweet via Buffer

        Args:
            text: Tweet text (max 280 characters)
            scheduled_at: When to post (defaults to now)
            media_ids: List of media IDs to attach

        Returns:
            Buffer update response if successful
        """
        if not self.access_token or not self.profile_id:
            logger.error("BUFFER_ACCESS_TOKEN or BUFFER_PROFILE_ID not configured")
            return None

        try:
            # Ensure text is within X limits
            if len(text) > 280:
                logger.warning(f"Tweet text too long ({len(text)} chars), truncating")
                text = text[:277] + "..."

            payload = {
                "profile_ids": [self.profile_id],
                "text": text,
            }

            if scheduled_at:
                payload["scheduled_at"] = int(scheduled_at.timestamp())

            if media_ids:
                payload["media_ids"] = media_ids

            # POST to Buffer API
            url = f"{self.base_url}/updates/create.json"
            response = self.session.post(url, data=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Scheduled tweet: {text[:50]}...")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to schedule tweet: {str(e)}")
            return None

    async def schedule_tweet_chain(
        self,
        tweets: list[str],
        interval_minutes: int = 30
    ) -> list[dict]:
        """
        Schedule multiple tweets at intervals

        Args:
            tweets: List of tweet texts
            interval_minutes: Minutes between tweets

        Returns:
            List of scheduled updates
        """
        scheduled = []

        for i, tweet in enumerate(tweets):
            minutes_offset = i * interval_minutes
            scheduled_at = datetime.fromtimestamp(
                datetime.now().timestamp() + (minutes_offset * 60)
            )

            result = await self.schedule_tweet(tweet, scheduled_at)
            if result:
                scheduled.append(result)

        return scheduled

    async def validate_token(self) -> bool:
        """Validate Buffer API token"""
        try:
            url = f"{self.base_url}/user.json"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            logger.info("Buffer token validated")
            return True
        except Exception as e:
            logger.error(f"Buffer token validation failed: {str(e)}")
            return False


class XPublisher:
    """High-level X publisher for note article promotion"""

    def __init__(self):
        self.buffer = BufferClient()

    async def announce_new_article(
        self,
        title: str,
        note_url: str,
        price: int = 0
    ) -> Optional[dict]:
        """
        Create an announcement tweet for a new note article

        Args:
            title: Article title
            note_url: Link to note article
            price: Price in yen (0 for free)

        Returns:
            Buffer schedule response
        """
        if price == 0:
            tweet_text = f"🆕 新しい記事を出しました\n\n{title}\n\n{note_url}\n\n#トレカ投資 #eBay"
        else:
            tweet_text = f"💰 有料記事が出ました\n\n{title}\n¥{price}\n\n{note_url}\n\n#トレカ投資 #note"

        return await self.buffer.schedule_tweet(tweet_text)

    async def announce_multiple_articles(
        self,
        articles: list[dict]
    ) -> list[dict]:
        """
        Create announcement tweets for multiple articles

        Args:
            articles: List of articles with keys: title, note_url, price

        Returns:
            List of scheduled announcements
        """
        announcements = []

        for article in articles:
            result = await self.announce_new_article(
                title=article.get("title"),
                note_url=article.get("note_url"),
                price=article.get("price", 0)
            )
            if result:
                announcements.append(result)

        return announcements

    async def post_market_update(
        self,
        summary: str,
        link: str = None
    ) -> Optional[dict]:
        """Post a market update tweet"""
        tweet = f"📊 相場アップデート\n\n{summary}\n\n詳細はnoteで👇\n{link if link else ''}\n\n#ポケカ #トレカ相場"
        return await self.buffer.schedule_tweet(tweet)
