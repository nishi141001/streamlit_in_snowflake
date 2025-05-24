"""
AIサービス

機能
- ドキュメント要約生成
- 質問応答
- 多言語翻訳
- カスタムプロンプト管理
- 回答履歴管理
"""

import streamlit as st
from typing import List, Dict, Optional, Union, Any
from datetime import datetime
import json
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import col, lit, array_construct
from utils.vector_utils import hybrid_search
from utils.cache_utils import SnowflakeCache
from config import SETTINGS

class AIService:
    def __init__(self):
        """初期化"""
        self.session = get_active_session()
        self.cache = SnowflakeCache()
        self._init_tables()
    
    def _init_tables(self):
        """必要なテーブルの初期化"""
        # 既存のテーブルを個別に削除
        self.session.sql("DROP TABLE IF EXISTS custom_prompts").collect()
        self.session.sql("DROP TABLE IF EXISTS answer_history").collect()

        # カスタムプロンプトテーブル
        self.session.sql("""
        CREATE TABLE IF NOT EXISTS custom_prompts (
            prompt_id STRING,
            user_id STRING,
            name STRING,
            description STRING,
            prompt_template STRING,
            parameters VARIANT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            is_active BOOLEAN,
            PRIMARY KEY (prompt_id)
        )
        """).collect()
        
        # 回答履歴テーブル
        self.session.sql("""
        CREATE TABLE IF NOT EXISTS answer_history (
            answer_id STRING,
            user_id STRING,
            query STRING,
            context VARIANT,
            answer STRING,
            explanation STRING,
            metadata VARIANT,
            created_at TIMESTAMP,
            PRIMARY KEY (answer_id)
        )
        """).collect()
    
    def generate_summary(
        self,
        document_text: str,
        max_length: int = 200,
        language: str = "ja",
        style: str = "formal"
    ) -> Dict:
        """
        ドキュメントの要約を生成
        
        Parameters:
        -----------
        document_text : str
            要約対象のテキスト
        max_length : int
            要約の最大長
        language : str
            出力言語
        style : str
            要約のスタイル（formal/casual/technical）
            
        Returns:
        --------
        Dict
            要約結果
        """
        # プロンプトの構築
        prompt = f"""
        以下のテキストを{max_length}文字以内で要約してください。
        言語: {language}
        スタイル: {style}
        
        テキスト:
        {document_text}
        
        要約は以下の形式で出力してください:
        {{
            "summary": "要約テキスト",
            "key_points": ["重要なポイント1", "重要なポイント2", ...],
            "metadata": {{
                "original_length": 元のテキストの長さ,
                "summary_length": 要約の長さ,
                "language": 出力言語,
                "style": スタイル
            }}
        }}
        """
        
        # Cortex LLMの呼び出し
        try:
            response = self.session.sql(f"""
            SELECT CORTEX_LLM_COMPLETE(
                '{prompt}',
                {{
                    'temperature': {SETTINGS.AI_TEMPERATURE},
                    'max_tokens': {max_length * 2},
                    'model': '{SETTINGS.AI_MODEL}'
                }}
            ) as response
            """).collect()[0]["RESPONSE"]
            
            # レスポンスの解析
            result = json.loads(response)
            
            # キャッシュの更新
            cache_key = f"summary_{hash(document_text)}_{max_length}_{language}_{style}"
            self.cache.set(cache_key, result, ttl=3600)  # 1時間キャッシュ
            
            return result
            
        except Exception as e:
            st.error(f"要約生成中にエラーが発生しました: {str(e)}")
            return {
                "summary": "要約の生成に失敗しました。",
                "key_points": [],
                "metadata": {
                    "error": str(e)
                }
            }
    
    def answer_question(
        self,
        question: str,
        context: List[Dict],
        custom_prompt_id: Optional[str] = None,
        include_explanation: bool = True,
        language: str = "ja"
    ) -> Dict:
        """
        質問に回答
        
        Parameters:
        -----------
        question : str
            質問文
        context : List[Dict]
            回答のためのコンテキスト
        custom_prompt_id : Optional[str]
            使用するカスタムプロンプトのID
        include_explanation : bool
            説明を含めるかどうか
        language : str
            出力言語
            
        Returns:
        --------
        Dict
            回答結果
        """
        # カスタムプロンプトの取得
        prompt_template = self._get_prompt_template(custom_prompt_id) if custom_prompt_id else None
        
        # コンテキストの準備
        context_text = "\n\n".join([
            f"ドキュメント: {c.get('file_name', 'Unknown')}\n"
            f"ページ: {c.get('page', 'Unknown')}\n"
            f"テキスト: {c.get('text', '')}"
            for c in context
        ])
        
        # プロンプトの構築
        if prompt_template:
            prompt = prompt_template.format(
                question=question,
                context=context_text,
                language=language,
                include_explanation=include_explanation
            )
        else:
            prompt = f"""
            以下のコンテキストに基づいて質問に回答してください。
            
            質問: {question}
            言語: {language}
            説明を含める: {include_explanation}
            
            コンテキスト:
            {context_text}
            
            回答は以下の形式で出力してください:
            {{
                "answer": "回答テキスト",
                "explanation": "説明テキスト" if {include_explanation} else null,
                "confidence": 0.0-1.0の信頼度,
                "sources": [
                    {{
                        "file_name": "ソースファイル名",
                        "page": ページ番号,
                        "relevance": 関連度
                    }}
                ]
            }}
            """
        
        # Cortex LLMの呼び出し
        try:
            response = self.session.sql(f"""
            SELECT CORTEX_LLM_COMPLETE(
                '{prompt}',
                {{
                    'temperature': {SETTINGS.AI_TEMPERATURE},
                    'max_tokens': 1000,
                    'model': '{SETTINGS.AI_MODEL}'
                }}
            ) as response
            """).collect()[0]["RESPONSE"]
            
            # レスポンスの解析
            result = json.loads(response)
            
            # 回答履歴の保存
            self._save_answer_history(
                question=question,
                context=context,
                answer=result["answer"],
                explanation=result.get("explanation"),
                metadata={
                    "custom_prompt_id": custom_prompt_id,
                    "language": language,
                    "confidence": result.get("confidence", 0.0),
                    "sources": result.get("sources", [])
                }
            )
            
            return result
            
        except Exception as e:
            st.error(f"質問応答中にエラーが発生しました: {str(e)}")
            return {
                "answer": "回答の生成に失敗しました。",
                "explanation": str(e) if include_explanation else None,
                "confidence": 0.0,
                "sources": []
            }
    
    def translate_text(
        self,
        text: str,
        source_language: str = "ja",
        target_language: str = "en",
        style: str = "formal"
    ) -> Dict:
        """
        テキストの翻訳
        
        Parameters:
        -----------
        text : str
            翻訳対象のテキスト
        source_language : str
            元の言語
        target_language : str
            翻訳先の言語
        style : str
            翻訳のスタイル（formal/casual/technical）
            
        Returns:
        --------
        Dict
            翻訳結果
        """
        # プロンプトの構築
        prompt = f"""
        以下のテキストを{target_language}に翻訳してください。
        元の言語: {source_language}
        スタイル: {style}
        
        テキスト:
        {text}
        
        翻訳は以下の形式で出力してください:
        {{
            "translated_text": "翻訳テキスト",
            "metadata": {{
                "source_language": 元の言語,
                "target_language": 翻訳先の言語,
                "style": スタイル,
                "original_length": 元のテキストの長さ,
                "translated_length": 翻訳の長さ
            }}
        }}
        """
        
        # Cortex LLMの呼び出し
        try:
            response = self.session.sql(f"""
            SELECT CORTEX_LLM_COMPLETE(
                '{prompt}',
                {{
                    'temperature': {SETTINGS.AI_TEMPERATURE},
                    'max_tokens': len('{text}') * 2,
                    'model': '{SETTINGS.AI_MODEL}'
                }}
            ) as response
            """).collect()[0]["RESPONSE"]
            
            # レスポンスの解析
            result = json.loads(response)
            
            # キャッシュの更新
            cache_key = f"translation_{hash(text)}_{source_language}_{target_language}_{style}"
            self.cache.set(cache_key, result, ttl=3600)  # 1時間キャッシュ
            
            return result
            
        except Exception as e:
            st.error(f"翻訳中にエラーが発生しました: {str(e)}")
            return {
                "translated_text": "翻訳に失敗しました。",
                "metadata": {
                    "error": str(e)
                }
            }
    
    def save_custom_prompt(
        self,
        name: str,
        description: str,
        prompt_template: str,
        parameters: Optional[Dict] = None
    ) -> Dict:
        """
        カスタムプロンプトの保存
        
        Parameters:
        -----------
        name : str
            プロンプト名
        description : str
            説明
        prompt_template : str
            プロンプトテンプレート
        parameters : Optional[Dict]
            パラメータ定義
            
        Returns:
        --------
        Dict
            保存結果
        """
        prompt_id = f"prompt_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        user_id = st.session_state.get("user_id", "anonymous")
        
        try:
            self.session.sql("""
            INSERT INTO custom_prompts (
                prompt_id, user_id, name, description,
                prompt_template, parameters, created_at,
                updated_at, is_active
            ) VALUES (
                :prompt_id, :user_id, :name, :description,
                :prompt_template, :parameters, :created_at,
                :updated_at, :is_active
            )
            """, {
                "prompt_id": prompt_id,
                "user_id": user_id,
                "name": name,
                "description": description,
                "prompt_template": prompt_template,
                "parameters": json.dumps(parameters) if parameters else None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "is_active": True
            }).collect()
            
            return {
                "prompt_id": prompt_id,
                "status": "success"
            }
            
        except Exception as e:
            st.error(f"プロンプトの保存中にエラーが発生しました: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def get_custom_prompts(
        self,
        user_id: Optional[str] = None,
        include_inactive: bool = False
    ) -> List[Dict]:
        """
        カスタムプロンプトの取得
        
        Parameters:
        -----------
        user_id : Optional[str]
            ユーザーID（指定がない場合は現在のユーザー）
        include_inactive : bool
            非アクティブなプロンプトを含めるかどうか
            
        Returns:
        --------
        List[Dict]
            プロンプトのリスト
        """
        if user_id is None:
            user_id = st.session_state.get("user_id", "anonymous")
        
        query = "SELECT * FROM custom_prompts WHERE user_id = :user_id"
        params = {"user_id": user_id}
        
        if not include_inactive:
            query += " AND is_active = TRUE"
        
        query += " ORDER BY created_at DESC"
        
        results = self.session.sql(query, params).collect()
        
        return [
            {
                "prompt_id": row["PROMPT_ID"],
                "name": row["NAME"],
                "description": row["DESCRIPTION"],
                "prompt_template": row["PROMPT_TEMPLATE"],
                "parameters": json.loads(row["PARAMETERS"]) if row["PARAMETERS"] else None,
                "created_at": row["CREATED_AT"],
                "updated_at": row["UPDATED_AT"],
                "is_active": row["IS_ACTIVE"]
            }
            for row in results
        ]
    
    def get_answer_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        回答履歴の取得
        
        Parameters:
        -----------
        user_id : Optional[str]
            ユーザーID（指定がない場合は現在のユーザー）
        limit : int
            取得する履歴の数
            
        Returns:
        --------
        List[Dict]
            回答履歴のリスト
        """
        if user_id is None:
            user_id = st.session_state.get("user_id", "anonymous")
        
        results = self.session.sql("""
        SELECT * FROM answer_history
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        LIMIT :limit
        """, {
            "user_id": user_id,
            "limit": limit
        }).collect()
        
        return [
            {
                "answer_id": row["ANSWER_ID"],
                "query": row["QUERY"],
                "context": json.loads(row["CONTEXT"]),
                "answer": row["ANSWER"],
                "explanation": row["EXPLANATION"],
                "metadata": json.loads(row["METADATA"]),
                "created_at": row["CREATED_AT"]
            }
            for row in results
        ]
    
    def _get_prompt_template(self, prompt_id: str) -> Optional[str]:
        """カスタムプロンプトテンプレートの取得"""
        result = self.session.sql("""
        SELECT prompt_template
        FROM custom_prompts
        WHERE prompt_id = :prompt_id
        AND is_active = TRUE
        """, {"prompt_id": prompt_id}).collect()
        
        return result[0]["PROMPT_TEMPLATE"] if result else None
    
    def _save_answer_history(
        self,
        question: str,
        context: List[Dict],
        answer: str,
        explanation: Optional[str],
        metadata: Dict
    ) -> None:
        """回答履歴の保存"""
        answer_id = f"answer_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        user_id = st.session_state.get("user_id", "anonymous")
        
        self.session.sql("""
        INSERT INTO answer_history (
            answer_id, user_id, query, context,
            answer, explanation, metadata, created_at
        ) VALUES (
            :answer_id, :user_id, :query, :context,
            :answer, :explanation, :metadata, :created_at
        )
        """, {
            "answer_id": answer_id,
            "user_id": user_id,
            "query": question,
            "context": json.dumps(context),
            "answer": answer,
            "explanation": explanation,
            "metadata": json.dumps(metadata),
            "created_at": datetime.now()
        }).collect() 