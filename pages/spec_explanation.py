"""
機能仕様ページ

PDFチャットアプリケーションの機能仕様を説明するページ
"""

import streamlit as st
from snowflake.snowpark.context import get_active_session



st.set_page_config(
    page_title="機能仕様 - PDF Chat Analyst",
    page_icon="📋",
    layout="wide",
)

st.markdown("""
<style>
body, .reportview-container {
    background-color: #F6FAFE !important;
}
.section-card {
    background-color: #FFFFFF;
    border-radius: 14px;
    box-shadow: 0 2px 8px rgba(31,174,255,0.08);
    margin: 1em 0 2em 0;
    padding: 1.35em 1.3em 1.1em 1.3em;
    border-left: 7px solid #1FAEFF;
}
.section-title {
    font-size: 1.28em;
    font-weight: bold;
    color: #1e40af;
    margin-bottom: 0.5em;
    display: flex;
    align-items: center;
    gap: 0.5em;
}
.grid-2col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
    margin-bottom: 2em;
}
@media (max-width: 800px) {
    .grid-2col { grid-template-columns: 1fr; }
}
.card-core, .card-detail {
    border-radius: 11px;
    padding: 1em 1.15em 0.9em 1.15em;
    display: flex;
    align-items: flex-start;
    gap: 0.85em;
    min-height: 98px;
    box-shadow: 0 1px 8px rgba(31,174,255,0.04);
}
.card-core {
    background: linear-gradient(105deg, #EAF6FF 80%, #F6FAFE 100%);
    border-left: 6px solid #63C0F6;
}
.card-detail {
    background: linear-gradient(105deg, #F3F8FB 82%, #F6FAFE 100%);
    border-left: 6px solid #90D6F6;
}
.icon-core, .icon-detail {
    font-size: 1.85em;
    min-width: 2.0em;
    text-align: center;
    margin-top: 2px;
}
.icon-core { color: #1FAEFF; }
.icon-detail { color: #63C0F6; }
.card-content { flex: 1; }
.card-title {
    font-weight: bold;
    font-size: 1.04em;
    margin-bottom: 4px;
}
.card-title-core { color: #2773B0; }
.card-title-detail { color: #3399CC; }
.card-desc-core {
    color: #477088;
    font-size: 0.99em;
}
.card-desc-detail {
    color: #476681;
    font-size: 0.98em;
}
ul.tech-list li {
    margin-bottom: 0.3em;
    font-size: 1.03em;
}
footer {
    text-align: right;
    font-size: 13px;
    color: #475569;
    margin-top: 2em;
    opacity: 0.75;
}
</style>
""", unsafe_allow_html=True)

# 概要
st.markdown("""
<div class="section-card">
  <div class="section-title">📋 PDF Chat Analyst - 機能仕様</div>
  <p>
    <span style="font-weight:600; color:#1FAEFF;">PDF Chat Analyst</span>は、Snowflake Cortexを活用したPDF文書分析・チャットアプリケーションです。<br>
    <strong>複数PDFの同時分析・自然言語での質問応答・文書要約・詳細な分析機能</strong>を備えています。
  </p>
</div>
""", unsafe_allow_html=True)

# コア機能（淡色カード/2列グリッド）
st.markdown("""
<div class="section-card">
  <div class="section-title">🔑 コア機能</div>
  <div class="grid-2col">
    <div class="card-core">
      <div class="icon-core">📚</div>
      <div class="card-content">
        <div class="card-title card-title-core">複数PDF管理</div>
        <div class="card-desc-core">
          複数のPDFを同時にアップロード・管理し、文書間の横断分析が可能。
        </div>
      </div>
    </div>
    <div class="card-core">
      <div class="icon-core">🔍</div>
      <div class="card-content">
        <div class="card-title card-title-core">ハイブリッド検索</div>
        <div class="card-desc-core">
          セマンティック検索とキーワード検索を組み合わせた高精度な検索機能。
        </div>
      </div>
    </div>
    <div class="card-core">
      <div class="icon-core">💬</div>
      <div class="card-content">
        <div class="card-title card-title-core">インテリジェントチャット</div>
        <div class="card-desc-core">
          Snowflake Cortexを活用した自然な対話インターフェースで文脈理解した回答を生成。
        </div>
      </div>
    </div>
    <div class="card-core">
      <div class="icon-core">📊</div>
      <div class="card-content">
        <div class="card-title card-title-core">高度な分析機能</div>
        <div class="card-desc-core">
          使用パターン分析、セッション統計、トピック進化分析など詳細な分析機能。
        </div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# 技術的特徴
st.markdown("""
<div class="section-card">
  <div class="section-title">🛠 技術的特徴</div>
  <ul class="tech-list">
    <li>🔧 <strong>Snowflake Cortex統合：</strong>高度なAI機能（質問応答・要約・埋め込み）を活用</li>
    <li>🔧 <strong>ベクトル検索：</strong>VECTOR_COSINE_SIMILARITYによる高速なセマンティック検索</li>
    <li>🔧 <strong>キャッシュ管理：</strong>効率的なデータキャッシング機能</li>
    <li>🔧 <strong>エラーハンドリング：</strong>堅牢な例外処理・ログ管理</li>
  </ul>
</div>
""", unsafe_allow_html=True)

# 分析機能の詳細（より淡いブルー系カード/2列グリッド）
st.markdown("""
<div class="section-card">
  <div class="section-title">📈 分析機能の詳細</div>
  <div class="grid-2col">
    <div class="card-detail">
      <div class="icon-detail">📈</div>
      <div class="card-content">
        <div class="card-title card-title-detail">使用パターン分析</div>
        <div class="card-desc-detail">
          ・時間帯別の使用状況<br>
          ・セッション統計<br>
          ・応答時間分析<br>
          ・フィードバック統計
        </div>
      </div>
    </div>
    <div class="card-detail">
      <div class="icon-detail">🔎</div>
      <div class="card-content">
        <div class="card-title card-title-detail">検索パターン分析</div>
        <div class="card-desc-detail">
          ・クエリカテゴリ分析<br>
          ・クエリの複雑さ分析<br>
          ・ソースの有効性分析<br>
          ・頻出キーワード抽出
        </div>
      </div>
    </div>
    <div class="card-detail">
      <div class="icon-detail">📊</div>
      <div class="card-content">
        <div class="card-title card-title-detail">トレンド分析</div>
        <div class="card-desc-detail">
          ・トピックの進化分析<br>
          ・時系列変化の可視化<br>
          ・トレンドトピックの抽出<br>
          ・カスタマイズ可能な分析期間
        </div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# フッター
st.markdown("""
<footer>
  © 2024 PDF Chat Analyst - Powered by Snowflake Cortex
</footer>
""", unsafe_allow_html=True)

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