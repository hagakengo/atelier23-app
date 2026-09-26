import React, { useState, useEffect } from 'react';

interface Article {
  id: number;
  title: string;
  content: string;
  category: string;
  status: string;
  note_url: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

interface ArticleDashboardProps {
  apiBase: string;
}

export function ArticleDashboard({ apiBase }: ArticleDashboardProps) {
  const [articles, setArticles] = useState<Article[]>([]);
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<'all' | 'draft' | 'ready' | 'published'>('all');
  const [formData, setFormData] = useState({
    title: '',
    content: '',
    category: 'strategy'
  });

  useEffect(() => {
    fetchArticles();
  }, [filter]);

  const fetchArticles = async () => {
    setLoading(true);
    try {
      const url = filter === 'all'
        ? `${apiBase}/api/articles-dashboard`
        : `${apiBase}/api/articles-dashboard?status=${filter}`;

      const res = await fetch(url);
      const data = await res.json();
      setArticles(data.articles || []);
    } catch (err) {
      setError('記事の読み込みに失敗しました');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectArticle = (article: Article) => {
    setSelectedArticle(article);
    setFormData({
      title: article.title,
      content: article.content,
      category: article.category
    });
    setEditMode(false);
  };

  const handleSaveArticle = async () => {
    if (!selectedArticle) return;

    try {
      const res = await fetch(`${apiBase}/api/articles/${selectedArticle.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      if (res.ok) {
        setEditMode(false);
        fetchArticles();
        setSelectedArticle(null);
      }
    } catch (err) {
      setError('保存に失敗しました');
    }
  };

  const handleDeleteArticle = async () => {
    if (!selectedArticle || selectedArticle.status === 'published') return;

    if (!window.confirm('この記事を削除しますか？')) return;

    try {
      const res = await fetch(`${apiBase}/api/articles/${selectedArticle.id}`, {
        method: 'DELETE'
      });

      if (res.ok) {
        fetchArticles();
        setSelectedArticle(null);
      }
    } catch (err) {
      setError('削除に失敗しました');
    }
  };

  const handlePublishToNote = async () => {
    if (!selectedArticle) return;

    try {
      const res = await fetch(`${apiBase}/api/articles/${selectedArticle.id}/publish-to-note`, {
        method: 'POST'
      });

      if (res.ok) {
        const data = await res.json();
        alert(`note に投稿しました: ${data.note_url}`);
        fetchArticles();
      }
    } catch (err) {
      setError('note への投稿に失敗しました');
    }
  };

  const handleCopyNoteFormat = async () => {
    if (!selectedArticle) return;

    try {
      const res = await fetch(`${apiBase}/api/articles/${selectedArticle.id}/note-format`);
      const data = await res.json();

      // Copy to clipboard
      await navigator.clipboard.writeText(data.note_format);
      alert('note 形式でコピーしました');
    } catch (err) {
      setError('コピーに失敗しました');
    }
  };

  const handlePostToNoteQuick = async () => {
    if (!selectedArticle) return;

    try {
      const res = await fetch(`${apiBase}/api/articles/${selectedArticle.id}/note-format`);
      const data = await res.json();

      // Copy to clipboard
      await navigator.clipboard.writeText(data.note_format);

      // Open note new post page in new tab
      window.open('https://note.com/new', '_blank');

      alert('✅ 記事がコピーされました！\n\n開いた note のページで以下を実行：\n1. 本文欄に貼り付け（Ctrl+V）\n2. タイトル・価格を設定\n3. 投稿ボタンをクリック');
    } catch (err) {
      setError('エラーが発生しました');
    }
  };

  return (
    <div className="article-dashboard">
      <div className="dashboard-header">
        <h2>📝 ノート記事ダッシュボード</h2>
        <div className="filter-buttons">
          {(['all', 'draft', 'ready', 'published'] as const).map(status => (
            <button
              key={status}
              className={`filter-btn ${filter === status ? 'active' : ''}`}
              onClick={() => setFilter(status)}
            >
              {status === 'all' && 'すべて'}
              {status === 'draft' && '下書き'}
              {status === 'ready' && '準備完了'}
              {status === 'published' && '投稿済み'}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="dashboard-layout">
        {/* 記事リスト */}
        <div className="articles-list">
          <h3>記事一覧 ({articles.length})</h3>
          {loading ? (
            <p>読み込み中...</p>
          ) : (
            <div className="article-items">
              {articles.map(article => (
                <div
                  key={article.id}
                  className={`article-item ${selectedArticle?.id === article.id ? 'selected' : ''}`}
                  onClick={() => handleSelectArticle(article)}
                >
                  <div className="article-title">{article.title}</div>
                  <div className="article-meta">
                    <span className={`status ${article.status}`}>{article.status}</span>
                    <span className="category">{article.category}</span>
                    <span className="date">{new Date(article.updated_at).toLocaleDateString('ja-JP')}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 記事エディタ */}
        <div className="article-editor">
          {selectedArticle ? (
            <>
              <div className="editor-header">
                <h3>{editMode ? '編集' : 'プレビュー'}</h3>
                {editMode ? (
                  <div className="editor-buttons">
                    <button className="btn-save" onClick={handleSaveArticle}>💾 保存</button>
                    <button className="btn-cancel" onClick={() => setEditMode(false)}>✕ キャンセル</button>
                  </div>
                ) : (
                  <div className="editor-buttons">
                    <button className="btn-edit" onClick={() => setEditMode(true)}>✏️ 編集</button>
                    <button
                      className="btn-copy"
                      onClick={handleCopyNoteFormat}
                    >
                      📋 コピー
                    </button>
                    {selectedArticle.status !== 'published' && (
                      <button
                        className="btn-publish"
                        onClick={handlePostToNoteQuick}
                      >
                        🚀 note で投稿
                      </button>
                    )}
                    <button
                      className="btn-delete"
                      onClick={handleDeleteArticle}
                      disabled={selectedArticle.status === 'published'}
                    >
                      🗑️ 削除
                    </button>
                  </div>
                )}
              </div>

              {editMode ? (
                <div className="edit-form">
                  <div className="form-group">
                    <label>タイトル</label>
                    <input
                      type="text"
                      value={formData.title}
                      onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                      className="form-input"
                    />
                  </div>

                  <div className="form-group">
                    <label>カテゴリー</label>
                    <select
                      value={formData.category}
                      onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                      className="form-select"
                    >
                      <option value="strategy">戦略</option>
                      <option value="tutorial">チュートリアル</option>
                      <option value="analysis">分析</option>
                      <option value="profit_report">利益報告</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label>本文</label>
                    <textarea
                      value={formData.content}
                      onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                      className="form-textarea"
                      rows={20}
                    />
                  </div>
                </div>
              ) : (
                <div className="article-preview">
                  <div className="preview-title">{selectedArticle.title}</div>
                  <div className="preview-meta">
                    <span>カテゴリー: {selectedArticle.category}</span>
                    <span>ステータス: {selectedArticle.status}</span>
                    {selectedArticle.published_at && (
                      <span>投稿日: {new Date(selectedArticle.published_at).toLocaleDateString('ja-JP')}</span>
                    )}
                  </div>
                  <div className="preview-content">
                    {selectedArticle.content.split('\n').map((line, i) => (
                      <p key={i}>{line || <br />}</p>
                    ))}
                  </div>
                  {selectedArticle.note_url && (
                    <div className="note-link">
                      <a href={selectedArticle.note_url} target="_blank" rel="noopener noreferrer">
                        📎 note リンク: {selectedArticle.note_url}
                      </a>
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">
              <p>左から記事を選択してください</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
