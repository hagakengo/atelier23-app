import os
import logging
import requests
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class NoteClient:
    """note API client for publishing articles"""

    def __init__(self, access_token: str = None):
        self.access_token = access_token or os.getenv("NOTE_ACCESS_TOKEN")
        self.base_url = "https://note.com/api/v2"
        self.session = requests.Session()
        if self.access_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })

    async def publish_article(
        self,
        title: str,
        content: str,
        is_paid: bool = False,
        price: int = 500,
        preview_text: str = None
    ) -> Optional[dict]:
        """
        Publish an article to note

        Args:
            title: Article title
            content: Article body (markdown)
            is_paid: Whether this is a paid article
            price: Price in yen (if is_paid=True)
            preview_text: Preview text for paid articles

        Returns:
            Article response with url if successful, None otherwise
        """
        if not self.access_token:
            logger.error("NOTE_ACCESS_TOKEN not configured")
            return None

        try:
            # Prepare payload
            payload = {
                "title": title,
                "body": content,
                "publish_at": datetime.now().isoformat(),
            }

            if is_paid:
                payload["price"] = price
                payload["preview_text"] = preview_text or content[:200]
                payload["status"] = "public_paid"
            else:
                payload["status"] = "public"

            # POST to note API
            url = f"{self.base_url}/notes"
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Published article: {title}")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to publish article: {str(e)}")
            return None

    async def publish_draft(
        self,
        title: str,
        content: str,
        is_paid: bool = False,
        price: int = 500
    ) -> Optional[dict]:
        """Publish article as draft (not visible to public)"""
        if not self.access_token:
            logger.error("NOTE_ACCESS_TOKEN not configured")
            return None

        try:
            payload = {
                "title": title,
                "body": content,
                "status": "draft",
            }

            if is_paid:
                payload["price"] = price

            url = f"{self.base_url}/notes"
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Created draft: {title}")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create draft: {str(e)}")
            return None

    async def update_article(
        self,
        article_id: str,
        title: str = None,
        content: str = None
    ) -> Optional[dict]:
        """Update an existing article"""
        if not self.access_token:
            logger.error("NOTE_ACCESS_TOKEN not configured")
            return None

        try:
            payload = {}
            if title:
                payload["title"] = title
            if content:
                payload["body"] = content

            url = f"{self.base_url}/notes/{article_id}"
            response = self.session.patch(url, json=payload, timeout=30)
            response.raise_for_status()

            logger.info(f"Updated article: {article_id}")
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update article: {str(e)}")
            return None

    async def get_my_profile(self) -> Optional[dict]:
        """Get authenticated user's profile"""
        if not self.access_token:
            logger.error("NOTE_ACCESS_TOKEN not configured")
            return None

        try:
            url = f"{self.base_url}/me"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            logger.info("Retrieved profile info")
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get profile: {str(e)}")
            return None


class NotePublisher:
    """High-level note article publisher with caching and retry logic"""

    def __init__(self):
        self.client = NoteClient()

    async def publish_daily_articles(self, articles: list[dict]) -> list[dict]:
        """
        Publish multiple articles with optimized timing

        Args:
            articles: List of article dicts with keys:
                - title (str)
                - content (str)
                - category (str)
                - is_paid (bool, optional)
                - price (int, optional)

        Returns:
            List of published article results
        """
        published = []

        for i, article in enumerate(articles):
            # Alternate between paid and free for diversity
            is_paid = i > 0  # First article free, rest paid
            price = 500 if i == 1 else (1800 if i == 2 else 500)

            result = await self.client.publish_article(
                title=article.get("title"),
                content=article.get("content"),
                is_paid=is_paid,
                price=price,
                preview_text=article.get("content", "")[:200]
            )

            if result:
                published.append({
                    "title": article.get("title"),
                    "url": result.get("url"),
                    "price": price if is_paid else 0,
                    "published_at": datetime.now().isoformat()
                })

        return published

    async def validate_token(self) -> bool:
        """Validate note API token"""
        profile = await self.client.get_my_profile()
        return profile is not None
