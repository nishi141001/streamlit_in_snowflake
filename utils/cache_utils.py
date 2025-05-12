"""
キャッシュ管理ユーティリティ

Snowflakeテーブルベースのキャッシュ管理
セッションベースのキャッシュ管理
キャッシュの自動クリーンアップ
"""

import streamlit as st
from typing import Any, Dict, List, Optional, Union
import pandas as pd
from datetime import datetime, timedelta
import hashlib
import json
from functools import wraps
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import col, lit, current_timestamp
from config import SETTINGS


class SnowflakeCache:
    """Snowflakeテーブルベースのキャッシュ管理"""
    
    def __init__(self, table_name: str = "cache_table"):
        """
        初期化
        
        Parameters:
        -----------
        table_name : str
            キャッシュテーブル名
        """
        self.session = get_active_session()
        self.table_name = table_name
        self._init_cache_table()
    
    def _init_cache_table(self) -> None:
        """キャッシュテーブルの初期化"""
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            cache_key VARCHAR,
            cache_value VARIANT,
            created_at TIMESTAMP,
            expires_at TIMESTAMP,
            metadata VARIANT,
            PRIMARY KEY (cache_key)
        )
        """
        
        try:
            self.session.sql(create_table_sql).collect()
        except Exception as e:
            print(f"キャッシュテーブル初期化中にエラー: {str(e)}")
    
    def _generate_key(self, key: Union[str, Dict]) -> str:
        """
        キャッシュキーの生成
        
        Parameters:
        -----------
        key : Union[str, Dict]
            キャッシュキー（文字列または辞書）
            
        Returns:
        --------
        str
            ハッシュ化されたキャッシュキー
        """
        if isinstance(key, dict):
            key_str = json.dumps(key, sort_keys=True)
        else:
            key_str = str(key)
        
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def get(self, key: Union[str, Dict], default: Any = None) -> Any:
        """
        キャッシュ値の取得
        
        Parameters:
        -----------
        key : Union[str, Dict]
            キャッシュキー
        default : Any
            デフォルト値
            
        Returns:
        --------
        Any
            キャッシュ値（存在しない場合はデフォルト値）
        """
        try:
            cache_key = self._generate_key(key)
            result = self.session.sql(f"""
                SELECT cache_value
                FROM {self.table_name}
                WHERE cache_key = '{cache_key}'
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP())
            """).collect()
            
            if result:
                return json.loads(result[0]["CACHE_VALUE"])
            return default
            
        except Exception as e:
            print(f"キャッシュ取得中にエラー: {str(e)}")
            return default
    
    def set(
        self,
        key: Union[str, Dict],
        value: Any,
        ttl: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        キャッシュ値の設定
        
        Parameters:
        -----------
        key : Union[str, Dict]
            キャッシュキー
        value : Any
            キャッシュ値
        ttl : Optional[int]
            有効期限（秒）
        metadata : Optional[Dict]
            メタデータ
            
        Returns:
        --------
        bool
            設定成功時True
        """
        try:
            cache_key = self._generate_key(key)
            expires_at = (
                current_timestamp() + lit(ttl) if ttl is not None
                else None
            )
            
            self.session.sql(f"""
                MERGE INTO {self.table_name} t
                USING (
                    SELECT
                        '{cache_key}' as cache_key,
                        PARSE_JSON('{json.dumps(value)}') as cache_value,
                        CURRENT_TIMESTAMP() as created_at,
                        {expires_at} as expires_at,
                        PARSE_JSON('{json.dumps(metadata or {})}') as metadata
                ) s
                ON t.cache_key = s.cache_key
                WHEN MATCHED THEN
                    UPDATE SET
                        t.cache_value = s.cache_value,
                        t.created_at = s.created_at,
                        t.expires_at = s.expires_at,
                        t.metadata = s.metadata
                WHEN NOT MATCHED THEN
                    INSERT (cache_key, cache_value, created_at, expires_at, metadata)
                    VALUES (s.cache_key, s.cache_value, s.created_at, s.expires_at, s.metadata)
            """).collect()
            
            return True
            
        except Exception as e:
            print(f"キャッシュ設定中にエラー: {str(e)}")
            return False
    
    def delete(self, key: Union[str, Dict]) -> bool:
        """
        キャッシュ値の削除
        
        Parameters:
        -----------
        key : Union[str, Dict]
            キャッシュキー
            
        Returns:
        --------
        bool
            削除成功時True
        """
        try:
            cache_key = self._generate_key(key)
            self.session.sql(f"""
                DELETE FROM {self.table_name}
                WHERE cache_key = '{cache_key}'
            """).collect()
            
            return True
            
        except Exception as e:
            print(f"キャッシュ削除中にエラー: {str(e)}")
            return False
    
    def clear_expired(self) -> int:
        """
        期限切れキャッシュの削除
        
        Returns:
        --------
        int
            削除されたキャッシュ数
        """
        try:
            result = self.session.sql(f"""
                DELETE FROM {self.table_name}
                WHERE expires_at <= CURRENT_TIMESTAMP()
                RETURNING COUNT(*)
            """).collect()
            
            return result[0]["COUNT(*)"]
            
        except Exception as e:
            print(f"期限切れキャッシュ削除中にエラー: {str(e)}")
            return 0
    
    def get_stats(self) -> Dict:
        """
        キャッシュ統計情報の取得
        
        Returns:
        --------
        dict
            統計情報
        """
        try:
            stats = self.session.sql(f"""
                SELECT
                    COUNT(*) as total_entries,
                    COUNT(CASE WHEN expires_at <= CURRENT_TIMESTAMP() THEN 1 END) as expired_entries,
                    AVG(JSON_LENGTH(cache_value)) as avg_value_size,
                    MAX(created_at) as last_updated
                FROM {self.table_name}
            """).collect()[0]
            
            return {
                "total_entries": stats["TOTAL_ENTRIES"],
                "expired_entries": stats["EXPIRED_ENTRIES"],
                "avg_value_size": float(stats["AVG_VALUE_SIZE"] or 0),
                "last_updated": stats["LAST_UPDATED"]
            }
            
        except Exception as e:
            print(f"統計情報取得中にエラー: {str(e)}")
            return {
                "total_entries": 0,
                "expired_entries": 0,
                "avg_value_size": 0,
                "last_updated": None
            }


class SessionCache:
    """セッションベースのキャッシュ管理"""
    
    def __init__(self, prefix: str = "cache_"):
        """
        初期化
        
        Parameters:
        -----------
        prefix : str
            キャッシュキーのプレフィックス
        """
        self.prefix = prefix
        if "cache" not in st.session_state:
            st.session_state.cache = {}
    
    def _get_key(self, key: Union[str, Dict]) -> str:
        """
        キャッシュキーの生成
        
        Parameters:
        -----------
        key : Union[str, Dict]
            キャッシュキー
            
        Returns:
        --------
        str
            完全なキャッシュキー
        """
        if isinstance(key, dict):
            key_str = json.dumps(key, sort_keys=True)
        else:
            key_str = str(key)
        
        return f"{self.prefix}{key_str}"
    
    def get(self, key: Union[str, Dict], default: Any = None) -> Any:
        """
        キャッシュ値の取得
        
        Parameters:
        -----------
        key : Union[str, Dict]
            キャッシュキー
        default : Any
            デフォルト値
            
        Returns:
        --------
        Any
            キャッシュ値
        """
        cache_key = self._get_key(key)
        cache_data = st.session_state.cache.get(cache_key)
        
        if cache_data is None:
            return default
        
        # 期限切れチェック
        if cache_data.get("expires_at"):
            if datetime.fromisoformat(cache_data["expires_at"]) <= datetime.now():
                del st.session_state.cache[cache_key]
                return default
        
        return cache_data["value"]
    
    def set(
        self,
        key: Union[str, Dict],
        value: Any,
        ttl: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        キャッシュ値の設定
        
        Parameters:
        -----------
        key : Union[str, Dict]
            キャッシュキー
        value : Any
            キャッシュ値
        ttl : Optional[int]
            有効期限（秒）
        metadata : Optional[Dict]
            メタデータ
        """
        cache_key = self._get_key(key)
        cache_data = {
            "value": value,
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        if ttl is not None:
            cache_data["expires_at"] = (
                datetime.now() + timedelta(seconds=ttl)
            ).isoformat()
        
        st.session_state.cache[cache_key] = cache_data
    
    def delete(self, key: Union[str, Dict]) -> None:
        """
        キャッシュ値の削除
        
        Parameters:
        -----------
        key : Union[str, Dict]
            キャッシュキー
        """
        cache_key = self._get_key(key)
        if cache_key in st.session_state.cache:
            del st.session_state.cache[cache_key]
    
    def clear_expired(self) -> int:
        """
        期限切れキャッシュの削除
        
        Returns:
        --------
        int
            削除されたキャッシュ数
        """
        expired_keys = []
        now = datetime.now()
        
        for key, data in st.session_state.cache.items():
            if data.get("expires_at"):
                if datetime.fromisoformat(data["expires_at"]) <= now:
                    expired_keys.append(key)
        
        for key in expired_keys:
            del st.session_state.cache[key]
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict:
        """
        キャッシュ統計情報の取得
        
        Returns:
        --------
        dict
            統計情報
        """
        total_entries = len(st.session_state.cache)
        expired_entries = 0
        total_size = 0
        now = datetime.now()
        
        for data in st.session_state.cache.values():
            if data.get("expires_at"):
                if datetime.fromisoformat(data["expires_at"]) <= now:
                    expired_entries += 1
            
            try:
                total_size += len(json.dumps(data["value"]))
            except:
                total_size += len(str(data["value"]))
        
        return {
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "avg_value_size": total_size / total_entries if total_entries > 0 else 0,
            "last_updated": datetime.now().isoformat()
        }


# キャッシュマネージャーのインスタンス化
snowflake_cache = SnowflakeCache()
session_cache = SessionCache()


def get_cache_manager(use_snowflake: bool = True) -> Union[SnowflakeCache, SessionCache]:
    """
    キャッシュマネージャーの取得
    
    Parameters:
    -----------
    use_snowflake : bool
        Snowflakeキャッシュを使用するかどうか
        
    Returns:
    --------
    Union[SnowflakeCache, SessionCache]
        キャッシュマネージャー
    """
    return snowflake_cache if use_snowflake else session_cache


def cached(
    cache_type: str = "session",
    ttl: Optional[int] = None,
    key_prefix: str = "",
    snowflake_conn = None
):
    """
    キャッシュデコレータ
    
    Parameters:
    -----------
    cache_type : str, optional
        キャッシュタイプ（"session" または "snowflake"）
    ttl : Optional[int], optional
        有効期限（秒）
    key_prefix : str, optional
        キャッシュキーのプレフィックス
    snowflake_conn : Optional[snowflake.connector.SnowflakeConnection], optional
        Snowflake接続オブジェクト（cache_type="snowflake"の場合に必要）
        
    Returns:
    --------
    Callable
        デコレートされた関数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # キャッシュキーの生成
            key_parts = [key_prefix, func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
            cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()
            
            # キャッシュの取得
            if cache_type == "session":
                cache = SessionCache()
                cached_value = cache.get(cache_key)
            else:  # snowflake
                if not snowflake_conn:
                    raise ValueError("snowflake_conn is required for snowflake cache")
                cache = SnowflakeCache(snowflake_conn)
                cached_value = cache.get(cache_key)
            
            if cached_value is not None:
                return cached_value
            
            # 関数の実行
            result = func(*args, **kwargs)
            
            # キャッシュの設定
            if cache_type == "session":
                cache.set(cache_key, result)
            else:  # snowflake
                cache.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator


def partial_update(
    original_data: Union[List, Dict],
    update_data: Union[List, Dict],
    key_field: Optional[str] = None
) -> Union[List, Dict]:
    """
    部分更新を実行
    
    Parameters:
    -----------
    original_data : Union[List, Dict]
        元のデータ
    update_data : Union[List, Dict]
        更新データ
    key_field : Optional[str], optional
        キーフィールド名（リストの場合に必要）
        
    Returns:
    --------
    Union[List, Dict]
        更新されたデータ
    """
    if isinstance(original_data, dict) and isinstance(update_data, dict):
        # 辞書の場合は再帰的に更新
        result = original_data.copy()
        for key, value in update_data.items():
            if isinstance(value, (dict, list)):
                result[key] = partial_update(
                    original_data.get(key, {} if isinstance(value, dict) else []),
                    value,
                    key_field
                )
            else:
                result[key] = value
        return result
    
    elif isinstance(original_data, list) and isinstance(update_data, list):
        if not key_field:
            raise ValueError("key_field is required for list updates")
        
        # リストの場合はキーフィールドでマッチング
        result = original_data.copy()
        update_dict = {item[key_field]: item for item in update_data}
        
        for i, item in enumerate(result):
            if item[key_field] in update_dict:
                result[i] = partial_update(item, update_dict[item[key_field]], key_field)
        
        # 新規アイテムの追加
        existing_keys = {item[key_field] for item in result}
        for item in update_data:
            if item[key_field] not in existing_keys:
                result.append(item)
        
        return result
    
    else:
        return update_data 