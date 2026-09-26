import os
import requests
import json
from typing import Dict, List, Optional
from datetime import datetime
import urllib3

# SSL 警告を無効化
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CardPriceLookup:
    """TCG Price API を使ったカード相場検索"""

    def __init__(self):
        self.api_key = os.getenv("TCG_PRICE_API_KEY", "")
        self.base_url = "https://api.tcgfast.com/api/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
        # コネクションプールを設定
        self.session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        self.session.mount('http://', requests.adapters.HTTPAdapter(max_retries=3))

    def search_cards(self, card_name: str, game: str = "pokemon-japanese", limit: int = 5) -> List[Dict]:
        """
        カード名で検索（複数候補を返す）

        Args:
            card_name: カード名（日本語）
            game: ゲームタイプ (pokemon-japanese, one-piece, yu-gi-oh など)
            limit: 返す候補数

        Returns:
            相場情報を含むカード情報リスト
        """
        try:
            params = {
                "q": card_name,
                "game": game,
                "limit": limit
            }

            response = self.session.get(
                f"{self.base_url}/cards/search",
                params=params,
                timeout=15,
                verify=False
            )
            response.raise_for_status()

            data = response.json()
            results = []

            if "results" in data:
                for card in data["results"][:limit]:
                    results.append(self._format_card_info(card))

            return results

        except requests.exceptions.RequestException as e:
            print(f"TCG Price API Error: {e}")
            return []

    def get_card_details(self, card_id: str) -> Optional[Dict]:
        """
        カード ID で詳細情報を取得

        Args:
            card_id: カード ID

        Returns:
            カード詳細情報（相場グラフ、在庫など）
        """
        try:
            response = self.session.get(f"{self.base_url}/cards/{card_id}", timeout=10)
            response.raise_for_status()

            card = response.json()
            return self._format_card_info(card)

        except requests.exceptions.RequestException as e:
            print(f"TCG Price API Error: {e}")
            return None

    def _format_card_info(self, card_data: Dict) -> Dict:
        """
        API のレスポンスをフロント用にフォーマット
        """
        return {
            "id": card_data.get("id"),
            "name": card_data.get("name"),
            "game": card_data.get("game"),
            "set_code": card_data.get("set", {}).get("code"),
            "set_name": card_data.get("set", {}).get("name"),
            "card_number": card_data.get("number"),
            "rarity": card_data.get("rarity"),
            "image_url": card_data.get("image_url"),
            "prices": {
                "market": card_data.get("prices", {}).get("market"),
                "low": card_data.get("prices", {}).get("low"),
                "mid": card_data.get("prices", {}).get("mid"),
                "high": card_data.get("prices", {}).get("high"),
                "buy": card_data.get("prices", {}).get("buy"),
            },
            "price_change": card_data.get("price_change", {}).get("percent", 0),
            "last_updated": datetime.now().isoformat(),
            "language": card_data.get("language", "Japanese"),
            "condition": card_data.get("condition"),
            "stock": card_data.get("stock")
        }

    def search_by_recognition(self, recognized_name: str) -> List[Dict]:
        """
        画像認識結果からカード検索

        Args:
            recognized_name: LLaVA が認識したカード名

        Returns:
            複数候補のカード情報
        """
        # ゲーム判定（簡易版）
        game_type = self._guess_game_type(recognized_name)

        return self.search_cards(recognized_name, game=game_type, limit=5)

    def _guess_game_type(self, card_name: str) -> str:
        """
        カード名からゲームタイプを推測
        """
        keywords = {
            "pokemon-japanese": ["ポケモン", "ピカチュウ", "リザードン", "フリーザー"],
            "one-piece": ["ワンピース", "ルフィ", "ナミ", "ゾロ"],
            "yu-gi-oh": ["遊戯王", "ブルーアイズ", "ダークマジシャン", "融合"],
            "dragon-ball": ["ドラゴンボール", "孫悟空", "フリーザ", "セル"],
        }

        for game, keys in keywords.items():
            if any(keyword in card_name for keyword in keys):
                return game

        return "pokemon-japanese"  # デフォルト


# グローバルインスタンス
card_price_lookup = CardPriceLookup()


def search_card_price(card_name: str, game: str = "pokemon-japanese") -> List[Dict]:
    """相場検索の簡易インターフェース"""
    return card_price_lookup.search_cards(card_name, game)


def get_card_by_recognition(recognized_name: str) -> List[Dict]:
    """画像認識結果から相場検索"""
    return card_price_lookup.search_by_recognition(recognized_name)


# テスト用
if __name__ == "__main__":
    lookup = CardPriceLookup()
    print(f"API Key set: {bool(lookup.api_key)}")
    print(f"Base URL: {lookup.base_url}")
    results = lookup.search_cards("ピカチュウ", limit=3)
    print(f"Results count: {len(results)}")
    for r in results:
        print(r)
