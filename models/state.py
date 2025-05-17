"""
アプリケーション状態管理

セッション状態の管理
グローバル状態の管理
状態の永続化
"""

import streamlit as st
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import json
from dataclasses import dataclass, asdict
import hashlib


@dataclass
class AppState:
    """アプリケーション状態"""
    current_page: str
    current_document: Optional[Dict]
    chat_history: List[Dict]
    search_history: List[Dict]
    analytics_data: Dict
    user_preferences: Dict
    last_updated: datetime


class StateManager:
    """状態管理クラス"""
    
    def __init__(self):
        """初期化"""
        self._init_session_state()
    
    def _init_session_state(self) -> None:
        """セッション状態の初期化"""
        if 'app_state' not in st.session_state:
            st.session_state.app_state = AppState(
                current_page='home',
                current_document=None,
                chat_history=[],
                search_history=[],
                analytics_data={},
                user_preferences={
                    'theme': 'light',
                    'language': 'ja',
                    'notifications': True
                },
                last_updated=datetime.now()
            )
    
    def get_state(self) -> AppState:
        """
        現在の状態を取得
        
        Returns:
        --------
        AppState
            アプリケーション状態
        """
        return st.session_state.app_state
    
    def update_state(self, **kwargs) -> None:
        """
        状態を更新
        
        Parameters:
        -----------
        **kwargs
            更新する状態のキーと値
        """
        current_state = self.get_state()
        for key, value in kwargs.items():
            if hasattr(current_state, key):
                setattr(current_state, key, value)
        current_state.last_updated = datetime.now()
        st.session_state.app_state = current_state
    
    def reset_state(self) -> None:
        """状態をリセット"""
        self._init_session_state()
    
    def get_state_hash(self) -> str:
        """
        状態のハッシュ値を取得
        
        Returns:
        --------
        str
            状態のハッシュ値
        """
        state_dict = asdict(self.get_state())
        state_dict['last_updated'] = state_dict['last_updated'].isoformat()
        state_json = json.dumps(state_dict, sort_keys=True)
        return hashlib.md5(state_json.encode()).hexdigest()
    
    def export_state(self, format: str = 'json') -> str:
        """
        状態をエクスポート
        
        Parameters:
        -----------
        format : str, optional
            エクスポート形式（'json' または 'dict'）
            
        Returns:
        --------
        str or Dict
            エクスポートされた状態
        """
        state_dict = asdict(self.get_state())
        state_dict['last_updated'] = state_dict['last_updated'].isoformat()
        
        if format == 'json':
            return json.dumps(state_dict, ensure_ascii=False, indent=2)
        return state_dict
    
    def import_state(self, state_data: Union[str, Dict]) -> None:
        """
        状態をインポート
        
        Parameters:
        -----------
        state_data : Union[str, Dict]
            インポートする状態データ
        """
        if isinstance(state_data, str):
            state_dict = json.loads(state_data)
        else:
            state_dict = state_data
        
        # 日付文字列をdatetimeに変換
        if 'last_updated' in state_dict:
            state_dict['last_updated'] = datetime.fromisoformat(state_dict['last_updated'])
        
        # 状態を更新
        self.update_state(**state_dict)


# グローバルな状態マネージャーのインスタンス
state_manager = StateManager() 