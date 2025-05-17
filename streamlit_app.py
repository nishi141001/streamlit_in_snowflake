"""
ChatPDFアプリケーション

機能
- PDFドキュメントのアップロードと管理
- ハイブリッド検索（ベクトル検索 + キーワード検索）
- AI機能（要約生成、質問応答、翻訳）
- カスタムプロンプト管理
- 回答履歴管理
"""

import os
import streamlit as st
from snowflake.snowpark.context import get_active_session
from typing import List, Dict, Optional, Union, Any
import pandas as pd
from datetime import datetime
import json
from components.search_interface import SearchInterface

# アプリケーション設定
from config import SETTINGS, MESSAGES, UI_CONFIG

# ユーティリティ
from utils.pdf_utils import load_pdf, extract_text, get_pdf_metadata, extract_text_with_tables
from utils.vector_utils import calculate_similarity, embed_text, find_relevant_chunks, hybrid_search
from utils.export_utils import export_history_as_csv, export_history_as_markdown

# サービス
from services.chat_service import generate_answer, generate_summary
# from services.embedding_service import embed_documents, embed_query
from services.document_service import DocumentService
from services.search_service import SearchService
from services.ai_service import AIService
from components.ai_interface import AIInterface

# UI コンポーネント
from components.sidebar import render_sidebar
from components.pdf_viewer import render_pdf_viewer
from components.search_panel import render_search_panel
from components.chat_interface import render_chat_interface
from components.analytics_panel import render_analytics_panel

# アプリケーション状態管理
from models.state import initialize_session_state


def init_app_state():
    """
    アプリケーションの状態を初期化
    """
    if 'pdf_contents' not in st.session_state:
        st.session_state.pdf_contents = []
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "search"
    if 'user_id' not in st.session_state:
        st.session_state.user_id = "anonymous"  # TODO: ユーザー認証の実装


def main():
    """メインアプリケーション"""
    # ページ設定
    st.set_page_config(
        page_title="ChatPDF",
        page_icon="��",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # カスタムCSSの適用
    st.markdown(UI_CONFIG["CUSTOM_CSS"], unsafe_allow_html=True)
    
    # セッション状態の初期化
    initialize_session_state()
    
    # Snowflakeセッション取得
    try:
        session = get_active_session()
        st.session_state.snowflake_connected = True
    except Exception as e:
        st.error(f"Snowflakeセッションの取得に失敗しました: {str(e)}")
        st.session_state.snowflake_connected = False
        return
    
    # アプリタイトルとナビゲーション
    st.markdown(
        """
        <div style="display: flex; align-items: center; margin-bottom: 1em;">
            <h1 style="margin: 0;">❄️ PDF Chat Analyst</h1>
            <div style="margin-left: auto;">
                <a href="/機能仕様" target="_self" style="
                    text-decoration: none;
                    padding: 0.5em 1em;
                    background-color: #1FAEFF;
                    color: white;
                    border-radius: 4px;
                    font-size: 0.9em;
                ">📋 機能仕様</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # サイドバー表示
    uploaded_files = render_sidebar()
    
    # メイン画面
    if not uploaded_files:
        st.info(MESSAGES["UPLOAD_PROMPT"])
        show_features_overview()
        return
    
    # メインコンテンツの描画
    render_main_content()


def render_main_content():
    """メインコンテンツの描画"""
    # ページに応じたコンテンツの表示
    if st.session_state.current_page == "search":
        # 検索インターフェース
        search_interface = SearchInterface()
        search_interface.render_search_interface()
    
    elif st.session_state.current_page == "ai":
        # AIインターフェース
        ai_interface = AIInterface()
        ai_interface.render()
    
    elif st.session_state.current_page == "settings":
        # 設定画面
        render_settings_page()


def render_settings_page():
    """設定画面の描画"""
    st.title("設定")
    
    # アプリケーション設定
    st.header("アプリケーション設定")
    
    # 検索設定
    st.subheader("検索設定")
    col1, col2 = st.columns(2)
    with col1:
        SETTINGS.SEARCH_TOP_N = st.number_input(
            "検索結果の表示数",
            min_value=1,
            max_value=50,
            value=SETTINGS.SEARCH_TOP_N
        )
        SETTINGS.USE_SIMILAR_TERMS = st.checkbox(
            "類似語を使用",
            value=SETTINGS.USE_SIMILAR_TERMS
        )
    with col2:
        SETTINGS.SEARCH_TEMPERATURE = st.slider(
            "類似語生成の温度",
            min_value=0.0,
            max_value=1.0,
            value=SETTINGS.SEARCH_TEMPERATURE,
            step=0.1
        )
    
    # AI設定
    st.subheader("AI設定")
    col1, col2 = st.columns(2)
    with col1:
        SETTINGS.AI_MODEL = st.selectbox(
            "AIモデル",
            options=["gpt-4", "gpt-3.5-turbo"],
            index=0 if SETTINGS.AI_MODEL == "gpt-4" else 1
        )
        SETTINGS.AI_TEMPERATURE = st.slider(
            "AI応答の温度",
            min_value=0.0,
            max_value=1.0,
            value=SETTINGS.AI_TEMPERATURE,
            step=0.1
        )
    with col2:
        SETTINGS.CACHE_TTL = st.number_input(
            "キャッシュの有効期限（秒）",
            min_value=0,
            max_value=86400,
            value=SETTINGS.CACHE_TTL
        )
    
    # 設定の保存
    if st.button("設定を保存"):
        # TODO: 設定の永続化
        st.success("設定を保存しました")

def show_features_overview():
    st.markdown("""
    <style>
        body, .reportview-container {
            background-color: #F6FAFE !important;
        }
        .feature-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 26px;
            margin-bottom: 2.3em;
        }
        @media (max-width: 800px) {
            .feature-grid { grid-template-columns: 1fr; }
        }
        .feature-card {
            background: #fff;
            border-radius: 15px;
            box-shadow: 0 4px 18px rgba(31,174,255,0.07);
            padding: 1.4em 1.3em 1.15em 1.3em;
            border-left: 6px solid #1FAEFF;
            display: flex;
            align-items: flex-start;
            gap: 1em;
            min-height: 115px;
            transition: box-shadow .15s;
        }
        .feature-card:hover {
            box-shadow: 0 8px 24px rgba(31,174,255,0.14);
        }
        .feature-icon {
            font-size: 2.25em;
            color: #1FAEFF;
            min-width: 2.1em;
            text-align: center;
            margin-top: 2px;
        }
        .feature-content {
            flex: 1;
        }
        .feature-title {
            font-size: 1.14em;
            font-weight: bold;
            color: #1e40af;
            margin-bottom: 4px;
        }
        .feature-description {
            font-size: 1.01em;
            color: #475569;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div>
      <h3 style="color:#1FAEFF; font-size:1.5em; margin-bottom:0.5em; margin-top:0;">📋 機能概要</h3>
      <div class="feature-grid">
        <div class="feature-card">
          <div class="feature-icon">📚</div>
          <div class="feature-content">
            <div class="feature-title">複数PDF分析</div>
            <div class="feature-description">複数のPDFを同時に分析し、横断的な質問や集計が可能です。</div>
          </div>
        </div>
        <div class="feature-card">
          <div class="feature-icon">🔍</div>
          <div class="feature-content">
            <div class="feature-title">セマンティック検索</div>
            <div class="feature-description">意味ベース・キーワードベース両方のPDF横断検索を実現します。</div>
          </div>
        </div>
        <div class="feature-card">
          <div class="feature-icon">💬</div>
          <div class="feature-content">
            <div class="feature-title">インテリジェント回答</div>
            <div class="feature-description">Snowflake Cortexで高精度な自然言語質問応答が可能。</div>
          </div>
        </div>
        <div class="feature-card">
          <div class="feature-icon">📝</div>
          <div class="feature-content">
            <div class="feature-title">要約機能</div>
            <div class="feature-description">文書全体やページ単位での自動要約が利用できます。</div>
          </div>
        </div>
        <div class="feature-card">
          <div class="feature-icon">📊</div>
          <div class="feature-content">
            <div class="feature-title">チャット履歴管理</div>
            <div class="feature-description">過去の会話履歴の保存・エクスポートが可能です。</div>
          </div>
        </div>
        <div class="feature-card">
          <div class="feature-icon">🎯</div>
          <div class="feature-content">
            <div class="feature-title">インタラクティブUI</div>
            <div class="feature-description">直感的で使いやすいPDF閲覧＆分析インターフェース。</div>
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # 始め方
    st.markdown("""
    <h3 style="color:#1FAEFF; margin-bottom:0.2em; margin-top:0.9em;">🚀 始め方</h3>
    <ol style="font-size:1.07em; color:#334155; margin-left:1.2em;">
      <li>左のサイドバーからPDFファイルをアップロード</li>
      <li>「統合検索」または「個別分析」モードを選択</li>
      <li>質問や要約を入力して分析スタート</li>
      <li>結果を確認し、必要に応じて追加分析や履歴管理</li>
    </ol>
    <div style="margin-top: 1.2em;">
      <a href="/機能仕様" target="_self"
        style="text-decoration:none; padding:0.5em 1em; background:#1FAEFF; color:white; border-radius:4px; font-size:1em;">
        📋 詳細な機能仕様を確認
      </a>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
