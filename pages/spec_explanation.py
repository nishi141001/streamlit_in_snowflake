"""
機能仕様ページ

PDFチャットアプリケーションの機能仕様を説明するページ
"""

import streamlit as st
from snowflake.snowpark.context import get_active_session

# ページ設定
st.set_page_config(
    page_title="機能仕様 - PDF Chat Analyst",
    page_icon="📋",
    layout="wide",
)

# カスタムCSS
st.markdown(
    """
<style>
/* 手書き風の日本語フォント */
@import url('https://fonts.googleapis.com/css2?family=Kaisei+Decol&display=swap');

/* 全体背景色 */
body, .reportview-container {
    background-color: #F6FAFE !important;
}

/* 文章部分の設定 */
.article {
    font-family: 'Kaisei Decol', sans-serif;
    width: 100%;
    margin: 0 auto;
    padding: 1em;
    color: #334155;
    line-height: 1.6;
}

/* タイトルの装飾 */
h1 {
    font-size: 32px;
    font-weight: bold;
    background: linear-gradient(to right, #63C0F6, #1FAEFF);
    -webkit-background-clip: text;
    color: transparent;
    margin-bottom: 0.2em;
    display: inline-block;
    padding-left: 0.2em;
}

/* セクション見出しの設定 */
h3 {
    font-size: 20px;
    color: #1e40af;
    margin-top: 1.4em;
    margin-bottom: 0.5em;
    position: relative;
    padding-left: 2em;
    font-weight: bold;
}
h3::before {
    content: "📋";
    position: absolute;
    left: 0;
}

/* カード風の装飾 */
.section-card {
    background-color: #FFFFFF;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    margin: 1em 0;
    padding: 1.2em 1.5em;
    border-left: 6px solid #63C0F6;
}

/* 強調用クラス */
.note {
    display: inline-block;
    background-color: #DAF1FF;
    border-radius: 4px;
    padding: 2px 6px;
    margin: 0 4px;
}
.marker {
    background-color: #A9DFFF;
    padding: 0 4px;
    border-radius: 2px;
}
.arrow {
    color: #1B95E0;
    font-weight: bold;
}

/* 機能カード */
.feature-card {
    display: flex;
    align-items: flex-start;
    margin: 0.8em 0;
    background-color: #FFFFFF;
    border-radius: 8px;
    padding: 1em;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    border: 1px solid #E2E8F0;
}
.feature-icon {
    font-size: 1.5em;
    margin-right: 1em;
    color: #1FAEFF;
}
.feature-content {
    flex: 1;
}
.feature-title {
    font-weight: bold;
    color: #1e40af;
    margin-bottom: 0.3em;
}
.feature-description {
    color: #475569;
    font-size: 0.95em;
}

/* フッター */
footer {
    text-align: right;
    font-size: 12px;
    color: #475569;
    margin-top: 2em;
    opacity: 0.7;
}
</style>
""",
    unsafe_allow_html=True
)

# ヘッダー
st.markdown(
    """
    <div class="article">
        <header style="display:flex; flex-direction:column; align-items:flex-start;">
            <h1>📋 PDF Chat Analyst - 機能仕様</h1>
        </header>
    </div>
    """,
    unsafe_allow_html=True
)

# アプリケーション概要
st.markdown(
    """
    <div class="article">
        <div class="section-card">
            <h3>アプリケーション概要</h3>
            <p>
                PDF Chat Analystは、<strong>Snowflake Cortex</strong>を活用した
                <span class="note">PDF文書分析・チャットアプリケーション</span>です。
                複数のPDFファイルを同時に分析し、
                <span class="marker">自然言語での質問応答</span>や
                <span class="marker">文書要約</span>を実現します。
            </p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# コア機能
st.markdown(
    """
    <div class="article">
        <div class="section-card">
            <h3>コア機能</h3>
            
            <div class="feature-card">
                <div class="feature-icon">📚</div>
                <div class="feature-content">
                    <div class="feature-title">複数PDF管理</div>
                    <div class="feature-description">
                        複数のPDFファイルを同時にアップロード・管理。
                        文書間の横断的な分析が可能です。
                    </div>
                </div>
            </div>

            <div class="feature-card">
                <div class="feature-icon">🔍</div>
                <div class="feature-content">
                    <div class="feature-title">ハイブリッド検索</div>
                    <div class="feature-description">
                        セマンティック検索とキーワード検索を組み合わせた
                        高精度な検索機能を提供します。
                    </div>
                </div>
            </div>

            <div class="feature-card">
                <div class="feature-icon">💬</div>
                <div class="feature-content">
                    <div class="feature-title">インテリジェントチャット</div>
                    <div class="feature-description">
                        Snowflake Cortexを活用した自然な対話インターフェース。
                        文脈を理解した回答を生成します。
                    </div>
                </div>
            </div>

            <div class="feature-card">
                <div class="feature-icon">📊</div>
                <div class="feature-content">
                    <div class="feature-title">高度な分析機能</div>
                    <div class="feature-description">
                        使用パターン分析、セッション統計、トピック進化分析など、
                        詳細な分析機能を提供します。
                    </div>
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# 技術的特徴
st.markdown(
    """
    <div class="article">
        <div class="section-card">
            <h3>技術的特徴</h3>
            <ul style="margin-left:1em;">
                <li><span class="arrow">🔧</span> <strong>Snowflake Cortex統合</strong>：高度なAI機能を活用</li>
                <li><span class="arrow">🔧</span> <strong>ベクトル検索</strong>：VECTOR_COSINE_SIMILARITYによる高速検索</li>
                <li><span class="arrow">🔧</span> <strong>キャッシュ管理</strong>：効率的なデータキャッシング</li>
                <li><span class="arrow">🔧</span> <strong>エラーハンドリング</strong>：堅牢な例外処理</li>
            </ul>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# 分析機能の詳細
st.markdown(
    """
    <div class="article">
        <div class="section-card">
            <h3>分析機能の詳細</h3>
            
            <div class="feature-card">
                <div class="feature-icon">📈</div>
                <div class="feature-content">
                    <div class="feature-title">使用パターン分析</div>
                    <div class="feature-description">
                        • 時間帯別の使用状況<br>
                        • セッション統計<br>
                        • 応答時間分析<br>
                        • フィードバック統計
                    </div>
                </div>
            </div>

            <div class="feature-card">
                <div class="feature-icon">🔎</div>
                <div class="feature-content">
                    <div class="feature-title">検索パターン分析</div>
                    <div class="feature-description">
                        • クエリカテゴリ分析<br>
                        • クエリの複雑さ分析<br>
                        • ソースの有効性分析<br>
                        • 頻出キーワード抽出
                    </div>
                </div>
            </div>

            <div class="feature-card">
                <div class="feature-icon">📊</div>
                <div class="feature-content">
                    <div class="feature-title">トレンド分析</div>
                    <div class="feature-description">
                        • トピックの進化分析<br>
                        • 時系列変化の可視化<br>
                        • トレンドトピックの抽出<br>
                        • カスタマイズ可能な分析期間
                    </div>
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# フッター
st.markdown(
    """
    <div class="article">
        <footer>
            © 2024 PDF Chat Analyst - Powered by Snowflake Cortex
        </footer>
    </div>
    """,
    unsafe_allow_html=True
)

# 現在の接続情報を表示
try:
    session = get_active_session()
    if session:
        current_db = session.get_current_database()
        current_schema = session.get_current_schema()
        current_warehouse = session.get_current_warehouse()
        st.sidebar.subheader("現在の接続情報")
        st.sidebar.info(
            f"データベース: {current_db}\n"
            f"スキーマ: {current_schema}\n"
            f"ウェアハウス: {current_warehouse}"
        )
except Exception as e:
    st.sidebar.warning("Snowflake接続を確立できませんでした。") 