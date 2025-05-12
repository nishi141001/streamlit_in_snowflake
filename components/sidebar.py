"""
サイドバーコンポーネント

アプリケーションのサイドバーUI要素を管理
"""

import streamlit as st
from config import SETTINGS, MESSAGES
from utils.export_utils import export_manager, render_export_ui, render_export_history
from components.chat_interface import clear_chat_history
from typing import Dict, List, Optional
from datetime import datetime
import json


def render_sidebar():
    """
    サイドバーUIを描画
    
    Returns:
    --------
    list
        アップロードされたファイルのリスト
    """
    with st.sidebar:
        st.title("📂 設定 & 管理")
        
        # モード設定
        st.subheader("🔍 動作モード")
        enable_summary = st.checkbox(
            "要約モード",
            value=st.session_state.get("summary_mode", False),
            help="文書やページの自動要約機能を有効にします"
        )
        st.session_state.summary_mode = enable_summary
        
        # 詳細設定
        with st.expander("⚙️ 詳細設定", expanded=False):
            # 類似度閾値
            similarity = st.slider(
                "類似度閾値",
                min_value=0.0,
                max_value=1.0,
                value=SETTINGS["SIMILARITY_THRESHOLD"],
                step=0.05,
                help="検索結果の類似度閾値。高いほど関連性の高い結果のみ表示されます"
            )
            st.session_state.similarity_threshold = similarity
            
            # 最大チャンク数
            chunks = st.slider(
                "最大コンテキストチャンク数",
                min_value=1,
                max_value=10,
                value=SETTINGS["MAX_CHUNKS_FOR_QUERY"],
                step=1,
                help="質問応答時に使用するコンテキストチャンク数。多いほど情報量が増えますが、処理が遅くなります"
            )
            st.session_state.max_chunks = chunks
        
        # PDFファイルアップロード
        st.subheader("📄 PDFファイル")
        uploaded_files = st.file_uploader(
            "PDFファイルをアップロード",
            type="pdf",
            accept_multiple_files=True,
            help="複数のPDFファイルをアップロードできます"
        )
        
        # PDFファイル数表示
        if uploaded_files:
            st.success(f"{len(uploaded_files)}個のファイルがロードされました")
        
        # 履歴管理
        st.subheader("🕒 履歴管理")
        
        # 履歴クリア
        if st.button("履歴クリア", use_container_width=True):
            clear_chat_history()
        
        # エクスポート
        render_export_section()
        
        # アプリ情報
        st.markdown("---")
        st.markdown("### 📝 アプリ情報")
        st.markdown("""
        - Snowflake Cortexを利用したPDF分析アプリ
        - 意味検索とAI質問応答
        - 複数文書の横断分析
        """)
        
        # バージョン情報
        st.markdown("---")
        st.caption("Version 2.0.0")
    
    return uploaded_files


def render_export_section():
    """エクスポートセクションを表示"""
    st.subheader("エクスポート")
    
    # エクスポート形式の選択
    export_format = st.radio(
        "エクスポート形式",
        ['JSON', 'CSV', 'Markdown'],
        horizontal=True
    )
    
    # チャット履歴のエクスポート
    if st.button("チャット履歴をエクスポート"):
        if 'chat_history' in st.session_state and st.session_state.chat_history:
            # チャット履歴のデータを準備
            chat_data = []
            for msg in st.session_state.chat_history:
                chat_data.append({
                    'timestamp': msg.get('timestamp', ''),
                    'role': msg.get('role', ''),
                    'content': msg.get('content', ''),
                    'page': msg.get('page', ''),
                    'score': msg.get('score', ''),
                    'feedback': msg.get('feedback', '')
                })
            
            # エクスポートUIの表示
            render_export_ui(
                data=chat_data,
                title="チャット履歴のエクスポート",
                default_filename=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format.lower()}",
                metadata={
                    'export_type': 'chat_history',
                    'message_count': len(chat_data),
                    'export_timestamp': datetime.now().isoformat()
                }
            )
        else:
            st.warning("エクスポートするチャット履歴がありません")
    
    # エクスポート履歴の表示
    render_export_history()
