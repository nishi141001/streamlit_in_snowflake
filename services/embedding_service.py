import streamlit as st
from typing import List, Dict, Any, Optional, Union
import numpy as np
from datetime import datetime
import json
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import col, lit, array_construct
from snowflake.snowpark.types import VectorType, FloatType
from utils.vector_utils import calculate_similarity
from utils.cache_utils import SnowflakeCache
from config import SETTINGS

class EmbeddingService:
    def __init__(self, cache: Optional[SnowflakeCache] = None):
        """
        埋め込みサービスの初期化
        
        Args:
            cache: キャッシュインスタンス
        """
        self.session = get_active_session()
        self.cache = cache
        self.model_name = SETTINGS.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.vector_dim = SETTINGS.get("VECTOR_DIM", 384)
    
    def embed_text(self, text: str) -> Optional[List[float]]:
        """
        テキストをベクトルに変換
        
        Args:
            text: 変換するテキスト
        
        Returns:
            Optional[List[float]]: 埋め込みベクトル
        """
        try:
            # キャッシュキーの生成
            cache_key = f"embed_{hash(text)}"
            
            # キャッシュから結果を取得
            if self.cache:
                cached_vector = self.cache.get(cache_key)
                if cached_vector:
                    return cached_vector
            
            # 埋め込みの実行
            vector = self.session.sql(f"""
                SELECT VECTOR_EMBED('{self.model_name}', '{text}') as embedding
            """).collect()[0]["EMBEDDING"]
            
            # 結果をキャッシュに保存
            if self.cache:
                self.cache.set(cache_key, vector)
            
            return vector
        
        except Exception as e:
            st.error(f"テキストの埋め込み中にエラーが発生しました: {str(e)}")
            return None
    
    def embed_documents(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = 32
    ) -> List[Dict[str, Any]]:
        """
        複数のドキュメントをベクトル化
        
        Args:
            documents: ドキュメントのリスト
            batch_size: バッチ処理のサイズ
        
        Returns:
            List[Dict[str, Any]]: ベクトル化されたドキュメント
        """
        try:
            embedded_docs = []
            
            # バッチ処理
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                
                # バッチ内のテキストを結合
                texts = [doc.get("text", "") for doc in batch]
                text_batch = "|".join(texts)
                
                # バッチの埋め込み
                vectors = self.session.sql(f"""
                    SELECT VECTOR_EMBED('{self.model_name}', '{text_batch}') as embeddings
                """).collect()[0]["EMBEDDINGS"]
                
                # 結果の分割とドキュメントへの追加
                for doc, vector in zip(batch, vectors):
                    doc["embedding"] = vector
                    embedded_docs.append(doc)
            
            return embedded_docs
        
        except Exception as e:
            st.error(f"ドキュメントの埋め込み中にエラーが発生しました: {str(e)}")
            return []
    
    def embed_query(
        self,
        query: str,
        use_synonyms: bool = True
    ) -> Dict[str, Any]:
        """
        検索クエリをベクトル化
        
        Args:
            query: 検索クエリ
            use_synonyms: 類似語を使用するかどうか
        
        Returns:
            Dict[str, Any]: クエリベクトルと関連情報
        """
        try:
            # クエリのベクトル化
            query_vector = self.embed_text(query)
            if not query_vector:
                return {}
            
            result = {
                "query": query,
                "vector": query_vector,
                "timestamp": datetime.now().isoformat()
            }
            
            # 類似語の処理
            if use_synonyms:
                synonyms = self._get_synonyms(query)
                if synonyms:
                    synonym_vectors = [self.embed_text(syn) for syn in synonyms]
                    result["synonyms"] = list(zip(synonyms, synonym_vectors))
            
            return result
        
        except Exception as e:
            st.error(f"クエリの埋め込み中にエラーが発生しました: {str(e)}")
            return {}
    
    def _get_synonyms(self, text: str) -> List[str]:
        """
        テキストの類似語を取得
        
        Args:
            text: 入力テキスト
        
        Returns:
            List[str]: 類似語のリスト
        """
        try:
            # Snowflakeの類似語検索機能を使用
            synonyms = self.session.sql(f"""
                SELECT ARRAY_AGG(synonym) as synonyms
                FROM TABLE(SYNONYM_LOOKUP('{text}'))
                LIMIT 5
            """).collect()[0]["SYNONYMS"]
            
            return synonyms if synonyms else []
        
        except Exception as e:
            st.warning(f"類似語の取得中にエラーが発生しました: {str(e)}")
            return []
    
    def calculate_similarities(
        self,
        query_vector: List[float],
        document_vectors: List[List[float]]
    ) -> List[float]:
        """
        クエリベクトルとドキュメントベクトル間の類似度を計算
        
        Args:
            query_vector: クエリのベクトル
            document_vectors: ドキュメントのベクトルリスト
        
        Returns:
            List[float]: 類似度スコアのリスト
        """
        try:
            # 類似度の計算
            similarities = []
            for doc_vector in document_vectors:
                similarity = calculate_similarity(query_vector, doc_vector)
                similarities.append(similarity)
            
            return similarities
        
        except Exception as e:
            st.error(f"類似度の計算中にエラーが発生しました: {str(e)}")
            return []
    
    def batch_embed_and_store(
        self,
        documents: List[Dict[str, Any]],
        table_name: str,
        batch_size: int = 32
    ) -> bool:
        """
        ドキュメントをベクトル化してSnowflakeテーブルに保存
        
        Args:
            documents: ドキュメントのリスト
            table_name: 保存先テーブル名
            batch_size: バッチ処理のサイズ
        
        Returns:
            bool: 処理の成功/失敗
        """
        try:
            # ドキュメントのベクトル化
            embedded_docs = self.embed_documents(documents, batch_size)
            if not embedded_docs:
                return False
            
            # テーブルへの保存
            for i in range(0, len(embedded_docs), batch_size):
                batch = embedded_docs[i:i + batch_size]
                
                # バッチデータの準備
                rows = []
                for doc in batch:
                    row = {
                        "id": doc.get("id"),
                        "content": doc.get("text", ""),
                        "metadata": json.dumps(doc.get("metadata", {})),
                        "embedding": doc.get("embedding", []),
                        "created_at": datetime.now().isoformat()
                    }
                    rows.append(row)
                
                # テーブルへの挿入
                self.session.write_pandas(
                    pd.DataFrame(rows),
                    table_name,
                    auto_create_table=True,
                    table_type="transient"
                )
            
            return True
        
        except Exception as e:
            st.error(f"ドキュメントの保存中にエラーが発生しました: {str(e)}")
            return False 