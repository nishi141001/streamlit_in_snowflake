"""
チャットサービス

Snowflake Cortexを使用したチャット機能と会話管理
"""

import streamlit as st
from typing import List, Dict, Optional
from datetime import datetime
from snowflake.snowpark.context import get_active_session
from config import SETTINGS
from utils.vector_utils import hybrid_search, search_in_tables_and_figures
from utils.cache_utils import cache_search_results, get_cached_data


class ChatService:
    def __init__(self):
        self.session = get_active_session()
        self.model = SETTINGS["MODEL_CHAT"]
        self.max_history = SETTINGS.get("MAX_CHAT_HISTORY", 10)
        self.context_window = SETTINGS.get("CONTEXT_WINDOW", 5)
    
    def _format_context(self, search_results: List[Dict]) -> str:
        """
        検索結果をコンテキストとして整形
        
        Parameters:
        -----------
        search_results : list[dict]
            検索結果のリスト
            
        Returns:
        --------
        str
            整形されたコンテキスト
        """
        context_parts = []
        
        for result in search_results:
            # テキストコンテキスト
            if 'text' in result:
                context_parts.append(f"ページ {result.get('page', '?')}:\n{result['text']}")
            
            # テーブルコンテキスト
            if result.get('type') == 'table':
                table_data = result.get('data', [])
                if table_data:
                    table_text = "テーブル:\n" + "\n".join(
                        " | ".join(str(cell) for cell in row)
                        for row in table_data
                    )
                    context_parts.append(table_text)
            
            # 図表コンテキスト
            if result.get('type') == 'figure':
                context_parts.append(
                    f"図表 {result.get('figure_num', '?')}:\n"
                    f"{result.get('context', '')}"
                )
        
        return "\n\n".join(context_parts)
    
    def _get_relevant_history(self, history: List[Dict], current_query: str) -> List[Dict]:
        """
        現在のクエリに関連する会話履歴を取得
        
        Parameters:
        -----------
        history : list[dict]
            会話履歴
        current_query : str
            現在のクエリ
            
        Returns:
        --------
        list[dict]
            関連する会話履歴
        """
        if not history:
            return []
        
        # 最新の会話を優先
        recent_history = history[-self.context_window:]
        
        # クエリに関連する履歴を抽出
        relevant_history = []
        for entry in recent_history:
            if any(word in entry['query'].lower() for word in current_query.lower().split()):
                relevant_history.append(entry)
        
        return relevant_history or recent_history
    
    def _build_prompt(self, query: str, context: str, history: List[Dict]) -> str:
        """
        プロンプトを構築
        
        Parameters:
        -----------
        query : str
            ユーザークエリ
        context : str
            関連コンテキスト
        history : list[dict]
            関連する会話履歴
            
        Returns:
        --------
        str
            構築されたプロンプト
        """
        prompt_parts = [
            "あなたはPDF文書の内容について質問に答えるアシスタントです。",
            "以下のコンテキストと会話履歴を参考に、質問に答えてください。",
            "回答は簡潔かつ正確に行い、必要に応じてコンテキストから引用してください。",
            "\nコンテキスト:",
            context,
        ]
        
        if history:
            prompt_parts.extend([
                "\n関連する会話履歴:",
                *[f"Q: {h['query']}\nA: {h['response']}" for h in history]
            ])
        
        prompt_parts.extend([
            "\n現在の質問:",
            query,
            "\n回答:"
        ])
        
        return "\n".join(prompt_parts)
    
    def chat(self, query: str, pdf_contents: List[Dict], history: List[Dict]) -> Dict:
        """
        チャット応答を生成
        
        Parameters:
        -----------
        query : str
            ユーザークエリ
        pdf_contents : list[dict]
            PDF内容の辞書リスト
        history : list[dict]
            会話履歴
            
        Returns:
        --------
        dict
            チャット応答（クエリ、応答、コンテキスト、タイムスタンプを含む）
        """
        # キャッシュされた結果を確認
        cached_result = get_cached_data(query, 'chat')
        if cached_result:
            return cached_result
        
        try:
            # 関連コンテキストの検索
            search_results = hybrid_search(query, pdf_contents)
            table_figure_results = search_in_tables_and_figures(query, pdf_contents)
            
            # コンテキストの構築
            context = self._format_context(search_results + table_figure_results)
            
            # 関連する会話履歴の取得
            relevant_history = self._get_relevant_history(history, query)
            
            # プロンプトの構築
            prompt = self._build_prompt(query, context, relevant_history)
            
            # Snowflake Cortexで応答を生成
            response = self.session.cortex.complete(
                model=self.model,
                prompt=prompt,
                temperature=0.7,
                max_tokens=1000
            )
            
            # 結果の整形
            result = {
                'query': query,
                'response': response,
                'context': context,
                'timestamp': datetime.now().isoformat(),
                'sources': [
                    {
                        'page': r.get('page'),
                        'type': r.get('type', 'text'),
                        'score': r.get('score', r.get('final_score', 0))
                    }
                    for r in search_results + table_figure_results
                ]
            }
            
            # 結果をキャッシュ
            cache_search_results(query, result)
            
            return result
            
        except Exception as e:
            print(f"チャット応答生成中にエラー: {str(e)}")
            return {
                'query': query,
                'response': "申し訳ありません。応答の生成中にエラーが発生しました。",
                'context': "",
                'timestamp': datetime.now().isoformat(),
                'sources': []
            }
    
    def summarize_chat(self, history: List[Dict]) -> str:
        """
        会話履歴の要約を生成
        
        Parameters:
        -----------
        history : list[dict]
            会話履歴
            
        Returns:
        --------
        str
            会話の要約
        """
        if not history:
            return "会話履歴がありません。"
        
        try:
            # 要約用のプロンプトを構築
            prompt = (
                "以下の会話履歴を要約してください。"
                "重要なポイントと結論を簡潔にまとめてください。\n\n"
                "会話履歴:\n" +
                "\n".join(
                    f"Q: {h['query']}\nA: {h['response']}"
                    for h in history[-self.max_history:]
                )
            )
            
            # 要約を生成
            summary = self.session.cortex.complete(
                model=self.model,
                prompt=prompt,
                temperature=0.3,
                max_tokens=500
            )
            
            return summary
            
        except Exception as e:
            print(f"会話要約生成中にエラー: {str(e)}")
            return "会話の要約生成中にエラーが発生しました。"


@st.cache_data(ttl=SETTINGS["CACHE_EXPIRE"])
def generate_answer(session, question, context, system_prompt=None):
    """
    質問に対する回答を生成
    
    Parameters:
    -----------
    session : snowflake.snowpark.Session
        Snowflakeセッション
    text : str
        要約するテキスト
    max_length : int, optional
        要約の最大長
    system_prompt : str, optional
        システムプロンプト（指示）
        
    Returns:
    --------
    str
        生成された要約
    """
    if system_prompt is None:
        system_prompt = MESSAGES["SUMMARY_PROMPT"]
    
    if max_length is None:
        max_length = SETTINGS["SUMMARY_MAX_LENGTH"]
    
    try:
        # テキストが長すぎる場合は分割して要約
        if len(text) > 32000:  # モデルの最大コンテキスト長を考慮
            chunks = split_text(text, chunk_size=30000)
            chunk_summaries = []
            
            for chunk in chunks:
                response = session.cortex.complete(
                    model=SETTINGS["MODEL_CHAT"],
                    messages=[
                        {"role": "system", "content": system_prompt + f"\n\n結果は{max_length//len(chunks)}文字以内にまとめてください。"},
                        {"role": "user", "content": chunk}
                    ],
                    temperature=0.1,
                    max_tokens=max_length // len(chunks)
                )
                chunk_summaries.append(response['message']['content'])
            
            # 個別要約をまとめて最終要約を生成
            combined_summary = "\n\n".join(chunk_summaries)
            response = session.cortex.complete(
                model=SETTINGS["MODEL_CHAT"],
                messages=[
                    {"role": "system", "content": "以下の要約をさらに簡潔にまとめてください。"},
                    {"role": "user", "content": combined_summary}
                ],
                temperature=0.1,
                max_tokens=max_length
            )
            return response['message']['content']
        else:
            # 直接要約
            response = session.cortex.complete(
                model=SETTINGS["MODEL_CHAT"],
                messages=[
                    {"role": "system", "content": system_prompt + f"\n\n結果は{max_length}文字以内にまとめてください。"},
                    {"role": "user", "content": text}
                ],
                temperature=0.1,
                max_tokens=max_length
            )
            return response['message']['content']
    except Exception as e:
        error_msg = f"要約生成中にエラーが発生しました: {str(e)}"
        print(error_msg)
        return f"申し訳ありません。要約の生成中に問題が発生しました。"


def split_text(text, chunk_size=30000, overlap=1000):
    """
    長いテキストを重複あり部分文字列に分割
    
    Parameters:
    -----------
    text : str
        分割するテキスト
    chunk_size : int, optional
        各チャンクの最大サイズ
    overlap : int, optional
        重複文字数
        
    Returns:
    --------
    list[str]
        分割されたテキストチャンクのリスト
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        
        # 文の途中で切らないように調整
        if end < len(text):
            # ピリオド、改行、句読点などで区切る
            for delimiter in ["\n\n", "\n", "。", ".", "！", "!", "？", "?"]:
                pos = text.rfind(delimiter, start, end)
                if pos > start + chunk_size // 2:  # チャンクの半分以上あれば区切る
                    end = pos + 1
                    break
        
        chunks.append(text[start:end])
        start = end - overlap  # 重複を考慮して次の開始位置を設定
    
    return chunks


@st.cache_data(ttl=SETTINGS["CACHE_EXPIRE"])
def generate_summary(session, text, max_length=None, system_prompt=None):
    """
    テキストの要約を生成
    
    Parameters:
    -----------
    session : snowflake.snowpark.Session
        Snowflakeセッション
    text : str
        要約するテキスト
    max_length : int, optional
        要約の最大長
    system_prompt : str, optional
        システムプロンプト（指示）
        
    Returns:
    --------
    str
        生成された要約
    """
    if system_prompt is None:
        system_prompt = MESSAGES["SUMMARY_PROMPT"]
    
    if max_length is None:
        max_length = SETTINGS["SUMMARY_MAX_LENGTH"]
    
    try:
        # テキストが長すぎる場合は分割して要約
        if len(text) > 32000:  # モデルの最大コンテキスト長を考慮
            chunks = split_text(text, chunk_size=30000)
            chunk_summaries = []
            
            for chunk in chunks:
                response = session.cortex.complete(
                    model=SETTINGS["MODEL_CHAT"],
                    messages=[
                        {"role": "system", "content": system_prompt + f"\n\n結果は{max_length//len(chunks)}文字以内にまとめてください。"},
                        {"role": "user", "content": chunk}
                    ],
                    temperature=0.1,
                    max_tokens=max_length // len(chunks)
                )
                chunk_summaries.append(response['message']['content'])
            
            # 個別要約をまとめて最終要約を生成
            combined_summary = "\n\n".join(chunk_summaries)
            response = session.cortex.complete(
                model=SETTINGS["MODEL_CHAT"],
                messages=[
                    {"role": "system", "content": "以下の要約をさらに簡潔にまとめてください。"},
                    {"role": "user", "content": combined_summary}
                ],
                temperature=0.1,
                max_tokens=max_length
            )
            return response['message']['content']
        else:
            # 直接要約
            response = session.cortex.complete(
                model=SETTINGS["MODEL_CHAT"],
                messages=[
                    {"role": "system", "content": system_prompt + f"\n\n結果は{max_length}文字以内にまとめてください。"},
                    {"role": "user", "content": text}
                ],
                temperature=0.1,
                max_tokens=max_length
            )
            return response['message']['content']
    except Exception as e:
        error_msg = f"要約生成中にエラーが発生しました: {str(e)}"
        print(error_msg)
        return f"申し訳ありません。要約の生成中に問題が発生しました。"