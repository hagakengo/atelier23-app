import logging
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import requests
import os
from main import SaleRecord, Card, ArticleLog, SessionLocal

logger = logging.getLogger(__name__)


class ArticleGenerator:
    """Generate articles with Ollama, then refine with Claude for professional editing"""

    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        self.generation_model = "mistral"  # Fast, free article generation

        # Optional: Claude API for professional refinement
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.claude_model = "claude-3-5-sonnet-20241022"
        if self.anthropic_key:
            try:
                from anthropic import Anthropic
                self.claude_client = Anthropic(api_key=self.anthropic_key)
            except Exception as e:
                logger.warning(f"Claude client unavailable: {e}. Using Ollama-only mode.")
                self.claude_client = None
        else:
            self.claude_client = None

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
        """Generate a single article using Ollama (free local LLM) - FIRE-optimized template"""
        try:
            prompt = f"""【note有料記事を執筆】読者の人生を変える説得力のある記事を作成してください。

テーマ: {idea}

【ターゲット読者の心理状態】
- 月5-50万円を目指しているが「本当に稼げるのか」と疑っている
- 失敗経験があり、もう失敗したくない心情を抱えている
- 「確実な方法」「実証済みのテクニック」に飢えている
- 記事を読んだら「今すぐ実行したい」と思わせる必要がある

【記事構成】（必須 - 読者の心を動かす流れ）
1. **共感と問題提示（4-5行）**：「あなたはこんな経験ありませんか？」と読者の痛みを指摘。失敗の苦しさを言語化する
2. **希望の提示（3行）**：「実は、この問題は解決できる」と希望を見せる
3. **根拠データ（5-6行）**：実際のビジネス数字で「この記事の信頼性」を立証。感情ではなく論理で確信させる
4. **コア解決法（8-10行）**：3-5つのステップを具体的に。それぞれを「なぜこれが効果的か」まで説明する
5. **実装ハードル克服（4-5行）**：「よくある失敗」「陥りやすい罠」を指摘。読者が実装時に「あ、この落とし穴だ」と気づかせる
6. **アクションチェックリスト（6-8行）**：今週・今月・3ヶ月後の行動を明確化。読者が迷わずに実行できるようにする
7. **感情的クロージング（3-4行）**：「この方法を使えば、3ヶ月後のあなたは○○になっている」と未来を見せる

【実際のビジネスデータ - 信頼性の根拠】
- 実績：平均売却価格 ¥{analysis.get('avg_price', 0):,.0f}、平均利益 ¥{analysis.get('avg_profit', 0):,.0f}
- 検証済み販売件数: {analysis.get('total_sales', 0)} 件
- 信頼性：これらは机上の空論ではなく「実際に出ている数字」である

【文体ルール】（厳守 - 読者の心に届く文章のために）
- 1文は必ず1行（読みやすさ）
- 文末は「。」で統一（一貫性）
- 読点「、」は控えめに（1文に最大1個）
- 「です・ます」は使わず「である」「だ」で統一（信頼感）
- 数字は常に「¥」をつける（説得力）
- 「あなた」「私たち」を使って読者との距離を縮める
- 段落は3-4行でまとめる（リズム感）

【必ず提供する価値】
1. **感情的価値**：読者が「この著者は自分の痛みを理解している」と感じる
2. **認知的価値**：読者が「なるほど、だからこの方法が効果的なのか」と納得する
3. **実装的価値**：読者が「明日からこれを実行しよう」と思える具体性
4. **経済的価値**：読者が「この記事は¥1,800の価値がある」と確信する

本文のみ（タイトルなし）を出力してください。
記事の最後に「この記事が役に立ったら、コメントやサポートをお願いします」は追加しないでください。本文だけに集中してください。"""

            # Ollama 経由で記事生成
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.generation_model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.7,
                },
                timeout=120
            )
            response.raise_for_status()

            data = response.json()
            content = data.get("response", "").strip()

            # 1文1行・文末「。」の自動化
            content = self._normalize_article_format(content)

            # Claude で添削（API キーがある場合）
            if self.claude_client:
                content = await self._refine_with_claude(content, idea)

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

        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API error: {str(e)}")
            return None
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

    async def _refine_with_claude(self, content: str, title: str) -> str:
        """Refine article with Claude for professional quality"""
        if not self.claude_client:
            return content

        try:
            refinement_prompt = f"""以下の記事をプロの作家目線で添削してください。

【記事タイトル】
{title}

【記事本文】
{content}

【添削のポイント】
1. **説得力の強化**：読者の心に響く文章になっているか。感情と論理のバランスは取れているか。
2. **文体の統一**：「です・ます」「である」「だ」が混在していないか。一貫性を確保。
3. **具体性**：抽象的な表現を具体的に。「これ」「それ」を明確な名詞に。
4. **リズム感**：句点の位置は適切か。読みやすく、呼吸がしやすい文章か。
5. **不要な表現の削除**：冗長さ、重複がないか。「てにをは」は正確か。
6. **FIRE読者向けの最適化**：¥1,800の価値を感じさせる内容か。実装可能性は明確か。

元の構成と意図は保ちながら、より洗練された文章に改善してください。
本文のみを出力してください（説明や注釈は不要）。"""

            message = self.claude_client.messages.create(
                model=self.claude_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": refinement_prompt}]
            )

            refined = message.content[0].text
            logger.info(f"Article refined with Claude: {title}")
            return refined

        except Exception as e:
            logger.warning(f"Claude refinement failed, using original: {e}")
            return content

    def _normalize_article_format(self, content: str) -> str:
        """Normalize article to 1-sentence-per-line format with 。 at end"""
        import re

        lines = []
        current_line = ""

        # Replace various sentence endings with 。
        content = re.sub(r'([^。\n])$', r'\1。', content, flags=re.MULTILINE)
        content = re.sub(r'([^。])(\n)', r'\1。\2', content)

        for char in content:
            if char == '。':
                current_line += char
                lines.append(current_line.strip())
                current_line = ""
            elif char == '\n':
                if current_line.strip():
                    if not current_line.endswith('。'):
                        current_line += '。'
                    lines.append(current_line.strip())
                    current_line = ""
            else:
                current_line += char

        if current_line.strip():
            if not current_line.strip().endswith('。'):
                current_line += '。'
            lines.append(current_line.strip())

        # Remove empty lines and rejoin
        lines = [line for line in lines if line]
        return '\n'.join(lines)

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
