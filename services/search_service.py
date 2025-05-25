"""
検索サービス

拡張検索機能
- 複数PDF検索モードと個別PDF検索モード
- フィルタリング
- 高度な検索オプション
- 検索履歴管理
- エクスポート機能
"""

import streamlit as st
from typing import List, Dict, Optional, Union, Any
from datetime import datetime, timedelta
import pandas as pd
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import col, lit, array_construct
import json
from utils.vector_utils import hybrid_search, search_in_tables_and_figures
from utils.cache_utils import SnowflakeCache

class SearchService:
    def __init__(self):
        self.session = get_active_session()
        self.cache = SnowflakeCache()
        self._init_tables()
    
    def _init_tables(self):
        """必要なテーブルの初期化"""
        try:
            # 既存のテーブルを個別に削除（外部キー制約を考慮して逆順に削除）
            self.session.sql("DROP TABLE IF EXISTS search_history").collect()
            self.session.sql("DROP TABLE IF EXISTS document_metadata").collect()

            # 検索履歴テーブルを個別に作成
            create_search_history = """
            CREATE TABLE IF NOT EXISTS search_history (
                id STRING,
                user_id STRING,
                query STRING,
                mode STRING,
                target_document STRING,
                filters VARIANT,
                timestamp TIMESTAMP,
                results_count INTEGER,
                PRIMARY KEY (id)
            )
            """
            self.session.sql(create_search_history).collect()
            
            # ドキュメントメタデータテーブルを個別に作成
            create_document_metadata = """
            CREATE TABLE IF NOT EXISTS document_metadata (
                file_name STRING,
                upload_date TIMESTAMP,
                file_type STRING,
                page_count INTEGER,
                tags ARRAY,
                folder_path STRING,
                version INTEGER,
                access_control VARIANT,
                PRIMARY KEY (file_name)
            )
            """
            self.session.sql(create_document_metadata).collect()

        except Exception as e:
            print(f"テーブル初期化中にエラー: {str(e)}")
            raise
    
    def search(
        self,
        query: str,
        mode: str = "all",  # "all" or "single"
        target_document: Optional[str] = None,
        filters: Optional[Dict] = None,
        search_options: Optional[Dict] = None,
        top_n: int = 5,
        save_history: bool = True
    ) -> Dict:
        """
        拡張検索機能
        
        Parameters:
        -----------
        query : str
            検索クエリ
        mode : str
            検索モード ("all": 複数PDF検索, "single": 個別PDF検索)
        target_document : Optional[str]
            個別PDF検索時の対象ファイル名
        filters : Optional[Dict]
            フィルター条件
            - date_range: (start_date, end_date)
            - file_types: List[str]
            - page_range: (start_page, end_page)
            - tags: List[str]
            - folders: List[str]
        search_options : Optional[Dict]
            検索オプション
            - use_operators: bool (AND/OR/NOT)
            - use_similar_terms: bool
            - search_type: str (hybrid/vector/keyword)
        top_n : int
            取得する結果数
        save_history : bool
            検索履歴を保存するかどうか
            
        Returns:
        --------
        Dict
            検索結果とメタデータ
        """
        # 検索モードに応じたフィルターの設定
        if mode == "single" and target_document:
            if filters is None:
                filters = {}
            filters["file_names"] = [target_document]
        
        # フィルターの適用
        filtered_contents = self._apply_filters(filters) if filters else None
        
        # 検索オプションの設定
        search_type = search_options.get("search_type", "hybrid") if search_options else "hybrid"
        use_similar_terms = search_options.get("use_similar_terms", True) if search_options else True
        
        # 検索の実行
        if search_type == "hybrid":
            results = hybrid_search(
                query=query,
                pdf_contents=filtered_contents,
                top_n=top_n,
                use_similar_terms=use_similar_terms,
                mode=mode  # 検索モードを渡す
            )
        elif search_type == "vector":
            results = self._vector_search(query, filtered_contents, top_n, mode)
        else:  # keyword
            results = self._keyword_search(query, filtered_contents, top_n, mode)
        
        # 検索履歴の保存
        if save_history:
            self._save_search_history(
                query=query,
                mode=mode,
                target_document=target_document,
                filters=filters,
                results_count=len(results)
            )
        
        return {
            "results": results,
            "metadata": {
                "query": query,
                "mode": mode,
                "target_document": target_document,
                "filters": filters,
                "search_options": search_options,
                "total_results": len(results),
                "timestamp": datetime.now().isoformat()
            }
        }
    
    def _apply_filters(self, filters: Dict) -> List[Dict]:
        """フィルターの適用"""
        session = get_active_session()
        
        # メタデータテーブルからフィルター条件に合致するファイルを取得
        where_clauses = []
        params = {}
        
        if "date_range" in filters:
            start_date, end_date = filters["date_range"]
            where_clauses.append("upload_date BETWEEN :start_date AND :end_date")
            params["start_date"] = start_date
            params["end_date"] = end_date
        
        if "file_types" in filters:
            where_clauses.append("file_type IN (:file_types)")
            params["file_types"] = filters["file_types"]
        
        if "tags" in filters:
            where_clauses.append("ARRAY_INTERSECTION(tags, :tags) IS NOT NULL")
            params["tags"] = filters["tags"]
        
        if "folders" in filters:
            where_clauses.append("folder_path IN (:folders)")
            params["folders"] = filters["folders"]
        
        # クエリの構築
        query = "SELECT file_name FROM document_metadata"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        # フィルター条件に合致するファイルの取得
        filtered_files = session.sql(query, params).collect()
        filtered_file_names = [row["FILE_NAME"] for row in filtered_files]
        
        # ページ範囲フィルターの適用
        if "page_range" in filters:
            start_page, end_page = filters["page_range"]
            return [
                content for content in self._get_document_contents()
                if content["file_name"] in filtered_file_names
                and start_page <= content["page"] <= end_page
            ]
        
        return [
            content for content in self._get_document_contents()
            if content["file_name"] in filtered_file_names
        ]
    
    def _get_document_contents(self) -> List[Dict]:
        """ドキュメント内容の取得（キャッシュ対応）"""
        cache_key = "document_contents"
        cached_contents = self.cache.get(cache_key)
        
        if cached_contents is None:
            # キャッシュがない場合はデータベースから取得
            contents = self._load_document_contents()
            self.cache.set(cache_key, contents, ttl=3600)  # 1時間キャッシュ
            return contents
        
        return cached_contents
    
    def _load_document_contents(self) -> List[Dict]:
        """データベースからドキュメント内容を取得"""
        # 実装は既存のコードに依存
        pass
    
    def _save_search_history(
        self,
        query: str,
        mode: str,
        target_document: Optional[str],
        filters: Optional[Dict],
        results_count: int
    ) -> None:
        """検索履歴の保存（検索モード情報を追加）"""
        history_id = f"search_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        user_id = st.session_state.get("user_id", "anonymous")
        timestamp = datetime.now()
        
        # filtersをJSON文字列に変換
        filters_json = json.dumps(filters) if filters else "{}"
        
        # SQLクエリを修正：INSERT ... SELECT形式を使用
        self.session.sql("""
        INSERT INTO search_history (
            id, user_id, query, mode, target_document,
            filters, timestamp, results_count
        )
        SELECT
            ?, ?, ?, ?, ?,
            PARSE_JSON(?),  -- SELECT句ではPARSE_JSON関数が使用可能
            ?, ?
        """, [
            history_id,
            user_id,
            query,
            mode,
            target_document,
            filters_json,  # JSON文字列をPARSE_JSON関数に渡す
            timestamp,
            results_count
        ]).collect()
    
    def get_search_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """検索履歴の取得"""
        query = "SELECT * FROM search_history"
        params = {}
        
        if user_id:
            query += " WHERE user_id = :user_id"
            params["user_id"] = user_id
        
        query += " ORDER BY timestamp DESC LIMIT :limit"
        params["limit"] = limit
        
        results = self.session.sql(query, params).collect()
        return [
            {
                "id": row["ID"],
                "query": row["QUERY"],
                "mode": row["MODE"],
                "target_document": row["TARGET_DOCUMENT"],
                "filters": json.loads(row["FILTERS"]) if row["FILTERS"] else None,
                "timestamp": row["TIMESTAMP"],
                "results_count": row["RESULTS_COUNT"]
            }
            for row in results
        ]
    
    def export_results(
        self,
        results: List[Dict],
        format: str = "csv",
        filename: Optional[str] = None
    ) -> bytes:
        """
        検索結果のエクスポート
        
        Parameters:
        -----------
        results : List[Dict]
            エクスポートする検索結果
        format : str
            エクスポート形式 (csv/excel/pdf)
        filename : Optional[str]
            ファイル名（指定がない場合は自動生成）
            
        Returns:
        --------
        bytes
            エクスポートされたデータ
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"search_results_{timestamp}"
        
        # データフレームの作成
        df = pd.DataFrame([
            {
                "file_name": r["file_name"],
                "page": r["page"],
                "text": r.get("text", ""),
                "score": r.get("score", 0),
                "type": r.get("type", "unknown")
            }
            for r in results
        ])
        
        if format == "csv":
            return df.to_csv(index=False).encode("utf-8-sig")
        elif format == "excel":
            output = pd.ExcelWriter(filename + ".xlsx", engine="xlsxwriter")
            df.to_excel(output, index=False, sheet_name="Search Results")
            output.close()
            with open(filename + ".xlsx", "rb") as f:
                return f.read()
        elif format == "pdf":
            # PDFエクスポートの実装
            # 必要に応じてreportlabなどのライブラリを使用
            pass
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _vector_search(
        self,
        query: str,
        contents: Optional[List[Dict]],
        top_n: int,
        mode: str = "all"
    ) -> List[Dict]:
        """ベクトル検索の実装"""
        # 検索モードに応じた処理
        if mode == "single":
            # 個別PDF検索の場合は、ページ単位での類似度計算を最適化
            return self._optimized_single_doc_search(query, contents, top_n)
        else:
            # 複数PDF検索の場合は、通常のベクトル検索
            return self._standard_vector_search(query, contents, top_n)
    
    def _keyword_search(
        self,
        query: str,
        contents: Optional[List[Dict]],
        top_n: int,
        mode: str = "all"
    ) -> List[Dict]:
        """キーワード検索の実装"""
        # 検索モードに応じた処理
        if mode == "single":
            # 個別PDF検索の場合は、ページ単位でのキーワードマッチングを最適化
            return self._optimized_single_doc_keyword_search(query, contents, top_n)
        else:
            # 複数PDF検索の場合は、通常のキーワード検索
            return self._standard_keyword_search(query, contents, top_n)
    
    def _optimized_single_doc_search(
        self,
        query: str,
        contents: Optional[List[Dict]],
        top_n: int
    ) -> List[Dict]:
        """個別PDF検索用の最適化されたベクトル検索"""
        if not contents:
            return []
        
        # クエリの埋め込み
        query_embedding = self._get_query_embedding(query)
        
        # ページ単位での類似度計算
        results = []
        for content in contents:
            similarity = self._calculate_similarity(
                query_embedding,
                content.get("embedding", [])
            )
            if similarity > 0.5:  # 類似度の閾値
                results.append({
                    **content,
                    "similarity": similarity
                })
        
        # 類似度でソート
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_n]
    
    def _optimized_single_doc_keyword_search(
        self,
        query: str,
        contents: Optional[List[Dict]],
        top_n: int
    ) -> List[Dict]:
        """個別PDF検索用の最適化されたキーワード検索"""
        if not contents:
            return []
        
        # キーワードの抽出
        keywords = self._extract_keywords(query)
        
        # ページ単位でのキーワードマッチング
        results = []
        for content in contents:
            text = content.get("text", "").lower()
            matches = sum(1 for keyword in keywords if keyword.lower() in text)
            if matches > 0:
                results.append({
                    **content,
                    "match_score": matches / len(keywords)
                })
        
        # マッチスコアでソート
        results.sort(key=lambda x: x["match_score"], reverse=True)
        return results[:top_n]
    
    def _standard_vector_search(
        self,
        query: str,
        contents: Optional[List[Dict]],
        top_n: int
    ) -> List[Dict]:
        """複数PDF検索用の通常のベクトル検索"""
        # 既存のvector_utilsの実装を使用
        pass
    
    def _standard_keyword_search(
        self,
        query: str,
        contents: Optional[List[Dict]],
        top_n: int
    ) -> List[Dict]:
        """複数PDF検索用の通常のキーワード検索"""
        # 既存のvector_utilsの実装を使用
        pass 