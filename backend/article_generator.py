import logging
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from anthropic import Anthropic
from main import SaleRecord, Card, ArticleLog, SessionLocal

logger = logging.getLogger(__name__)


class ArticleGenerator:
    """Generate valuable articles for note based on sales data"""

    def __init__(self, api_key: str = None):
        import os
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-3-5-sonnet-20241022"

    async def generate_daily_articles(self, num_articles: int = 3) -> list[dict]:
        """Generate multiple articles for daily posting"""
        db = SessionLocal()
        try:
            articles = []

            # Get recent sales data
            recent_sales = self._get_recent_sales(db, days=7)

            if not recent_sales:
                logger.warning("No recent sales data available")
                return articles

            # Analyze sales patterns
            analysis = self._analyze_sales(recent_sales)

            # Generate articles based on patterns
            article_ideas = self._generate_article_ideas(analysis, num_articles)

            for idea in article_ideas:
                article = await self._generate_article(idea, analysis, db)
                if article:
                    articles.append(article)

            return articles

        finally:
            db.close()

    async def generate_weekly_profit_report(self) -> dict:
        """Generate weekly profit report article"""
        db = SessionLocal()
        try:
            # Get last week's sales
            one_week_ago = datetime.now() - timedelta(days=7)
            sales = db.query(SaleRecord).filter(
                SaleRecord.sold_at >= one_week_ago
            ).all()

            if not sales:
                return None

            # Calculate metrics
            total_profit = sum(s.actual_profit for s in sales)
            total_sales = sum(s.sold_price for s in sales)
            avg_profit = total_profit / len(sales) if sales else 0
            total_fees = sum(s.total_fees for s in sales)

            article_content = f"""先週のトレーディングカード販売成績

こんにちは。この週も eBay で複数のカードを販売しました。

## 先週の実績

- **販売件数**: {len(sales)} 件
- **総売上**: ¥{total_sales:,.0f}
- **総手数料**: ¥{total_fees:,.0f}
- **実利益**: ¥{total_profit:,.0f}
- **平均利益/枚**: ¥{avg_profit:,.0f}

## カード販売の秘訣

1. **相場分析が全て** - 毎日の相場チェックで最適な売却タイミングを見つける
2. **手数料を甘く見ない** - eBay + PayPal で約 16% 手数料が取られる
3. **送料を含めて考える** - 国内 ¥110、海外 ¥1,290 の送料が大きく影響

次週も継続して販売していきます！

---

このような実績をベースに、読者に「カード投資で稼ぐ方法」を提供しています。"""

            article = {
                "title": f"先週の販売成績 | 利益 ¥{total_profit:,.0f}",
                "content": article_content,
                "category": "profit_report",
                "related_sales_ids": ",".join(str(s.id) for s in sales),
            }

            return article

        finally:
            db.close()

    def _get_recent_sales(self, db: Session, days: int = 7) -> list:
        """Get recent sales data"""
        since = datetime.now() - timedelta(days=days)
        return db.query(SaleRecord).filter(
            SaleRecord.sold_at >= since
        ).all()

    def _analyze_sales(self, sales: list) -> dict:
        """Analyze sales patterns"""
        if not sales:
            return {}

        game_types = {}
        prices = []
        profits = []

        for sale in sales:
            prices.append(sale.sold_price)
            profits.append(sale.actual_profit)

        return {
            "total_sales": len(sales),
            "total_profit": sum(profits),
            "avg_price": sum(prices) / len(prices) if prices else 0,
            "avg_profit": sum(profits) / len(profits) if profits else 0,
            "max_profit": max(profits) if profits else 0,
            "min_profit": min(profits) if profits else 0,
        }

    def _generate_article_ideas(self, analysis: dict, num_articles: int) -> list[str]:
        """Generate article ideas based on sales analysis"""
        base_ideas = [
            "相場速報：今週のトレカ市場動向と売却チャンス",
            "初心者向け：eBay輸出で月5万円稼ぐロードマップ",
            "カード相場を読むテクニック：データ分析で利益を最大化する方法",
            "初心者が避けるべき トレーディングカード投資の5つのミス",
            "eBay vs メルカリ：どのプラットフォームで売るべき？",
            "手数料を計算してから売る：利益を確保する値付けの秘訣",
            "月 20 万円達成者の販売戦略を分析してみた",
            "トレーディングカード投資で確実に利益を出す3つのルール",
            "相場が下がる前に売る方法：失敗しない売却タイミング",
            "ポケモンカード投資初心者向け完全ガイド",
            "eBayで売れやすいカードの特徴3つ",
            "PSA鑑定カードで利益を出すコツ",
        ]
        return base_ideas[:num_articles]

    async def _generate_article(self, idea: str, analysis: dict, db: Session) -> dict:
        """Generate a single article using Claude"""
        try:
            prompt = f"""以下のテーマで、note 読者向けの有価な記事を執筆してください。

テーマ: {idea}

読者の状況：
- トレーディングカード投資に興味がある
- eBay での販売を考えている
- 月 10-20 万円の副業収入を目指している

記事の要件：
1. 読者の悩みを最初に提示する（なぜこの記事が必要か）
2. 具体的なデータ・実例を交える
3. 実行可能なテクニック・ステップを3-5個提示
4. note の有料購読を促すような価値を提供
5. マークダウン形式で、見出し・箇条書きを活用

以下は実際のビジネスデータです：
- 今週の平均売却価格: ¥{analysis.get('avg_price', 0):,.0f}
- 今週の平均利益: ¥{analysis.get('avg_profit', 0):,.0f}
- 販売件数: {analysis.get('total_sales', 0)} 件

記事本文をマークダウン形式で生成してください。"""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            content = message.content[0].text

            article = {
                "title": idea,
                "content": content,
                "category": self._categorize_article(idea),
                "related_sales_ids": None,
            }

            # アフィリエイトリンクを自動注入
            from affiliate import inject_affiliate_to_article
            article = inject_affiliate_to_article(article)

            logger.info(f"Generated article with affiliate links: {idea}")
            return article

        except Exception as e:
            logger.error(f"Error generating article: {str(e)}")
            return None

    def _categorize_article(self, title: str) -> str:
        """Categorize article based on title"""
        title_lower = title.lower()
        if "利益" in title or "成績" in title:
            return "profit_report"
        elif "テクニック" in title or "方法" in title:
            return "tutorial"
        elif "分析" in title or "データ" in title:
            return "analysis"
        else:
            return "strategy"

    def save_article(self, article: dict, db: Session = None) -> bool:
        """Save generated article to database"""
        try:
            if db is None:
                db = SessionLocal()
                close_db = True
            else:
                close_db = False

            article_log = ArticleLog(
                title=article.get("title"),
                content=article.get("content"),
                category=article.get("category", "strategy"),
                related_sales_ids=article.get("related_sales_ids"),
                status="draft"
            )

            db.add(article_log)
            db.commit()
            logger.info(f"Saved article: {article.get('title')}")
            return True

        except Exception as e:
            logger.error(f"Error saving article: {str(e)}")
            return False
        finally:
            if close_db:
                db.close()
