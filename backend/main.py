from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime
import os
import shutil
import requests
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import asyncio
from card_price_lookup import card_price_lookup, get_card_by_recognition

# .env ファイルを読み込む
load_dotenv()

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = "sqlite:///./atelier23.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 画像保存ディレクトリ
UPLOAD_DIR = "uploads"
Path(UPLOAD_DIR).mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# eBay API 設定
EBAY_API_KEY = os.getenv("EBAY_API_KEY")
EBAY_API_SECRET = os.getenv("EBAY_API_SECRET")
EBAY_REFRESH_TOKEN = os.getenv("EBAY_REFRESH_TOKEN")

# スケジューラー
scheduler = BackgroundScheduler()

def sync_ebay_and_publish():
    """eBay から売却済み商品を取得して自動記録 & 記事を生成・投稿"""
    db = None
    try:
        db = SessionLocal()
        logger.info("Starting eBay sync and article generation...")

        # eBay API キーがある場合のみ実行
        if all([EBAY_API_KEY, EBAY_API_SECRET, EBAY_REFRESH_TOKEN]):
            # TODO: eBay API から売却済み商品を取得して db に記録
            pass
        else:
            logger.info("eBay API credentials not set, skipping eBay sync.")

        # 記事生成・投稿（常に実行）
        asyncio.run(_generate_and_publish_articles(db))

        logger.info("eBay sync and article generation completed.")

    except Exception as e:
        logger.error(f"Sync and publish error: {str(e)}")
    finally:
        if db:
            db.close()

async def _generate_and_publish_articles(db: Session):
    """Generate and publish articles to note & X"""
    try:
        from article_generator import ArticleGenerator
        from note_client import NotePublisher
        from x_client import XPublisher

        generator = ArticleGenerator()
        note_pub = NotePublisher()
        x_pub = XPublisher()

        # Generate articles
        articles = await generator.generate_daily_articles(num_articles=3)

        if not articles:
            logger.warning("No articles generated")
            return

        logger.info(f"Generated {len(articles)} articles")

        # Publish to note & X
        for i, article in enumerate(articles):
            # Publish to note (alternate between free and paid)
            is_paid = i > 0
            price = 500 if i == 1 else (1800 if i == 2 else 500)

            try:
                result = await note_pub.client.publish_article(
                    title=article.get("title"),
                    content=article.get("content"),
                    is_paid=is_paid,
                    price=price
                )

                if result:
                    note_url = result.get("url", "")
                    article_log = ArticleLog(
                        title=article.get("title"),
                        content=article.get("content"),
                        category=article.get("category", "strategy"),
                        note_url=note_url,
                        published_at=datetime.now(),
                        published_on_x=False,
                        status="published"
                    )
                    db.add(article_log)
                    db.commit()

                    # Announce on X
                    await x_pub.announce_new_article(
                        title=article.get("title"),
                        note_url=note_url,
                        price=price if is_paid else 0
                    )

                    logger.info(f"Published article: {article.get('title')}")
            except Exception as article_error:
                logger.error(f"Error publishing article {article.get('title')}: {str(article_error)}")
                continue

    except Exception as e:
        logger.error(f"Article generation/publication error: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """アプリ起動時にスケジューラーを開始"""
    # 毎日 08:00, 14:00, 20:00 に実行
    scheduler.add_job(sync_ebay_and_publish, 'cron', hour='8,14,20', minute='0')
    scheduler.start()
    logger.info("Scheduler started. Jobs: 08:00, 14:00, 20:00 JST")

@app.on_event("shutdown")
async def shutdown_event():
    """アプリ終了時にスケジューラーを停止"""
    scheduler.shutdown()
    logger.info("Scheduler stopped.")

class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    game_type = Column(String)
    series = Column(String)
    grade = Column(String, nullable=True)
    market_price = Column(Float)
    your_price = Column(Float)
    image_url = Column(String, nullable=True)
    last_price_update = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)
    ebay_fee = Column(Float, default=0.0)
    paypal_fee = Column(Float, default=0.0)
    total_fees = Column(Float, default=0.0)
    domestic_shipping = Column(Float, default=110.0)
    overseas_shipping = Column(Float, default=1290.0)
    your_price_after_fees = Column(Float, default=0.0)

class SaleRecord(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True)
    card_id = Column(Integer)
    sold_price = Column(Float)
    actual_profit = Column(Float)
    sold_at = Column(DateTime, default=datetime.now)
    ebay_fee = Column(Float, default=0.0)
    paypal_fee = Column(Float, default=0.0)
    total_fees = Column(Float, default=0.0)
    platform = Column(String, default="manual")  # 'ebay', 'amazon', 'mercari', 'manual'
    platform_order_id = Column(String, nullable=True, unique=True)  # 'ebay:12345'
    platform_item_id = Column(String, nullable=True)  # item id from platform
    sync_status = Column(String, default="manual")  # 'auto', 'manual', 'pending_match'

class SyncHistory(Base):
    __tablename__ = "sync_history"
    id = Column(Integer, primary_key=True)
    platform = Column(String)  # 'ebay', 'amazon', 'mercari', 'rakuma'
    last_sync_time = Column(DateTime, nullable=True)
    next_sync_time = Column(DateTime, nullable=True)
    status = Column(String, default="pending")  # 'success', 'failed', 'pending'
    error_message = Column(String, nullable=True)
    synced_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class PendingSales(Base):
    __tablename__ = "pending_sales"
    id = Column(Integer, primary_key=True)
    platform = Column(String)  # 'ebay', 'amazon', 'mercari'
    platform_order_id = Column(String, unique=True)
    item_title = Column(String)
    sold_price = Column(Float)
    sold_at = Column(DateTime)
    matched_card_id = Column(Integer, nullable=True)  # manual match時に設定
    status = Column(String, default="pending")  # 'pending', 'matched', 'archived'
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class ArticleLog(Base):
    __tablename__ = "article_logs"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    content = Column(String)  # article body
    category = Column(String)  # 'profit_report', 'strategy', 'analysis', 'tutorial'
    related_sales_ids = Column(String, nullable=True)  # comma-separated sale IDs
    note_url = Column(String, nullable=True)  # URL after publishing
    published_at = Column(DateTime, nullable=True)
    published_on_x = Column(Boolean, default=False)
    x_url = Column(String, nullable=True)
    status = Column(String, default="draft")  # 'draft', 'published', 'archived'
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

Base.metadata.create_all(bind=engine)

class CardCreate(BaseModel):
    name: str
    game_type: str
    series: str
    grade: str | None = None
    market_price: float

class CardResponse(BaseModel):
    id: int
    name: str
    game_type: str
    series: str
    grade: str | None = None
    market_price: float
    your_price: float
    image_url: str | None = None
    ebay_fee: float = 0.0
    paypal_fee: float = 0.0
    total_fees: float = 0.0
    domestic_shipping: float = 110.0
    overseas_shipping: float = 1290.0
    your_price_after_fees: float = 0.0
    class Config:
        from_attributes = True

class SaleRecordCreate(BaseModel):
    card_id: int
    sold_price: float
    cost: float

class SaleRecordResponse(BaseModel):
    id: int
    card_id: int
    sold_price: float
    actual_profit: float
    ebay_fee: float = 0.0
    paypal_fee: float = 0.0
    total_fees: float = 0.0
    platform: str = "manual"
    platform_order_id: str | None = None
    platform_item_id: str | None = None
    sync_status: str = "manual"
    class Config:
        from_attributes = True

# ============= カード管理 API =============

@app.post("/api/cards", response_model=CardResponse)
def create_card(card: CardCreate):
    db = SessionLocal()
    your_price = card.market_price * 0.9

    # 手数料計算（eBay 12.9% + PayPal 3.49% + ¥40）
    ebay_fee = round(card.market_price * 0.129, 2)
    paypal_fee = round(card.market_price * 0.0349 + 40, 2)
    total_fees = ebay_fee + paypal_fee

    # 日本国内向け実利益（送料¥110込み）
    domestic_shipping = 110.0
    your_price_after_fees = card.market_price - total_fees - domestic_shipping

    db_card = Card(
        name=card.name,
        game_type=card.game_type,
        series=card.series,
        grade=card.grade or "N/A",
        market_price=card.market_price,
        your_price=round(your_price, 2),
        ebay_fee=ebay_fee,
        paypal_fee=paypal_fee,
        total_fees=round(total_fees, 2),
        domestic_shipping=domestic_shipping,
        overseas_shipping=1290.0,
        your_price_after_fees=round(your_price_after_fees, 2),
    )
    db.add(db_card)
    db.commit()
    db.refresh(db_card)
    db.close()
    return db_card

@app.get("/api/cards", response_model=list[CardResponse])
def get_cards():
    db = SessionLocal()
    cards = db.query(Card).all()
    db.close()
    return cards

@app.get("/api/cards/{card_id}", response_model=CardResponse)
def get_card(card_id: int):
    db = SessionLocal()
    card = db.query(Card).filter(Card.id == card_id).first()
    db.close()
    return card

@app.put("/api/cards/{card_id}", response_model=CardResponse)
def update_card(card_id: int, card: CardCreate):
    db = SessionLocal()
    db_card = db.query(Card).filter(Card.id == card_id).first()
    your_price = card.market_price * 0.9

    # 手数料計算
    ebay_fee = round(card.market_price * 0.129, 2)
    paypal_fee = round(card.market_price * 0.0349 + 40, 2)
    total_fees = ebay_fee + paypal_fee

    domestic_shipping = 110.0
    your_price_after_fees = card.market_price - total_fees - domestic_shipping

    db_card.name = card.name
    db_card.game_type = card.game_type
    db_card.series = card.series
    db_card.grade = card.grade or "N/A"
    db_card.market_price = card.market_price
    db_card.your_price = round(your_price, 2)
    db_card.ebay_fee = ebay_fee
    db_card.paypal_fee = paypal_fee
    db_card.total_fees = round(total_fees, 2)
    db_card.domestic_shipping = domestic_shipping
    db_card.overseas_shipping = 1290.0
    db_card.your_price_after_fees = round(your_price_after_fees, 2)
    db_card.last_price_update = datetime.now()

    db.commit()
    db.refresh(db_card)
    db.close()
    return db_card

@app.delete("/api/cards/{card_id}")
def delete_card(card_id: int):
    db = SessionLocal()
    db_card = db.query(Card).filter(Card.id == card_id).first()
    if db_card:
        # 画像ファイルも削除
        if db_card.image_url:
            image_path = db_card.image_url.replace("/uploads/", "")
            try:
                os.remove(os.path.join(UPLOAD_DIR, image_path))
            except:
                pass
        db.delete(db_card)
        db.commit()
    db.close()
    return {"status": "deleted"}

# ============= 販売記録 API =============

@app.post("/api/sales", response_model=SaleRecordResponse)
def record_sale(sale: SaleRecordCreate):
    db = SessionLocal()
    # 手数料計算（eBay 12.9% + PayPal 3.49% + ¥40）
    ebay_fee = round(sale.sold_price * 0.129, 2)
    paypal_fee = round(sale.sold_price * 0.0349 + 40, 2)
    total_fees = ebay_fee + paypal_fee
    actual_income = sale.sold_price - total_fees
    actual_profit = actual_income - sale.cost

    db_sale = SaleRecord(
        card_id=sale.card_id,
        sold_price=sale.sold_price,
        actual_profit=round(actual_profit, 2),
        ebay_fee=ebay_fee,
        paypal_fee=paypal_fee,
        total_fees=round(total_fees, 2),
    )
    db.add(db_sale)
    db.commit()
    db.refresh(db_sale)
    db.close()
    return db_sale

@app.get("/api/sales")
def get_sales():
    db = SessionLocal()
    sales = db.query(SaleRecord).all()
    total_sales = sum([s.sold_price for s in sales])
    total_profit = sum([s.actual_profit for s in sales])
    db.close()
    return {
        "sales": sales,
        "total_sales": total_sales,
        "total_profit": round(total_profit, 2),
        "count": len(sales),
    }

# ============= 分析 API =============

@app.get("/api/analytics")
def get_analytics():
    db = SessionLocal()
    cards = db.query(Card).all()
    sales = db.query(SaleRecord).all()
    total_actual_profit = sum([s.actual_profit for s in sales])
    db.close()
    return {
        "total_items_listed": len(cards),
        "total_items_sold": len(sales),
        "total_potential_profit": 0,
        "total_actual_profit": round(total_actual_profit, 2),
        "average_profit_per_card": round(total_actual_profit / max(len(sales), 1), 2),
    }

# ============= 画像認識 & 相場検索 API =============

@app.post("/api/upload-card-image")
async def upload_card_image(file: UploadFile = File(...)):
    try:
        # ファイルを保存
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Ollama（LLaVA）でカード認識（無料ローカル）
        ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL", "llava:7b-v1.6")

        with open(file_path, "rb") as image_file:
            image_data = image_file.read()

        import base64
        import json
        base64_image = base64.standard_b64encode(image_data).decode("utf-8")

        # Ollama API にリクエスト
        ollama_prompt = """このトレーディングカードの情報を抽出してください。
JSON形式で以下を返してください：
{
  "name": "カード名",
  "game_type": "ゲームの種類（例：ポケモンカード、ワンピースカード、遊戯王、ドラゴンボール）",
  "series": "シリーズ名（例：Base Set, op-01）",
  "grade": "グレード（例：PSA 9, M, LP）"
}
"""

        ollama_response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": ollama_model,
                "prompt": ollama_prompt,
                "images": [base64_image],
                "stream": False,
            },
            timeout=60,
        )

        if ollama_response.status_code != 200:
            logger.warning(f"Ollama API error: {ollama_response.text}")
            # Ollama が使用できない場合は、デフォルトを返す
            return {
                "success": True,
                "image_url": f"/uploads/{file.filename}",
                "card_info": {"name": "Unknown", "game_type": "Unknown", "series": "Unknown", "grade": "Unknown"},
                "message": "Ollama が起動していません。http://localhost:11434 で Ollama を起動してください。"
            }

        response_data = ollama_response.json()
        response_text = response_data.get("response", "")

        # JSON を抽出
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                card_info = json.loads(response_text[json_start:json_end])
            else:
                card_info = {"name": "Unknown", "game_type": "Unknown", "series": "Unknown", "grade": "Unknown"}
        except (json.JSONDecodeError, ValueError):
            card_info = {"name": "Unknown", "game_type": "Unknown", "series": "Unknown", "grade": "Unknown"}

        # 相場検索を自動実行
        price_data = []
        if card_info.get("name") != "Unknown":
            try:
                price_data = get_card_by_recognition(card_info.get("name", ""))
            except Exception as e:
                logger.warning(f"Price lookup error: {e}")
                price_data = []

        return {
            "success": True,
            "image_url": f"/uploads/{file.filename}",
            "card_info": card_info,
            "price_data": price_data,
            "message": response_text
        }

    except requests.exceptions.ConnectionError:
        logger.error("Ollama connection error - make sure Ollama is running on http://localhost:11434")
        return {
            "success": False,
            "error": "Ollama が起動していません。以下を実行してください: ollama serve",
            "image_url": None
        }
    except Exception as e:
        logger.error(f"Image upload error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "image_url": None
        }

@app.get("/api/search-market-price")
def search_market_price(name: str):
    try:
        # TCGPlayer API を試す
        try:
            search_url = f"https://api.tcgplayer.com/catalog/products?q={name}&limit=1"
            response = requests.get(search_url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if data.get("results"):
                    product = data["results"][0]
                    market_price = product.get("marketPrice", product.get("lowestListingPrice", 50))
                    return {
                        "name": name,
                        "market_price": float(market_price) if market_price else 50.0,
                        "source": "TCGPlayer",
                        "found": True
                    }
        except:
            pass

        # フォールバック：推定相場
        base_price = 30.0
        name_factor = len(name.split()) * 5
        market_price = base_price + name_factor + (len(name) % 50)

        return {
            "name": name,
            "market_price": round(market_price, 2),
            "source": "estimate",
            "found": False,
            "note": "推定相場を表示しています。"
        }

    except Exception as e:
        return {
            "error": f"相場検索に失敗しました: {str(e)}",
            "market_price": 50.0,
            "name": name
        }

# ============= TCG Price API（カドラバ相場検索） =============

@app.get("/api/search-card-price")
def search_card_price(name: str, game: str = "pokemon-japanese"):
    """
    TCG Price API を使ったカード相場検索
    複数候補を返す

    Query params:
    - name: カード名（日本語対応）
    - game: ゲームタイプ (pokemon-japanese, one-piece, yu-gi-oh など)
    """
    try:
        results = card_price_lookup.search_cards(name, game=game, limit=5)
        return {
            "success": True,
            "query": name,
            "game": game,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Card price lookup error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "query": name,
            "results": []
        }

@app.get("/api/card-price/{card_id}")
def get_card_price_details(card_id: str):
    """
    カード ID で詳細情報を取得

    Path params:
    - card_id: カード ID
    """
    try:
        card = card_price_lookup.get_card_details(card_id)
        if card:
            return {
                "success": True,
                "card": card
            }
        else:
            return {
                "success": False,
                "error": "カードが見つかりません",
                "card_id": card_id
            }
    except Exception as e:
        logger.error(f"Card details lookup error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "card_id": card_id
        }

# ============= 記事生成・投稿 API =============

@app.post("/api/generate-articles")
async def generate_articles(num_articles: int = 3):
    """Generate articles manually and save to database"""
    db = SessionLocal()
    try:
        from article_generator import ArticleGenerator
        generator = ArticleGenerator()
        articles = await generator.generate_daily_articles(num_articles)

        # Save articles to database
        saved_articles = []
        for article in articles:
            article_log = ArticleLog(
                title=article.get("title"),
                content=article.get("content"),
                category=article.get("category", "strategy"),
                related_sales_ids=article.get("related_sales_ids"),
                status="draft"
            )
            db.add(article_log)
            db.commit()
            db.refresh(article_log)
            saved_articles.append(article_log)

        logger.info(f"Generated and saved {len(saved_articles)} articles")

        return {
            "success": True,
            "count": len(saved_articles),
            "articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "content": a.content,
                    "category": a.category,
                    "status": a.status
                }
                for a in saved_articles
            ]
        }
    except Exception as e:
        logger.error(f"Error generating articles: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        db.close()

@app.post("/api/publish-articles")
async def publish_articles():
    """Generate and publish articles to note & X"""
    try:
        db = SessionLocal()
        await _generate_and_publish_articles(db)
        db.close()
        return {
            "success": True,
            "message": "Articles published successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/article-logs")
def get_article_logs(limit: int = 20):
    """Get recent article logs"""
    db = SessionLocal()
    articles = db.query(ArticleLog).order_by(ArticleLog.created_at.desc()).limit(limit).all()
    db.close()
    return {
        "articles": articles,
        "total": len(articles)
    }

@app.get("/api/sync-status")
def get_sync_status():
    """Get synchronization status"""
    db = SessionLocal()
    sync_history = db.query(SyncHistory).all()
    pending_sales = db.query(PendingSales).filter(
        PendingSales.status == "pending"
    ).count()
    db.close()
    return {
        "sync_history": sync_history,
        "pending_sales": pending_sales
    }

@app.post("/api/manual-sync")
async def manual_sync():
    """Trigger manual sync"""
    try:
        db = SessionLocal()
        # Run the sync function
        sync_ebay_and_publish()
        db.close()
        return {
            "success": True,
            "message": "Sync triggered"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ============= ノート記事ダッシュボード API =============

class ArticleUpdate(BaseModel):
    title: str
    content: str
    category: str = "strategy"
    hashtags: str = ""
    status: str = "draft"  # draft, ready, published

@app.get("/api/articles-dashboard")
def get_articles_dashboard(status: str = None, limit: int = 50):
    """Get articles for dashboard"""
    db = SessionLocal()
    query = db.query(ArticleLog)

    if status:
        query = query.filter(ArticleLog.status == status)

    articles = query.order_by(ArticleLog.updated_at.desc()).limit(limit).all()
    db.close()

    return {
        "articles": articles,
        "total": len(articles)
    }

@app.get("/api/articles/{article_id}")
def get_article(article_id: int):
    """Get article by ID"""
    db = SessionLocal()
    article = db.query(ArticleLog).filter(ArticleLog.id == article_id).first()
    db.close()

    if not article:
        return {"error": "Article not found"}, 404

    return article

@app.put("/api/articles/{article_id}")
def update_article(article_id: int, article_data: ArticleUpdate):
    """Update article"""
    db = SessionLocal()
    article = db.query(ArticleLog).filter(ArticleLog.id == article_id).first()

    if not article:
        return {"error": "Article not found"}, 404

    article.title = article_data.title
    article.content = article_data.content
    article.category = article_data.category
    article.status = article_data.status
    article.updated_at = datetime.now()

    db.commit()
    db.refresh(article)
    db.close()

    return {
        "success": True,
        "article": article
    }

@app.post("/api/articles/{article_id}/publish-to-note")
async def publish_to_note(article_id: int):
    """Publish article to note (with manual confirmation)"""
    db = SessionLocal()
    article = db.query(ArticleLog).filter(ArticleLog.id == article_id).first()

    if not article:
        return {"error": "Article not found"}, 404

    try:
        from note_client import NotePublisher

        note_pub = NotePublisher()

        # Determine if paid or free based on status
        is_paid = article.category in ["strategy", "analysis"]
        price = 1800 if is_paid else 0

        result = await note_pub.client.publish_article(
            title=article.title,
            content=article.content,
            is_paid=is_paid,
            price=price
        )

        if result:
            article.note_url = result.get("url", "")
            article.published_at = datetime.now()
            article.status = "published"
            db.commit()

            return {
                "success": True,
                "note_url": article.note_url,
                "message": "Published to note successfully"
            }
        else:
            return {
                "success": False,
                "error": "Failed to publish to note"
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        db.close()

@app.get("/api/articles/{article_id}/note-format")
def get_article_note_format(article_id: int):
    """Get article in note-friendly format (markdown)"""
    db = SessionLocal()
    article = db.query(ArticleLog).filter(ArticleLog.id == article_id).first()
    db.close()

    if not article:
        return {"error": "Article not found"}, 404

    # Format for note copy-paste
    note_format = f"""# {article.title}

{article.content}

---

カテゴリー: {article.category}
作成日: {article.created_at.strftime('%Y年%m月%d日')}
"""

    return {
        "article_id": article_id,
        "title": article.title,
        "content": article.content,
        "note_format": note_format,
        "category": article.category
    }

class RefinementRequest(BaseModel):
    title: str
    content: str

@app.post("/api/articles/{article_id}/refine")
def refine_article(article_id: int, request: RefinementRequest):
    """Submit article for Claude Code professional refinement"""
    db = SessionLocal()
    article = db.query(ArticleLog).filter(ArticleLog.id == article_id).first()

    if not article:
        db.close()
        return {"error": "Article not found"}, 404

    try:
        # Log the refinement request for Claude Code to monitor
        logger.info(f"🔧 REFINEMENT REQUEST: Article ID {article_id}")
        logger.info(f"  Title: {request.title}")
        logger.info(f"  Content preview: {request.content[:200]}...")
        logger.info(f"  Full content:\n{request.content}")
        logger.info(f"🔧 END REFINEMENT REQUEST")

        db.close()
        return {
            "success": True,
            "message": "Article submitted for refinement. Claude Code will review and improve it shortly.",
            "article_id": article_id
        }

    except Exception as e:
        logger.error(f"Error submitting refinement: {str(e)}")
        db.close()
        return {
            "success": False,
            "error": str(e)
        }

@app.delete("/api/articles/{article_id}")
def delete_article(article_id: int):
    """Delete article draft"""
    db = SessionLocal()
    article = db.query(ArticleLog).filter(ArticleLog.id == article_id).first()

    if not article:
        return {"error": "Article not found"}, 404

    if article.status == "published":
        return {"error": "Cannot delete published articles"}, 400

    db.delete(article)
    db.commit()
    db.close()

    return {"success": True, "message": "Article deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
