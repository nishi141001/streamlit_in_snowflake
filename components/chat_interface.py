"""
チャットインターフェースコンポーネント

Streamlitを使用したチャットUIの実装
"""

import streamlit as st
from typing import List, Dict, Optional
from datetime import datetime
import json
from services.chat_service import ChatService
from utils.export_utils import export_manager, render_export_ui


def init_chat_state():
    """
    チャットの状態を初期化
    """
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'chat_service' not in st.session_state:
        st.session_state.chat_service = ChatService()
    if 'feedback_history' not in st.session_state:
        st.session_state.feedback_history = {}


def display_chat_message(message: Dict, is_user: bool = False):
    """
    チャットメッセージを表示
    
    Parameters:
    -----------
    message : dict
        メッセージデータ
    is_user : bool, optional
        ユーザーメッセージかどうか
    """
    if is_user:
        with st.chat_message("user"):
            st.write(message['query'])
            st.caption(f"送信時刻: {datetime.fromisoformat(message.get('timestamp', datetime.now().isoformat())).strftime('%H:%M:%S')}")
    else:
        with st.chat_message("assistant"):
            # メッセージIDを生成（タイムスタンプベース）
            msg_id = message.get('timestamp', datetime.now().isoformat())
            
            # 応答の表示
            st.write(message['response'])
            
            # ソース情報の表示
            if message.get('sources'):
                with st.expander("📚 参照元", expanded=False):
                    for source in message['sources']:
                        source_type = source.get('type', 'text')
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            if source_type == 'text':
                                st.write(f"📄 ページ {source.get('page', '?')}")
                            elif source_type == 'table':
                                st.write(f"📊 テーブル（ページ {source.get('page', '?')}）")
                            elif source_type == 'figure':
                                st.write(f"🖼️ 図表 {source.get('figure_num', '?')}（ページ {source.get('page', '?')}）")
                        
                        with col2:
                            st.write(f"関連度: {source.get('score', 0):.2f}")
            
            # フィードバックボタン
            col1, col2, col3 = st.columns([1, 1, 3])
            with col1:
                if st.button("👍", key=f"like_{msg_id}"):
                    st.session_state.feedback_history[msg_id] = "like"
                    st.success("フィードバックありがとうございます！")
            with col2:
                if st.button("👎", key=f"dislike_{msg_id}"):
                    st.session_state.feedback_history[msg_id] = "dislike"
                    st.success("フィードバックありがとうございます！")
            
            # タイムスタンプ
            st.caption(f"応答時刻: {datetime.fromisoformat(message.get('timestamp', datetime.now().isoformat())).strftime('%H:%M:%S')}")


def render_chat_interface(pdf_contents: List[Dict]):
    """
    チャットインターフェースをレンダリング
    
    Parameters:
    -----------
    pdf_contents : list[dict]
        PDF内容の辞書リスト
    """
    init_chat_state()
    
    # チャットコンテナ
    chat_container = st.container()
    
    with chat_container:
        # チャット履歴の表示
        if not st.session_state.chat_history:
            st.info("👋 PDFについて質問してみましょう！")
        
        for message in st.session_state.chat_history:
            if message.get('query'):
                display_chat_message(message, is_user=True)
            if message.get('response'):
                display_chat_message(message)
    
    # チャット入力
    if query := st.chat_input("PDFについて質問してください", key="chat_input"):
        # ユーザーメッセージの表示
        user_message = {
            'query': query,
            'timestamp': datetime.now().isoformat()
        }
        display_chat_message(user_message, is_user=True)
        
        # 応答の生成
        try:
            with st.spinner("🤔 考え中..."):
                response = st.session_state.chat_service.chat(
                    query=query,
                    pdf_contents=pdf_contents,
                    history=st.session_state.chat_history
                )
                
                # 応答の表示
                display_chat_message(response)
                
                # 履歴に追加
                st.session_state.chat_history.append(response)
                
        except Exception as e:
            st.error(f"申し訳ありません。エラーが発生しました: {str(e)}")
            st.info("もう一度お試しください。")
    
    # サイドバーに会話管理オプションを表示
    with st.sidebar:
        st.subheader("💬 会話管理")
        
        # 会話の要約
        if st.button("📝 会話を要約", use_container_width=True):
            try:
                with st.spinner("要約を生成中..."):
                    summary = st.session_state.chat_service.summarize_chat(
                        st.session_state.chat_history
                    )
                    st.write("### 📋 会話の要約")
                    st.write(summary)
            except Exception as e:
                st.error("要約の生成中にエラーが発生しました。")
        
        # 会話のエクスポート
        if st.button("💾 会話をエクスポート", use_container_width=True):
            try:
                export_data = {
                    'timestamp': datetime.now().isoformat(),
                    'history': st.session_state.chat_history,
                    'feedback': st.session_state.feedback_history
                }
                st.download_button(
                    "📥 JSONとしてダウンロード",
                    data=json.dumps(export_data, ensure_ascii=False, indent=2),
                    file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
        )
            except Exception as e:
                st.error("エクスポート中にエラーが発生しました。")
        
        # 会話のクリア
        if st.button("🗑️ 会話をクリア", use_container_width=True):
            if st.session_state.chat_history:
        st.session_state.chat_history = []
                st.session_state.feedback_history = {}
                st.rerun()
            else:
                st.info("クリアする会話がありません。")
        
        # フィードバック統計
        if st.session_state.feedback_history:
            st.subheader("📊 フィードバック統計")
            likes = sum(1 for v in st.session_state.feedback_history.values() if v == "like")
            dislikes = sum(1 for v in st.session_state.feedback_history.values() if v == "dislike")
            st.write(f"👍 良い: {likes}")
            st.write(f"👎 改善が必要: {dislikes}")


def render_chat_export(chat_history: List[Dict]) -> None:
    """
    チャット履歴のエクスポートUIを表示
    
    Parameters:
    -----------
    chat_history : List[Dict]
        チャット履歴
    """
    if not chat_history:
        st.warning("エクスポートするチャット履歴がありません")
        return
    
    # チャット履歴のデータを準備
    chat_data = []
    for msg in chat_history:
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
        default_filename=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        metadata={
            'export_type': 'chat_history',
            'message_count': len(chat_data),
            'export_timestamp': datetime.now().isoformat()
        }
    )
