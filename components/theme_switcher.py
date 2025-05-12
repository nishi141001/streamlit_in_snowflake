"""
テーマ切替コンポーネント

ダークモード/ライトモード切替
カスタムテーマ設定
"""

import streamlit as st
from typing import Dict, Optional
import json


class ThemeManager:
    """テーマ管理クラス"""
    
    def __init__(self):
        """初期化"""
        if 'theme' not in st.session_state:
            st.session_state.theme = {
                'mode': 'light',
                'primary_color': '#1E88E5',
                'background_color': '#FFFFFF',
                'text_color': '#000000',
                'font_family': 'sans-serif'
            }
    
    def get_current_theme(self) -> Dict[str, str]:
        """
        現在のテーマ設定を取得
        
        Returns:
        --------
        Dict[str, str]
            テーマ設定
        """
        return st.session_state.theme
    
    def set_theme(self, theme: Dict[str, str]) -> None:
        """
        テーマを設定
        
        Parameters:
        -----------
        theme : Dict[str, str]
            テーマ設定
        """
        st.session_state.theme = theme
        self._apply_theme()
    
    def toggle_mode(self) -> None:
        """ダークモード/ライトモードを切替"""
        current_theme = self.get_current_theme()
        new_mode = 'dark' if current_theme['mode'] == 'light' else 'light'
        
        # モードに応じた色を設定
        if new_mode == 'dark':
            theme = {
                'mode': 'dark',
                'primary_color': '#90CAF9',
                'background_color': '#121212',
                'text_color': '#FFFFFF',
                'font_family': current_theme['font_family']
            }
        else:
            theme = {
                'mode': 'light',
                'primary_color': '#1E88E5',
                'background_color': '#FFFFFF',
                'text_color': '#000000',
                'font_family': current_theme['font_family']
            }
        
        self.set_theme(theme)
    
    def _apply_theme(self) -> None:
        """テーマを適用"""
        theme = self.get_current_theme()
        
        # カスタムCSSの生成
        css = f"""
        <style>
            /* 全体のスタイル */
            .stApp {{
                background-color: {theme['background_color']};
                color: {theme['text_color']};
                font-family: {theme['font_family']};
            }}
            
            /* ヘッダー */
            .stApp header {{
                background-color: {theme['primary_color']};
            }}
            
            /* サイドバー */
            .css-1d391kg {{
                background-color: {theme['background_color']};
            }}
            
            /* ボタン */
            .stButton button {{
                background-color: {theme['primary_color']};
                color: white;
            }}
            
            /* リンク */
            a {{
                color: {theme['primary_color']};
            }}
            
            /* テキスト入力 */
            .stTextInput input {{
                background-color: {theme['background_color']};
                color: {theme['text_color']};
                border-color: {theme['primary_color']};
            }}
            
            /* セレクトボックス */
            .stSelectbox select {{
                background-color: {theme['background_color']};
                color: {theme['text_color']};
                border-color: {theme['primary_color']};
            }}
            
            /* テーブル */
            .stDataFrame {{
                background-color: {theme['background_color']};
                color: {theme['text_color']};
            }}
            
            /* カード */
            .stCard {{
                background-color: {theme['background_color']};
                border-color: {theme['primary_color']};
            }}
        </style>
        """
        
        # CSSの適用
        st.markdown(css, unsafe_allow_html=True)


def render_theme_switcher() -> None:
    """テーマ切替UIを表示"""
    theme_manager = ThemeManager()
    current_theme = theme_manager.get_current_theme()
    
    # テーマ切替ボタン
    if st.button(
        "🌙 ダークモード" if current_theme['mode'] == 'light' else "☀️ ライトモード",
        key="theme_toggle"
    ):
        theme_manager.toggle_mode()
        st.experimental_rerun()
    
    # カスタムテーマ設定（展開可能なセクション）
    with st.expander("カスタムテーマ設定"):
        # プライマリカラー
        primary_color = st.color_picker(
            "プライマリカラー",
            current_theme['primary_color']
        )
        
        # フォントファミリー
        font_family = st.selectbox(
            "フォント",
            ['sans-serif', 'serif', 'monospace'],
            index=['sans-serif', 'serif', 'monospace'].index(current_theme['font_family'])
        )
        
        # 設定の適用
        if st.button("テーマを適用"):
            new_theme = current_theme.copy()
            new_theme.update({
                'primary_color': primary_color,
                'font_family': font_family
            })
            theme_manager.set_theme(new_theme)
            st.experimental_rerun()


def get_theme_css() -> str:
    """
    現在のテーマのCSSを取得
    
    Returns:
    --------
    str
        カスタムCSS
    """
    theme_manager = ThemeManager()
    theme = theme_manager.get_current_theme()
    
    return f"""
    <style>
        :root {{
            --primary-color: {theme['primary_color']};
            --background-color: {theme['background_color']};
            --text-color: {theme['text_color']};
            --font-family: {theme['font_family']};
        }}
    </style>
    """ 