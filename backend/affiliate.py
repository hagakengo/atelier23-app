import os
from typing import Dict, List


class AffiliateManager:
    """アフィリエイトリンク管理"""

    def __init__(self):
        # Amazon アフィリエイト
        self.amazon_affiliate_id = os.getenv("AMAZON_AFFILIATE_ID", "atelier23-22")

        # 楽天アフィリエイト
        self.rakuten_affiliate_id = os.getenv("RAKUTEN_AFFILIATE_ID", "")
        self.rakuten_room_id = os.getenv("RAKUTEN_ROOM_ID", "")

        # eBay パートナー
        self.ebay_partner_id = os.getenv("EBAY_PARTNER_ID", "")

    def get_amazon_link(self, product_name: str, asin: str = None) -> str:
        """Amazon アフィリエイトリンク生成"""
        if asin:
            return f"https://amazon.jp/dp/{asin}?tag={self.amazon_affiliate_id}"
        else:
            encoded_name = product_name.replace(" ", "+")
            return f"https://amazon.jp/s?k={encoded_name}&tag={self.amazon_affiliate_id}"

    def get_rakuten_link(self, product_name: str, item_id: str = None) -> str:
        """楽天アフィリエイトリンク生成"""
        if item_id:
            return f"https://hb.afl.rakuten.co.jp/ichiba/1{self.rakuten_affiliate_id}/1/0/{item_id}/"
        else:
            encoded_name = product_name.replace(" ", "+")
            return f"https://search.rakuten.co.jp/search/mall/{encoded_name}/?s=1&oid={self.rakuten_affiliate_id}"

    def get_rakuten_link_html(self, product_name: str, item_id: str = None) -> str:
        """楽天リンク（HTML 形式）"""
        url = self.get_rakuten_link(product_name, item_id)
        return f"[{product_name}]({url})"

    def get_trading_card_links(self, game_type: str) -> Dict[str, str]:
        """トレーディングカード関連のリンク"""
        links = {}

        if game_type == "ポケモンカード":
            # ポケモンカード関連商品（Amazon + 楽天）
            links["【Amazon】ポケモンスリーブ"] = self.get_amazon_link("ポケモンカード スリーブ")
            links["【楽天】ポケモンスリーブ"] = self.get_rakuten_link("ポケモンカード スリーブ")
            links["【Amazon】デッキケース"] = self.get_amazon_link("ポケモンカード デッキケース")
            links["【楽天】デッキケース"] = self.get_rakuten_link("ポケモンカード デッキケース")
            links["PSA グレーディング"] = "https://www.psacard.com/"

        elif game_type == "ワンピースカード":
            links["【Amazon】スリーブ"] = self.get_amazon_link("ワンピースカード スリーブ")
            links["【楽天】スリーブ"] = self.get_rakuten_link("ワンピースカード スリーブ")
            links["【Amazon】デッキケース"] = self.get_amazon_link("ワンピースカード デッキケース")
            links["【楽天】デッキケース"] = self.get_rakuten_link("ワンピースカード デッキケース")

        elif game_type == "遊戯王":
            links["【Amazon】スリーブ"] = self.get_amazon_link("遊戯王 スリーブ")
            links["【楽天】スリーブ"] = self.get_rakuten_link("遊戯王 スリーブ")
            links["【Amazon】デッキケース"] = self.get_amazon_link("遊戯王 デッキケース")
            links["【楽天】デッキケース"] = self.get_rakuten_link("遊戯王 デッキケース")

        elif game_type == "ドラゴンボール":
            links["【Amazon】スリーブ"] = self.get_amazon_link("ドラゴンボール カード スリーブ")
            links["【楽天】スリーブ"] = self.get_rakuten_link("ドラゴンボール カード スリーブ")
            links["【Amazon】デッキケース"] = self.get_amazon_link("ドラゴンボール カード デッキケース")
            links["【楽天】デッキケース"] = self.get_rakuten_link("ドラゴンボール カード デッキケース")

        # 共通リンク（楽天ルーム優先）
        if self.rakuten_room_id:
            links["楽天ルーム"] = f"https://room.rakuten.co.jp/room/{self.rakuten_room_id}"
        else:
            links["【Amazon】カード保護ケース"] = self.get_amazon_link("トレーディングカード 保護ケース")
            links["【楽天】カード保護ケース"] = self.get_rakuten_link("トレーディングカード 保護ケース")

        return links

    def inject_affiliate_links(self, content: str, game_type: str = None) -> str:
        """記事内容にアフィリエイトリンクを埋め込む（FIRE層の最適化テンプレート）"""

        # セクション：関連商品の推奨（クリック率最適化版）
        affiliate_section = "\n\n---\n\n## 📦 おすすめ関連商品\n\n"
        affiliate_section += "記事の内容に役立つ商品をピックアップしました。\n"
        affiliate_section += "リンク経由での購入で、当サイトの運営を応援していただけます。\n\n"

        if game_type:
            links = self.get_trading_card_links(game_type)
            # Amazon 優先、2-3 個までに絞る（クリック率最適化）
            amazon_count = 0
            rakuten_count = 0

            for product, link in links.items():
                if "Amazon" in product and amazon_count < 2:
                    affiliate_section += f"**{product}**\n{link}\n\n"
                    amazon_count += 1
                elif "楽天" in product and rakuten_count < 1:
                    affiliate_section += f"**{product}**\n{link}\n\n"
                    rakuten_count += 1
        else:
            # デフォルトリンク（2-3 個に制限）
            affiliate_section += f"**【Amazon】カード保護ケース**\n"
            affiliate_section += f"{self.get_amazon_link('トレーディングカード 保護ケース')}\n\n"
            affiliate_section += f"**【楽天】カード保護ケース**\n"
            affiliate_section += f"{self.get_rakuten_link('トレーディングカード 保護ケース')}\n\n"

        # 楽天ルームがあれば最後に推奨
        if self.rakuten_room_id:
            affiliate_section += f"**楽天ルーム（おすすめ！）**\n"
            affiliate_section += f"https://room.rakuten.co.jp/room/{self.rakuten_room_id}\n\n"

        # サポート機能の宣伝
        support_section = "\n---\n\n## ☕ サポート機能について\n\n"
        support_section += "このような実践的な記事を毎日投稿しています。\n"
        support_section += "記事が参考になった場合は、サポート機能（¥500〜）で応援いただけると、\n"
        support_section += "より質の高いコンテンツ制作のモチベーションになります。\n"
        support_section += "ご協力ありがとうございます。🙏\n"

        return content + affiliate_section + support_section

    def format_affiliate_disclosure(self) -> str:
        """アフィリエイト表示（FTC/日本の法制度対応）"""
        return """
---

**[免責事項・アフィリエイト表示]**
当記事にはアフィリエイトリンクが含まれています。
Amazon や楽天などのリンクから商品を購入された場合、
著者が紹介料を受け取る可能性があります。
これは記事の品質や推奨には影響せず、
単に運営コストをサポートしていただく仕組みです。
"""


# グローバルインスタンス
affiliate_manager = AffiliateManager()


def inject_affiliate_to_article(article: dict) -> dict:
    """記事にアフィリエイトリンクを自動注入"""

    game_type = article.get("related_game_type")  # オプション

    # アフィリエイトセクション追加
    content_with_affiliate = affiliate_manager.inject_affiliate_links(
        article.get("content", ""),
        game_type=game_type
    )

    # 免責事項追加
    final_content = content_with_affiliate + affiliate_manager.format_affiliate_disclosure()

    # 更新
    article["content"] = final_content
    article["has_affiliate"] = True

    return article
