"""
ドキュメントサービス

ドキュメントの分類
エンティティ抽出
メタデータ管理

拡張機能
- フォルダ構造管理
- タグ管理
- バージョン管理
- アクセス権限管理
- 一括アップロード
"""

import streamlit as st
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from datetime import datetime
import json
import re
from dataclasses import dataclass, asdict
from enum import Enum
from utils.export_utils import export_manager, render_export_ui
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import col, lit, array_construct
from snowflake.snowpark.types import VectorType, FloatType
from utils.pdf_utils import extract_text, extract_tables_and_figures
from utils.vector_utils import (
    embed_text,
    create_vector_index,
    find_relevant_chunks,
    hybrid_search,
    search_in_tables_and_figures
)
from utils.cache_utils import SnowflakeCache
from config import SETTINGS
import os
from pathlib import Path


class DocumentType(Enum):
    """ドキュメントタイプ"""
    REPORT = "report"
    CONTRACT = "contract"
    MANUAL = "manual"
    PRESENTATION = "presentation"
    OTHER = "other"


@dataclass
class DocumentMetadata:
    """ドキュメントメタデータ"""
    title: str
    author: Optional[str]
    creation_date: Optional[datetime]
    document_type: DocumentType
    keywords: List[str]
    summary: Optional[str]
    page_count: int
    file_size: int
    language: str
    custom_metadata: Dict


class DocumentClassifier:
    """ドキュメント分類クラス"""
    
    def __init__(self):
        """初期化"""
        # キーワードベースの分類ルール
        self.classification_rules = {
            DocumentType.REPORT: [
                r'report', r'analysis', r'study', r'research',
                r'調査', r'報告', r'分析', r'研究'
            ],
            DocumentType.CONTRACT: [
                r'contract', r'agreement', r'terms', r'conditions',
                r'契約', r'合意', r'条項', r'条件'
            ],
            DocumentType.MANUAL: [
                r'manual', r'guide', r'instruction', r'tutorial',
                r'マニュアル', r'ガイド', r'説明書', r'手順書'
            ],
            DocumentType.PRESENTATION: [
                r'presentation', r'slide', r'deck', r'pitch',
                r'プレゼン', r'スライド', r'資料'
            ]
        }
    
    def classify_document(self, text: str, metadata: Dict) -> DocumentType:
        """
        ドキュメントを分類
        
        Parameters:
        -----------
        text : str
            ドキュメントテキスト
        metadata : Dict
            メタデータ
            
        Returns:
        --------
        DocumentType
            分類されたドキュメントタイプ
        """
        # テキストとメタデータを結合して検索
        search_text = f"{text} {json.dumps(metadata, ensure_ascii=False)}".lower()
        
        # 各タイプのキーワードをチェック
        for doc_type, patterns in self.classification_rules.items():
            for pattern in patterns:
                if re.search(pattern, search_text, re.IGNORECASE):
                    return doc_type
        
        return DocumentType.OTHER


class EntityExtractor:
    """エンティティ抽出クラス"""
    
    def __init__(self):
        """初期化"""
        # エンティティパターン
        self.entity_patterns = {
            'date': [
                r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?',
                r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',
                r'\d{4}年\d{1,2}月\d{1,2}日'
            ],
            'money': [
                r'¥\s*\d+(?:,\d{3})*(?:\.\d+)?',
                r'\d+(?:,\d{3})*(?:\.\d+)?\s*円',
                r'\$\s*\d+(?:,\d{3})*(?:\.\d+)?',
                r'\d+(?:,\d{3})*(?:\.\d+)?\s*ドル'
            ],
            'percentage': [
                r'\d+(?:\.\d+)?\s*%',
                r'\d+(?:\.\d+)?\s*パーセント'
            ],
            'email': [
                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            ],
            'url': [
                r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+',
                r'www\.(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
            ]
        }
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        エンティティを抽出
        
        Parameters:
        -----------
        text : str
            テキスト
            
        Returns:
        --------
        Dict[str, List[str]]
            抽出されたエンティティ
        """
        entities = {}
        
        for entity_type, patterns in self.entity_patterns.items():
            matches = []
            for pattern in patterns:
                matches.extend(re.findall(pattern, text))
            if matches:
                entities[entity_type] = list(set(matches))
        
        return entities


class DocumentService:
    """ドキュメントサービス"""
    
    def __init__(self):
        """初期化"""
        self.session = get_active_session()
        self.cache = SnowflakeCache()
        self.vector_dim = 384  # デフォルトのベクトル次元数
        self._init_tables()
    
    def _init_tables(self) -> None:
        """必要なテーブルの初期化"""
        try:
            # 既存のテーブルを個別に削除（外部キー制約を考慮して逆順に削除）
            self.session.sql("DROP TABLE IF EXISTS document_access").collect()
            self.session.sql("DROP TABLE IF EXISTS document_versions").collect()
            self.session.sql("DROP TABLE IF EXISTS document_tags").collect()
            self.session.sql("DROP TABLE IF EXISTS document_figures").collect()
            self.session.sql("DROP TABLE IF EXISTS document_tables").collect()
            self.session.sql("DROP TABLE IF EXISTS document_chunks").collect()
            self.session.sql("DROP TABLE IF EXISTS documents").collect()

            # ドキュメントテーブルを個別に作成（外部キー制約の親テーブル）
            create_documents = """
            CREATE TABLE IF NOT EXISTS documents (
                doc_id STRING,
                file_name STRING,
                upload_date TIMESTAMP,
                file_type STRING,
                file_size INTEGER,
                page_count INTEGER,
                folder_path STRING,
                version INTEGER,
                status STRING,
                metadata VARIANT,
                PRIMARY KEY (doc_id)
            )
            """
            self.session.sql(create_documents).collect()
            
            # ドキュメントチャンクテーブルを個別に作成
            create_document_chunks = """
            CREATE TABLE IF NOT EXISTS document_chunks (
                chunk_id STRING,
                doc_id STRING,
                page_num INTEGER,
                chunk_num INTEGER,
                text STRING,
                embedding VECTOR(FLOAT, {self.vector_dim}),
                metadata VARIANT,
                PRIMARY KEY (chunk_id),
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
            )
            """
            self.session.sql(create_document_chunks).collect()

            # ドキュメントテーブルテーブルを個別に作成
            create_document_tables = """
            CREATE TABLE IF NOT EXISTS document_tables (
                table_id STRING,
                doc_id STRING,
                page_num INTEGER,
                table_num INTEGER,
                data VARIANT,
                bbox VARIANT,
                metadata VARIANT,
                PRIMARY KEY (table_id),
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
            )
            """
            self.session.sql(create_document_tables).collect()

            # ドキュメント図表テーブルを個別に作成
            create_document_figures = """
            CREATE TABLE IF NOT EXISTS document_figures (
                figure_id STRING,
                doc_id STRING,
                page_num INTEGER,
                figure_num INTEGER,
                bbox VARIANT,
                metadata VARIANT,
                PRIMARY KEY (figure_id),
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
            )
            """
            self.session.sql(create_document_figures).collect()
            
            # タグテーブルを個別に作成
            create_document_tags = """
            CREATE TABLE IF NOT EXISTS document_tags (
                file_name STRING,
                tag STRING,
                created_at TIMESTAMP,
                created_by STRING,
                PRIMARY KEY (file_name, tag),
                FOREIGN KEY (file_name) REFERENCES documents(file_name)
            )
            """
            self.session.sql(create_document_tags).collect()
            
            # バージョン履歴テーブルを個別に作成
            create_document_versions = """
            CREATE TABLE IF NOT EXISTS document_versions (
                file_name STRING,
                version INTEGER,
                upload_date TIMESTAMP,
                uploaded_by STRING,
                change_description STRING,
                file_hash STRING,
                PRIMARY KEY (file_name, version),
                FOREIGN KEY (file_name) REFERENCES documents(file_name)
            )
            """
            self.session.sql(create_document_versions).collect()
            
            # アクセス権限テーブルを個別に作成
            create_document_access = """
            CREATE TABLE IF NOT EXISTS document_access (
                file_name STRING,
                user_id STRING,
                permission STRING,
                granted_at TIMESTAMP,
                granted_by STRING,
                PRIMARY KEY (file_name, user_id),
                FOREIGN KEY (file_name) REFERENCES documents(file_name)
            )
            """
            self.session.sql(create_document_access).collect()

        except Exception as e:
            print(f"テーブル初期化中にエラー: {str(e)}")
            raise
    
    def upload_document(
        self,
        file_data: bytes,
        file_name: str,
        folder_path: str = "/",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
        access_control: Optional[Dict] = None
    ) -> Dict:
        """
        ドキュメントのアップロード
        
        Parameters:
        -----------
        file_data : bytes
            ファイルデータ
        file_name : str
            ファイル名
        folder_path : str
            フォルダパス
        tags : Optional[List[str]]
            タグリスト
        metadata : Optional[Dict]
            メタデータ
        access_control : Optional[Dict]
            アクセス権限設定
            
        Returns:
        --------
        Dict
            アップロード結果
        """
        try:
            # ファイル情報の取得
            file_type = os.path.splitext(file_name)[1].lower()
            file_size = len(file_data)
            
            # バージョン番号の取得（個別に実行）
            version = self._get_next_version(file_name)
            
            # ドキュメントの保存（個別に実行）
            doc_id = f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.session.sql("""
            INSERT INTO documents (
                doc_id, file_name, upload_date, file_type, file_size,
                folder_path, version, status, metadata
            ) VALUES (
                :doc_id, :file_name, :upload_date, :file_type, :file_size,
                :folder_path, :version, :status, PARSE_JSON(:metadata)
            )
            """, {
                "doc_id": doc_id,
                "file_name": file_name,
                "upload_date": datetime.now(),
                "file_type": file_type,
                "file_size": file_size,
                "folder_path": folder_path,
                "version": version,
                "status": "active",
                "metadata": json.dumps(metadata) if metadata else "{}"
            }).collect()
            
            # タグの保存（個別に実行）
            if tags:
                for tag in tags:
                    self.session.sql("""
                    INSERT INTO document_tags (file_name, tag, created_at, created_by)
                    VALUES (:file_name, :tag, :created_at, :created_by)
                    """, {
                        "file_name": file_name,
                        "tag": tag,
                        "created_at": datetime.now(),
                        "created_by": st.session_state.get("user_id", "system")
                    }).collect()
            
            # アクセス権限の設定（個別に実行）
            if access_control:
                for user_id, permissions in access_control.items():
                    for permission in permissions:
                        self.session.sql("""
                        INSERT INTO document_access (
                            file_name, user_id, permission,
                            granted_at, granted_by
                        ) VALUES (
                            :file_name, :user_id, :permission,
                            :granted_at, :granted_by
                        )
                        """, {
                            "file_name": file_name,
                            "user_id": user_id,
                            "permission": permission,
                            "granted_at": datetime.now(),
                            "granted_by": st.session_state.get("user_id", "system")
                        }).collect()
            
            # バージョン履歴の保存（個別に実行）
            self.session.sql("""
            INSERT INTO document_versions (
                file_name, version, upload_date,
                uploaded_by, change_description
            ) VALUES (
                :file_name, :version, :upload_date,
                :uploaded_by, :change_description
            )
            """, {
                "file_name": file_name,
                "version": version,
                "upload_date": datetime.now(),
                "uploaded_by": st.session_state.get("user_id", "system"),
                "change_description": "Initial upload"
            }).collect()
            
            # キャッシュのクリア
            self.cache.delete("document_contents")
            
            return {
                "file_name": file_name,
                "version": version,
                "status": "success"
            }
            
        except Exception as e:
            print(f"ドキュメントアップロード中にエラー: {str(e)}")
            raise
    
    def upload_multiple_documents(
        self,
        files: List[Dict],
        folder_path: str = "/",
        tags: Optional[Dict[str, List[str]]] = None,
        metadata: Optional[Dict[str, Dict]] = None,
        access_control: Optional[Dict[str, Dict]] = None
    ) -> List[Dict]:
        """
        複数ドキュメントの一括アップロード
        
        Parameters:
        -----------
        files : List[Dict]
            ファイルデータのリスト
            - file_data: bytes
            - file_name: str
        folder_path : str
            フォルダパス
        tags : Optional[Dict[str, List[str]]]
            ファイルごとのタグ
        metadata : Optional[Dict[str, Dict]]
            ファイルごとのメタデータ
        access_control : Optional[Dict[str, Dict]]
            ファイルごとのアクセス権限
            
        Returns:
        --------
        List[Dict]
            アップロード結果のリスト
        """
        results = []
        
        for file_info in files:
            try:
                result = self.upload_document(
                    file_data=file_info["file_data"],
                    file_name=file_info["file_name"],
                    folder_path=folder_path,
                    tags=tags.get(file_info["file_name"]) if tags else None,
                    metadata=metadata.get(file_info["file_name"]) if metadata else None,
                    access_control=access_control.get(file_info["file_name"]) if access_control else None
                )
                results.append({
                    "file_name": file_info["file_name"],
                    "status": "success",
                    "version": result["version"]
                })
            except Exception as e:
                results.append({
                    "file_name": file_info["file_name"],
                    "status": "error",
                    "error": str(e)
                })
        
        return results
    
    def get_document_info(
        self,
        file_name: str,
        include_tags: bool = True,
        include_versions: bool = False,
        include_access: bool = False
    ) -> Dict:
        """
        ドキュメント情報の取得
        
        Parameters:
        -----------
        file_name : str
            ファイル名
        include_tags : bool
            タグ情報を含めるかどうか
        include_versions : bool
            バージョン履歴を含めるかどうか
        include_access : bool
            アクセス権限情報を含めるかどうか
            
        Returns:
        --------
        Dict
            ドキュメント情報
        """
        # 基本情報の取得
        doc_info = self.session.sql("""
        SELECT * FROM documents WHERE file_name = :file_name
        """, {"file_name": file_name}).collect()
        
        if not doc_info:
            raise ValueError(f"Document not found: {file_name}")
        
        doc_info = doc_info[0]
        result = {
            "file_name": doc_info["FILE_NAME"],
            "upload_date": doc_info["UPLOAD_DATE"],
            "file_type": doc_info["FILE_TYPE"],
            "file_size": doc_info["FILE_SIZE"],
            "folder_path": doc_info["FOLDER_PATH"],
            "version": doc_info["VERSION"],
            "status": doc_info["STATUS"],
            "metadata": json.loads(doc_info["METADATA"]) if doc_info["METADATA"] else None
        }
        
        # タグ情報の取得
        if include_tags:
            result["tags"] = self._get_tags(file_name)
        
        # バージョン履歴の取得
        if include_versions:
            result["versions"] = self._get_version_history(file_name)
        
        # アクセス権限情報の取得
        if include_access:
            result["access_control"] = self._get_access_control(file_name)
        
        return result
    
    def update_document(
        self,
        file_name: str,
        file_data: Optional[bytes] = None,
        folder_path: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
        access_control: Optional[Dict] = None,
        change_description: Optional[str] = None
    ) -> Dict:
        """
        ドキュメントの更新
        
        Parameters:
        -----------
        file_name : str
            ファイル名
        file_data : Optional[bytes]
            新しいファイルデータ
        folder_path : Optional[str]
            新しいフォルダパス
        tags : Optional[List[str]]
            新しいタグリスト
        metadata : Optional[Dict]
            新しいメタデータ
        access_control : Optional[Dict]
            新しいアクセス権限設定
        change_description : Optional[str]
            変更説明
            
        Returns:
        --------
        Dict
            更新結果
        """
        # 現在のバージョン情報の取得
        current_info = self.get_document_info(file_name)
        current_version = current_info["version"]
        
        # 新しいバージョン番号の取得
        new_version = current_version + 1
        
        # 更新情報の準備
        update_data = {}
        if file_data is not None:
            update_data["file_size"] = len(file_data)
        if folder_path is not None:
            update_data["folder_path"] = folder_path
        if metadata is not None:
            update_data["metadata"] = json.dumps(metadata)
        update_data["version"] = new_version
        
        # ドキュメント情報の更新
        if update_data:
            set_clause = ", ".join(f"{k} = :{k}" for k in update_data.keys())
            self.session.sql(f"""
            UPDATE documents SET {set_clause}
            WHERE file_name = :file_name
            """, {**update_data, "file_name": file_name}).collect()
        
        # タグの更新
        if tags is not None:
            self._update_tags(file_name, tags)
        
        # アクセス権限の更新
        if access_control is not None:
            self._update_access_control(file_name, access_control)
        
        # バージョン履歴の保存
        self._save_version_history(
            file_name,
            new_version,
            change_description or "Document updated"
        )
        
        # キャッシュのクリア
        self.cache.delete("document_contents")
        
        return {
            "file_name": file_name,
            "old_version": current_version,
            "new_version": new_version,
            "status": "success"
        }
    
    def delete_document(
        self,
        file_name: str,
        permanent: bool = False
    ) -> Dict:
        """
        ドキュメントの削除
        
        Parameters:
        -----------
        file_name : str
            ファイル名
        permanent : bool
            完全に削除するかどうか
            
        Returns:
        --------
        Dict
            削除結果
        """
        if permanent:
            # 完全削除
            self.session.sql("""
            DELETE FROM document_tags WHERE file_name = :file_name
            """, {"file_name": file_name}).collect()
            
            self.session.sql("""
            DELETE FROM document_versions WHERE file_name = :file_name
            """, {"file_name": file_name}).collect()
            
            self.session.sql("""
            DELETE FROM document_access WHERE file_name = :file_name
            """, {"file_name": file_name}).collect()
            
            self.session.sql("""
            DELETE FROM documents WHERE file_name = :file_name
            """, {"file_name": file_name}).collect()
        else:
            # 論理削除（ステータスの更新）
            self.session.sql("""
            UPDATE documents SET status = 'deleted'
            WHERE file_name = :file_name
            """, {"file_name": file_name}).collect()
        
        # キャッシュのクリア
        self.cache.delete("document_contents")
        
        return {
            "file_name": file_name,
            "status": "success",
            "permanent": permanent
        }
    
    def _get_next_version(self, file_name: str) -> int:
        """次のバージョン番号の取得"""
        result = self.session.sql("""
        SELECT MAX(version) as max_version
        FROM documents
        WHERE file_name = :file_name
        """, {"file_name": file_name}).collect()
        
        current_max = result[0]["MAX_VERSION"]
        return 1 if current_max is None else current_max + 1
    
    def _save_tags(self, file_name: str, tags: List[str]) -> None:
        """タグの保存"""
        for tag in tags:
            self.session.sql("""
            INSERT INTO document_tags (file_name, tag, created_at, created_by)
            VALUES (:file_name, :tag, :created_at, :created_by)
            """, {
                "file_name": file_name,
                "tag": tag,
                "created_at": datetime.now(),
                "created_by": st.session_state.get("user_id", "system")
            }).collect()
    
    def _get_tags(self, file_name: str) -> List[str]:
        """タグの取得"""
        results = self.session.sql("""
        SELECT tag FROM document_tags
        WHERE file_name = :file_name
        ORDER BY created_at
        """, {"file_name": file_name}).collect()
        
        return [row["TAG"] for row in results]
    
    def _update_tags(self, file_name: str, new_tags: List[str]) -> None:
        """タグの更新"""
        # 既存のタグを削除
        self.session.sql("""
        DELETE FROM document_tags
        WHERE file_name = :file_name
        """, {"file_name": file_name}).collect()
        
        # 新しいタグを保存
        self._save_tags(file_name, new_tags)
    
    def _set_access_control(
        self,
        file_name: str,
        access_control: Dict[str, List[str]]
    ) -> None:
        """アクセス権限の設定"""
        for user_id, permissions in access_control.items():
            for permission in permissions:
                self.session.sql("""
                INSERT INTO document_access (
                    file_name, user_id, permission,
                    granted_at, granted_by
                ) VALUES (
                    :file_name, :user_id, :permission,
                    :granted_at, :granted_by
                )
                """, {
                    "file_name": file_name,
                    "user_id": user_id,
                    "permission": permission,
                    "granted_at": datetime.now(),
                    "granted_by": st.session_state.get("user_id", "system")
                }).collect()
    
    def _get_access_control(self, file_name: str) -> Dict[str, List[str]]:
        """アクセス権限の取得"""
        results = self.session.sql("""
        SELECT user_id, permission
        FROM document_access
        WHERE file_name = :file_name
        ORDER BY granted_at
        """, {"file_name": file_name}).collect()
        
        access_control = {}
        for row in results:
            user_id = row["USER_ID"]
            permission = row["PERMISSION"]
            if user_id not in access_control:
                access_control[user_id] = []
            access_control[user_id].append(permission)
        
        return access_control
    
    def _update_access_control(
        self,
        file_name: str,
        new_access_control: Dict[str, List[str]]
    ) -> None:
        """アクセス権限の更新"""
        # 既存の権限を削除
        self.session.sql("""
        DELETE FROM document_access
        WHERE file_name = :file_name
        """, {"file_name": file_name}).collect()
        
        # 新しい権限を設定
        self._set_access_control(file_name, new_access_control)
    
    def _save_version_history(
        self,
        file_name: str,
        version: int,
        change_description: str
    ) -> None:
        """バージョン履歴の保存"""
        self.session.sql("""
        INSERT INTO document_versions (
            file_name, version, upload_date,
            uploaded_by, change_description
        ) VALUES (
            :file_name, :version, :upload_date,
            :uploaded_by, :change_description
        )
        """, {
            "file_name": file_name,
            "version": version,
            "upload_date": datetime.now(),
            "uploaded_by": st.session_state.get("user_id", "system"),
            "change_description": change_description
        }).collect()
    
    def _get_version_history(self, file_name: str) -> List[Dict]:
        """バージョン履歴の取得"""
        results = self.session.sql("""
        SELECT * FROM document_versions
        WHERE file_name = :file_name
        ORDER BY version DESC
        """, {"file_name": file_name}).collect()
        
        return [
            {
                "version": row["VERSION"],
                "upload_date": row["UPLOAD_DATE"],
                "uploaded_by": row["UPLOADED_BY"],
                "change_description": row["CHANGE_DESCRIPTION"]
            }
            for row in results
        ]

    def process_document(
        self,
        file_path: str,
        file_name: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        PDF文書の処理
        
        Parameters:
        -----------
        file_path : str
            PDFファイルのパス
        file_name : str
            ファイル名
        metadata : Optional[Dict]
            追加のメタデータ
            
        Returns:
        --------
        str
            文書ID
        """
        try:
            # 文書IDの生成
            doc_id = f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # テキスト抽出
            text_chunks = extract_text(file_path)
            
            # テーブルと図表の抽出
            tables_and_figures = extract_tables_and_figures(file_path)
            tables = [item for item in tables_and_figures if item.get("type") == "table"]
            figures = [item for item in tables_and_figures if item.get("type") == "figure"]
            
            # 文書メタデータの準備
            doc_metadata = {
                "file_name": file_name,
                "upload_time": datetime.now().isoformat(),
                "num_pages": len(text_chunks),
                "num_tables": len(tables),
                "num_figures": len(figures),
                **(metadata or {})
            }
            
            # 文書データの保存（個別に実行）
            self.session.sql("""
                INSERT INTO documents (doc_id, file_name, upload_date, metadata)
                VALUES (:doc_id, :file_name, CURRENT_TIMESTAMP(), PARSE_JSON(:metadata))
            """, {
                "doc_id": doc_id,
                "file_name": file_name,
                "metadata": json.dumps(doc_metadata)
            }).collect()
            
            # チャンクのベクトル化と保存（個別に実行）
            for page_num, chunks in enumerate(text_chunks, 1):
                # テキストのベクトル化
                embeddings = embed_text(chunks)
                
                # チャンクデータの保存
                for chunk_num, (text, embedding) in enumerate(zip(chunks, embeddings), 1):
                    chunk_id = f"{doc_id}_p{page_num}_c{chunk_num}"
                    chunk_metadata = {
                        "page_num": page_num,
                        "chunk_num": chunk_num,
                        "text_length": len(text)
                    }
                    
                    self.session.sql("""
                        INSERT INTO document_chunks (
                            chunk_id, doc_id, page_num, chunk_num,
                            text, embedding, metadata
                        )
                        VALUES (
                            :chunk_id, :doc_id, :page_num, :chunk_num,
                            :text, :embedding, PARSE_JSON(:metadata)
                        )
                    """, {
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "page_num": page_num,
                        "chunk_num": chunk_num,
                        "text": text,
                        "embedding": embedding,
                        "metadata": json.dumps(chunk_metadata)
                    }).collect()
            
            # テーブルデータの保存（個別に実行）
            for page_num, page_tables in enumerate(tables, 1):
                for table_num, table in enumerate(page_tables, 1):
                    table_id = f"{doc_id}_p{page_num}_t{table_num}"
                    table_metadata = {
                        "page_num": page_num,
                        "table_num": table_num,
                        "num_rows": len(table["data"]),
                        "num_cols": len(table["data"][0]) if table["data"] else 0
                    }
                    
                    self.session.sql("""
                        INSERT INTO document_tables (
                            table_id, doc_id, page_num, table_num,
                            data, bbox, metadata
                        )
                        VALUES (
                            :table_id, :doc_id, :page_num, :table_num,
                            PARSE_JSON(:data), PARSE_JSON(:bbox), PARSE_JSON(:metadata)
                        )
                    """, {
                        "table_id": table_id,
                        "doc_id": doc_id,
                        "page_num": page_num,
                        "table_num": table_num,
                        "data": json.dumps(table["data"]),
                        "bbox": json.dumps(table["bbox"]),
                        "metadata": json.dumps(table_metadata)
                    }).collect()
            
            # 図表データの保存（個別に実行）
            for page_num, page_figures in enumerate(figures, 1):
                for figure_num, figure in enumerate(page_figures, 1):
                    figure_id = f"{doc_id}_p{page_num}_f{figure_num}"
                    figure_metadata = {
                        "page_num": page_num,
                        "figure_num": figure_num,
                        "width": figure.get("width", 0),
                        "height": figure.get("height", 0)
                    }
                    
                    self.session.sql("""
                        INSERT INTO document_figures (
                            figure_id, doc_id, page_num, figure_num,
                            bbox, metadata
                        )
                        VALUES (
                            :figure_id, :doc_id, :page_num, :figure_num,
                            PARSE_JSON(:bbox), PARSE_JSON(:metadata)
                        )
                    """, {
                        "figure_id": figure_id,
                        "doc_id": doc_id,
                        "page_num": page_num,
                        "figure_num": figure_num,
                        "bbox": json.dumps(figure["bbox"]),
                        "metadata": json.dumps(figure_metadata)
                    }).collect()
            
            return doc_id
            
        except Exception as e:
            print(f"文書処理中にエラー: {str(e)}")
            raise
    
    def search_documents(
        self,
        query: str,
        doc_ids: Optional[List[str]] = None,
        search_type: str = "hybrid",
        top_n: int = 5,
        threshold: Optional[float] = None
    ) -> List[Dict]:
        """
        文書検索
        
        Parameters:
        -----------
        query : str
            検索クエリ
        doc_ids : Optional[List[str]]
            検索対象の文書IDリスト
        search_type : str
            検索タイプ ("hybrid", "vector", "keyword", "tables_figures")
        top_n : int
            取得する結果数
        threshold : Optional[float]
            類似度閾値
            
        Returns:
        --------
        list[dict]
            検索結果のリスト
        """
        try:
            # 検索対象の文書チャンクを取得
            chunks_query = """
                SELECT c.*, d.file_name
                FROM document_chunks c
                JOIN documents d ON c.doc_id = d.doc_id
            """
            
            if doc_ids:
                doc_ids_str = ','.join(f"'{id}'" for id in doc_ids)
                chunks_query += f" WHERE c.doc_id IN ({doc_ids_str})"
            
            chunks_df = self.session.sql(chunks_query)
            
            if chunks_df.is_empty():
                return []
            
            # 検索タイプに応じた検索実行
            if search_type == "hybrid":
                results = hybrid_search(
                    query,
                    chunks_df.collect(),
                    top_n=top_n,
                    threshold=threshold
                )
            elif search_type == "vector":
                query_embedding = embed_text([query])[0]
                results = find_relevant_chunks(
                    query_embedding,
                    chunks_df.collect(),
                    top_n=top_n,
                    threshold=threshold
                )
            elif search_type == "keyword":
                results = _keyword_search(
                    query,
                    chunks_df.collect(),
                    top_n=top_n
                )
            elif search_type == "tables_figures":
                results = search_in_tables_and_figures(
                    query,
                    chunks_df.collect(),
                    top_n=top_n
                )
            else:
                raise ValueError(f"未サポートの検索タイプ: {search_type}")
            
            return results
            
        except Exception as e:
            print(f"文書検索中にエラー: {str(e)}")
            return []
    
    def get_document_metadata(self, doc_id: str) -> Optional[Dict]:
        """
        文書メタデータの取得
        
        Parameters:
        -----------
        doc_id : str
            文書ID
            
        Returns:
        --------
        Optional[Dict]
            文書メタデータ
        """
        try:
            result = self.session.sql(f"""
                SELECT metadata
                FROM documents
                WHERE doc_id = '{doc_id}'
            """).collect()
            
            if result:
                return json.loads(result[0]["METADATA"])
            return None
            
        except Exception as e:
            print(f"メタデータ取得中にエラー: {str(e)}")
            return None
    
    def get_document_statistics(self) -> Dict:
        """
        文書統計情報の取得
        
        Returns:
        --------
        dict
            統計情報
        """
        try:
            stats = self.session.sql("""
                SELECT
                    COUNT(DISTINCT doc_id) as total_documents,
                    COUNT(DISTINCT chunk_id) as total_chunks,
                    COUNT(DISTINCT table_id) as total_tables,
                    COUNT(DISTINCT figure_id) as total_figures,
                    AVG(JSON_LENGTH(metadata, '$.num_pages')) as avg_pages_per_doc
                FROM documents d
                LEFT JOIN document_chunks c ON d.doc_id = c.doc_id
                LEFT JOIN document_tables t ON d.doc_id = t.doc_id
                LEFT JOIN document_figures f ON d.doc_id = f.doc_id
            """).collect()[0]
            
            return {
                "total_documents": stats["TOTAL_DOCUMENTS"],
                "total_chunks": stats["TOTAL_CHUNKS"],
                "total_tables": stats["TOTAL_TABLES"],
                "total_figures": stats["TOTAL_FIGURES"],
                "avg_pages_per_doc": float(stats["AVG_PAGES_PER_DOC"] or 0)
            }
            
        except Exception as e:
            print(f"統計情報取得中にエラー: {str(e)}")
            return {
                "total_documents": 0,
                "total_chunks": 0,
                "total_tables": 0,
                "total_figures": 0,
                "avg_pages_per_doc": 0
            }
    
    def update_metadata(
        self,
        current_metadata: DocumentMetadata,
        updates: Dict[str, Any]
    ) -> DocumentMetadata:
        """
        メタデータを更新
        
        Parameters:
        -----------
        current_metadata : DocumentMetadata
            現在のメタデータ
        updates : Dict[str, Any]
            更新内容
            
        Returns:
        --------
        DocumentMetadata
            更新されたメタデータ
        """
        # 更新可能なフィールド
        updateable_fields = {
            'title', 'author', 'keywords', 'summary',
            'language', 'custom_metadata'
        }
        
        # 更新
        for field, value in updates.items():
            if field in updateable_fields:
                setattr(current_metadata, field, value)
        
        return current_metadata
    
    def export_metadata(
        self,
        metadata: DocumentMetadata,
        format: str = 'json',
        filename: Optional[str] = None
    ) -> None:
        """
        メタデータをエクスポート
        
        Parameters:
        -----------
        metadata : DocumentMetadata
            エクスポートするメタデータ
        format : str, optional
            エクスポート形式（'json', 'csv', 'excel'）
        filename : Optional[str], optional
            ファイル名
        """
        # メタデータを辞書に変換
        metadata_dict = asdict(metadata)
        
        # 日付型の変換
        if metadata_dict.get('creation_date'):
            metadata_dict['creation_date'] = metadata_dict['creation_date'].isoformat()
        
        # エクスポートUIの表示
        render_export_ui(
            data=metadata_dict,
            title="メタデータのエクスポート",
            default_filename=filename or f"metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}",
            metadata={
                'export_type': 'document_metadata',
                'document_type': metadata.document_type.value,
                'export_timestamp': datetime.now().isoformat()
            }
        )
    
    def export_entities(
        self,
        entities: Dict[str, List[str]],
        format: str = 'json',
        filename: Optional[str] = None
    ) -> None:
        """
        エンティティをエクスポート
        
        Parameters:
        -----------
        entities : Dict[str, List[str]]
            エクスポートするエンティティ
        format : str, optional
            エクスポート形式（'json', 'csv', 'excel'）
        filename : Optional[str], optional
            ファイル名
        """
        # エクスポートUIの表示
        render_export_ui(
            data=entities,
            title="エンティティのエクスポート",
            default_filename=filename or f"entities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}",
            metadata={
                'export_type': 'document_entities',
                'entity_types': list(entities.keys()),
                'export_timestamp': datetime.now().isoformat()
            }
        ) 