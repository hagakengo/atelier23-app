import React, { useState, useEffect } from 'react';
import './App.css';
import { ArticleDashboard } from './ArticleDashboard';

interface Card {
  id: number;
  name: string;
  game_type: string;
  series: string;
  grade: string;
  market_price: number;
  your_price: number;
  cost: number;
  profit: number;
  profit_rate: number;
  ebay_fee: number;
  paypal_fee: number;
  total_fees: number;
  domestic_shipping: number;
  overseas_shipping: number;
  your_price_after_fees: number;
}

interface SaleRecord {
  id: number;
  card_id: number;
  sold_price: number;
  actual_profit: number;
  ebay_fee: number;
  paypal_fee: number;
  total_fees: number;
}

interface Analytics {
  total_items_listed: number;
  total_items_sold: number;
  total_potential_profit: number;
  total_actual_profit: number;
  average_profit_per_card: number;
}

const API_BASE = 'http://localhost:9000';

function App() {
  const [cards, setCards] = useState<Card[]>([]);
  const [sales, setSales] = useState<SaleRecord[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [activeTab, setActiveTab] = useState('inventory');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({ name: '', game_type: '', series: '', grade: '', market_price: '' });
  const [saleForm, setSaleForm] = useState({
    card_id: '',
    sold_price: '',
    cost: '',
    ebay_fee: 0,
    paypal_fee: 0,
    total_fees: 0,
    actual_profit: 0
  });
  const [success, setSuccess] = useState('');
  const [searching, setSearching] = useState(false);
  const [priceResults, setPriceResults] = useState<any[]>([]);
  const [showPriceResults, setShowPriceResults] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError('');
    try {
      const [cardsRes, salesRes, analyticsRes] = await Promise.all([
        fetch(`${API_BASE}/api/cards`),
        fetch(`${API_BASE}/api/sales`),
        fetch(`${API_BASE}/api/analytics`),
      ]);

      if (!cardsRes.ok || !salesRes.ok || !analyticsRes.ok) {
        throw new Error('データ取得に失敗しました');
      }

      const cardsData = await cardsRes.json();
      const salesData = await salesRes.json();
      const analyticsData = await analyticsRes.json();

      setCards(cardsData);
      setSales(salesData.sales || []);
      setAnalytics(analyticsData);
    } catch (err) {
      setError('バックエンドに接続できません。http://localhost:9000 が起動していることを確認してください。');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const searchMarketPrice = async (cardName: string) => {
    if (!cardName.trim() || cardName.length < 2) return;

    setSearching(true);
    try {
      const response = await fetch(`${API_BASE}/api/search-market-price?name=${encodeURIComponent(cardName)}`);
      if (response.ok) {
        const data = await response.json();
        if (data.market_price) {
          setFormData(prev => ({
            ...prev,
            market_price: data.market_price.toString()
          }));
        }
      }
    } catch (err) {
      console.error('市場価格検索に失敗:', err);
    } finally {
      setSearching(false);
    }
  };

  const handleAddCard = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!formData.name || !formData.game_type || !formData.series || !formData.market_price) {
      setError('すべての項目を入力してください');
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/cards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formData.name,
          game_type: formData.game_type,
          series: formData.series,
          grade: formData.grade || 'N/A',
          market_price: parseFloat(formData.market_price),
        }),
      });

      if (!response.ok) throw new Error('カード追加失敗');

      setFormData({ name: '', game_type: '', series: '', grade: '', market_price: '' });
      setSuccess('カードを追加しました！');
      await fetchData();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('カード追加に失敗しました');
      console.error(err);
    }
  };

  const handleRecordSale = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!saleForm.card_id || !saleForm.sold_price) {
      setError('カードと販売価格を入力してください');
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/sales`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          card_id: parseInt(saleForm.card_id),
          sold_price: parseFloat(saleForm.sold_price),
        }),
      });

      if (!response.ok) throw new Error('販売記録失敗');

      setSaleForm({ card_id: '', sold_price: '', cost: '', ebay_fee: 0, paypal_fee: 0, total_fees: 0, actual_profit: 0 });
      setSuccess('販売を記録しました！');
      await fetchData();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('販売記録に失敗しました');
      console.error(err);
    }
  };

  const handleDeleteCard = async (id: number) => {
    if (confirm('このカードを削除してもよろしいですか？')) {
      try {
        const response = await fetch(`${API_BASE}/api/cards/${id}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('削除失敗');
        setSuccess('カードを削除しました');
        await fetchData();
        setTimeout(() => setSuccess(''), 3000);
      } catch (err) {
        setError('カード削除に失敗しました');
        console.error(err);
      }
    }
  };

  return (
    <div className="App">
      <header className="header">
        <div className="header-content">
          <h1>🎴 Atelier 23</h1>
          <p className="subtitle">eBayカード販売管理ツール</p>
        </div>
      </header>

      <nav className="nav">
        <button
          className={`nav-btn ${activeTab === 'inventory' ? 'active' : ''}`}
          onClick={() => setActiveTab('inventory')}
        >
          <span className="nav-icon">📦</span>
          <span className="nav-label">在庫管理</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'sales' ? 'active' : ''}`}
          onClick={() => setActiveTab('sales')}
        >
          <span className="nav-icon">💰</span>
          <span className="nav-label">販売記録</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'analytics' ? 'active' : ''}`}
          onClick={() => setActiveTab('analytics')}
        >
          <span className="nav-icon">📊</span>
          <span className="nav-label">分析</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'articles' ? 'active' : ''}`}
          onClick={() => setActiveTab('articles')}
        >
          <span className="nav-icon">📝</span>
          <span className="nav-label">Note記事</span>
        </button>
      </nav>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <main className="main">
        {loading && (
          <div className="loading-spinner">
            <div className="spinner"></div>
            <p>読み込み中...</p>
          </div>
        )}

        {!loading && activeTab === 'inventory' && (
          <div className="tab-content">
            <div className="tab-header">
              <h2>📦 在庫管理</h2>
              <p>カード情報を追加・管理します</p>
            </div>

            <form className="form" onSubmit={handleAddCard}>
              <div className="form-section">
                <h3>新しいカードを追加</h3>

                <div className="image-upload-section">
                  <label className={`image-upload-label ${uploadingImage ? 'uploading' : ''}`}>
                    {uploadingImage ? (
                      <>
                        <span className="spinner"></span> 読み込み中...
                      </>
                    ) : (
                      <>📸 カード画像をアップロード（自動認識）</>
                    )}
                    <input
                      type="file"
                      accept="image/*"
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;

                        setUploadingImage(true);
                        const formDataImage = new FormData();
                        formDataImage.append('file', file);

                        try {
                          const response = await fetch(`${API_BASE}/api/upload-card-image`, {
                            method: 'POST',
                            body: formDataImage,
                          });
                          const data = await response.json();
                          if (data.success && data.card_info) {
                            setFormData({
                              ...formData,
                              name: data.card_info.name || formData.name,
                              game_type: data.card_info.game_type || formData.game_type,
                              series: data.card_info.series || formData.series,
                              grade: data.card_info.grade || formData.grade,
                            });
                            // 相場情報を表示
                            if (data.price_data && data.price_data.length > 0) {
                              setPriceResults(data.price_data);
                              setShowPriceResults(true);
                            }
                            // 市場価格を自動検索
                            if (data.card_info.name) {
                              setTimeout(() => searchMarketPrice(data.card_info.name), 500);
                            }
                            setSuccess('✅ カード情報を認識しました！');
                            setTimeout(() => setSuccess(''), 3000);
                          }
                        } catch (err) {
                          console.error('画像アップロード失敗:', err);
                          setError('画像アップロードに失敗しました');
                        } finally {
                          setUploadingImage(false);
                        }
                      }}
                      className="image-input"
                      hidden
                    />
                  </label>
                </div>

                {(uploadingImage || showPriceResults) && (
                  <div className={`price-results-section ${priceResults.length === 0 ? 'loading' : ''}`}>
                    <h4>
                      {uploadingImage ? (
                        <>
                          <span className="spinner-inline"></span> 相場情報を取得中...
                        </>
                      ) : (
                        <>📊 検索された相場情報</>
                      )}
                    </h4>
                    {priceResults.length > 0 && (
                      <>
                        <div className="price-results-grid">
                          {priceResults.map((card, idx) => (
                            <div key={idx} className="price-result-card">
                              {card.image_url && (
                                <img src={card.image_url} alt={card.name} className="card-thumbnail" />
                              )}
                              <div className="price-info">
                                <div className="card-name">{card.name}</div>
                                <div className="card-set">{card.set_name} {card.card_number}</div>
                                <div className="price-display">
                                  <div className="market-price">
                                    <span className="label">相場:</span>
                                    <span className="price">¥{card.prices?.market || card.prices?.mid || 'N/A'}</span>
                                  </div>
                                  {card.price_change !== undefined && (
                                    <div className={`price-change ${card.price_change >= 0 ? 'up' : 'down'}`}>
                                      {card.price_change >= 0 ? '📈' : '📉'} {card.price_change.toFixed(2)}%
                                    </div>
                                  )}
                                </div>
                                <button
                                  className="btn-select-price"
                                  onClick={() => {
                                    setFormData({
                                      ...formData,
                                      market_price: card.prices?.market?.toString() || ''
                                    });
                                    setShowPriceResults(false);
                                    setSuccess(`${card.name} の相場を反映しました`);
                                    setTimeout(() => setSuccess(''), 3000);
                                  }}
                                >
                                  この相場を使用
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                        <button
                          className="btn-close-results"
                          onClick={() => setShowPriceResults(false)}
                        >
                          閉じる
                        </button>
                      </>
                    )}
                  </div>
                )}

                <div className="form-grid">
                  <div className="form-group">
                    <label>ゲームの種類</label>
                    <select
                      value={formData.game_type}
                      onChange={(e) => setFormData({...formData, game_type: e.target.value})}
                      required
                    >
                      <option value="">-- 選択してください --</option>
                      <option value="ポケモンカード">ポケモンカード</option>
                      <option value="ワンピースカード">ワンピースカード</option>
                      <option value="遊戯王">遊戯王</option>
                      <option value="ドラゴンボールヒーローズ">ドラゴンボールヒーローズ</option>
                      <option value="MTG">MTG</option>
                      <option value="その他">その他</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>
                      カード名
                      {searching && <span className="searching-icon">🔍</span>}
                    </label>
                    <input
                      type="text"
                      placeholder="例：Charizard"
                      value={formData.name}
                      onChange={(e) => {
                        setFormData({...formData, name: e.target.value});
                        // 1秒後に市場価格検索
                        setTimeout(() => searchMarketPrice(e.target.value), 500);
                      }}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>シリーズ</label>
                    <input
                      type="text"
                      placeholder="例：Base Set"
                      value={formData.series}
                      onChange={(e) => setFormData({...formData, series: e.target.value})}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>グレード <span style={{ opacity: 0.6, fontSize: '0.8em' }}>(オプション)</span></label>
                    <input
                      type="text"
                      placeholder="例：PSA 9"
                      value={formData.grade}
                      onChange={(e) => setFormData({...formData, grade: e.target.value})}
                    />
                  </div>
                  <div className="form-group">
                    <label>市場価格 (¥)</label>
                    <input
                      type="number"
                      placeholder="0"
                      step="1"
                      value={formData.market_price}
                      onChange={(e) => setFormData({...formData, market_price: e.target.value})}
                      required
                    />
                  </div>
                </div>
                <button type="submit" className="btn btn-primary">追加</button>
              </div>
            </form>

            <div className="table-wrapper">
              <h3>📋 カード一覧</h3>
              {cards.length === 0 ? (
                <div className="empty-state">
                  <div style={{ fontSize: '3em', marginBottom: '12px' }}>📦</div>
                  <p>まだカードが登録されていません</p>
                  <p style={{ marginTop: '8px', fontSize: '0.9em', opacity: 0.7 }}>上のフォームからカードを追加してください</p>
                </div>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th>カード名</th>
                      <th>ゲーム</th>
                      <th>シリーズ</th>
                      <th>グレード</th>
                      <th>市場価格</th>
                      <th>手数料</th>
                      <th>国内実利益</th>
                      <th>海外実利益</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cards.map((card) => (
                      <tr key={card.id}>
                        <td><strong>{card.name}</strong></td>
                        <td>{card.game_type}</td>
                        <td>{card.series}</td>
                        <td>{card.grade}</td>
                        <td>¥{Math.round(card.market_price)}</td>
                        <td>¥{Math.round(card.total_fees)}</td>
                        <td className="profit-positive"><strong>¥{Math.round(card.market_price - card.total_fees - card.domestic_shipping)}</strong></td>
                        <td className="profit-positive"><strong>¥{Math.round(card.market_price - card.total_fees - card.overseas_shipping)}</strong></td>
                        <td>
                          <button className="btn btn-danger btn-sm" onClick={() => handleDeleteCard(card.id)}>
                            削除
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {!loading && activeTab === 'sales' && (
          <div className="tab-content">
            <div className="tab-header">
              <h2>💰 販売記録</h2>
              <p>販売した情報を記録します</p>
            </div>

            <form className="form" onSubmit={handleRecordSale}>
              <div className="form-section">
                <h3>販売を記録</h3>
                <div className="form-grid">
                  <div className="form-group">
                    <label>カード選択</label>
                    <select
                      value={saleForm.card_id}
                      onChange={(e) => setSaleForm({...saleForm, card_id: e.target.value})}
                      required
                    >
                      <option value="">-- 選択してください --</option>
                      {cards.map((card) => (
                        <option key={card.id} value={card.id}>
                          {card.name} (¥{Math.round(card.your_price)})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>実際の販売価格 (¥)</label>
                    <input
                      type="number"
                      placeholder="0"
                      step="1"
                      value={saleForm.sold_price}
                      onChange={(e) => {
                        const price = parseFloat(e.target.value) || 0;
                        const ebay_fee = Math.round(price * 0.129 * 100) / 100;
                        const paypal_fee = Math.round((price * 0.0349 + 40) * 100) / 100;
                        const total_fees = ebay_fee + paypal_fee;
                        const cost = parseFloat(saleForm.cost) || 0;
                        const actual_profit = price - total_fees - cost;
                        setSaleForm({
                          ...saleForm,
                          sold_price: e.target.value,
                          ebay_fee,
                          paypal_fee,
                          total_fees,
                          actual_profit
                        });
                      }}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>仕入原価 (¥)</label>
                    <input
                      type="number"
                      placeholder="0"
                      step="1"
                      value={saleForm.cost}
                      onChange={(e) => {
                        const cost = parseFloat(e.target.value) || 0;
                        const sold_price = parseFloat(saleForm.sold_price) || 0;
                        const actual_profit = sold_price - saleForm.total_fees - cost;
                        setSaleForm({
                          ...saleForm,
                          cost: e.target.value,
                          actual_profit
                        });
                      }}
                      required
                    />
                  </div>
                </div>

                {saleForm.sold_price && (
                  <div style={{
                    background: 'rgba(99, 102, 241, 0.08)',
                    border: '1px solid rgba(99, 102, 241, 0.3)',
                    borderRadius: '8px',
                    padding: '16px',
                    marginTop: '16px',
                    fontSize: '0.95em'
                  }}>
                    <h4 style={{ marginBottom: '12px', color: '#6366f1' }}>💰 収益計算</h4>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div>販売価格: <strong>¥{Math.round(parseFloat(saleForm.sold_price) || 0)}</strong></div>
                      <div>仕入原価: <strong>¥{Math.round(parseFloat(saleForm.cost) || 0)}</strong></div>
                      <div>eBay手数料 (12.9%): <span style={{ color: '#ef4444' }}>-¥{Math.round(saleForm.ebay_fee)}</span></div>
                      <div>PayPal手数料 (3.49%+¥40): <span style={{ color: '#ef4444' }}>-¥{Math.round(saleForm.paypal_fee)}</span></div>
                      <div style={{ gridColumn: '1 / -1', borderTop: '1px solid rgba(99, 102, 241, 0.2)', paddingTop: '8px', marginTop: '4px' }}>
                        実利益（送料別）: <strong style={{ color: '#10b981', fontSize: '1.1em' }}>¥{Math.round(saleForm.actual_profit)}</strong>
                      </div>
                    </div>
                  </div>
                )}

                <button type="submit" className="btn btn-primary" style={{ marginTop: '16px' }}>記録</button>
              </div>
            </form>

            <div className="table-wrapper">
              <h3>💾 販売記録一覧</h3>
              {sales.length === 0 ? (
                <div className="empty-state">
                  <div style={{ fontSize: '3em', marginBottom: '12px' }}>🛒</div>
                  <p>まだ販売記録がありません</p>
                  <p style={{ marginTop: '8px', fontSize: '0.9em', opacity: 0.7 }}>カードを販売したら記録してください</p>
                </div>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th>カードID</th>
                      <th>販売価格</th>
                      <th>eBay手数料</th>
                      <th>PayPal手数料</th>
                      <th>合計手数料</th>
                      <th>実利益</th>
                      <th>日時</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sales.map((sale) => (
                      <tr key={sale.id}>
                        <td>#{sale.card_id}</td>
                        <td>¥{Math.round(sale.sold_price)}</td>
                        <td style={{ color: '#ef4444' }}>¥{Math.round(sale.ebay_fee)}</td>
                        <td style={{ color: '#ef4444' }}>¥{Math.round(sale.paypal_fee)}</td>
                        <td style={{ color: '#ef4444' }}><strong>¥{Math.round(sale.total_fees)}</strong></td>
                        <td className="profit-positive"><strong>¥{sale.actual_profit.toFixed(0)}</strong></td>
                        <td>{new Date().toLocaleDateString('ja-JP')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {!loading && activeTab === 'analytics' && (
          <div className="tab-content">
            <div className="tab-header">
              <h2>📊 分析ダッシュボード</h2>
              <p>売上と利益の概要</p>
            </div>

            {analytics ? (
              <div className="analytics-grid">
                <div className="stat-card">
                  <div className="stat-icon">📦</div>
                  <h3>登録カード数</h3>
                  <p className="stat-value">{analytics.total_items_listed}</p>
                  <p className="stat-label">枚</p>
                </div>
                <div className="stat-card">
                  <div className="stat-icon">✅</div>
                  <h3>販売済み</h3>
                  <p className="stat-value">{analytics.total_items_sold}</p>
                  <p className="stat-label">枚</p>
                </div>
                <div className="stat-card">
                  <div className="stat-icon">🎯</div>
                  <h3>見込利益</h3>
                  <p className="stat-value">¥{Math.round(analytics.total_potential_profit)}</p>
                  <p className="stat-label">全在庫</p>
                </div>
                <div className="stat-card profit-card">
                  <div className="stat-icon">💰</div>
                  <h3>確定利益</h3>
                  <p className="stat-value">¥{Math.round(analytics.total_actual_profit)}</p>
                  <p className="stat-label">実績</p>
                </div>
                <div className="stat-card">
                  <div className="stat-icon">📈</div>
                  <h3>平均利益/枚</h3>
                  <p className="stat-value">¥{Math.round(analytics.average_profit_per_card)}</p>
                  <p className="stat-label">1枚あたり</p>
                </div>
              </div>
            ) : (
              <p className="empty-state">分析データがありません</p>
            )}
          </div>
        )}

        {!loading && activeTab === 'articles' && (
          <ArticleDashboard apiBase={API_BASE} />
        )}
      </main>
    </div>
  );
}

export default App;
