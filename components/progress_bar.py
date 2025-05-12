"""
プログレスバーコンポーネント

処理状況の表示
非同期タスクの進捗表示
"""

import streamlit as st
from typing import Optional, Callable, Dict, Any
import time
from utils.async_utils import AsyncTaskManager


class ProgressBar:
    """プログレスバー管理クラス"""
    
    def __init__(self, total_steps: int = 100):
        """
        初期化
        
        Parameters:
        -----------
        total_steps : int, optional
            総ステップ数
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.status_text = ""
        self.start_time = None
        self.estimated_time = None
    
    def start(self, status_text: str = "処理中...") -> None:
        """
        プログレスバーを開始
        
        Parameters:
        -----------
        status_text : str, optional
            ステータステキスト
        """
        self.current_step = 0
        self.status_text = status_text
        self.start_time = time.time()
        self.estimated_time = None
        self._update_display()
    
    def update(
        self,
        step: int,
        status_text: Optional[str] = None,
        estimated_time: Optional[float] = None
    ) -> None:
        """
        プログレスバーを更新
        
        Parameters:
        -----------
        step : int
            現在のステップ
        status_text : Optional[str], optional
            ステータステキスト
        estimated_time : Optional[float], optional
            推定残り時間（秒）
        """
        self.current_step = min(step, self.total_steps)
        if status_text:
            self.status_text = status_text
        if estimated_time is not None:
            self.estimated_time = estimated_time
        self._update_display()
    
    def increment(
        self,
        increment: int = 1,
        status_text: Optional[str] = None
    ) -> None:
        """
        プログレスバーを増分更新
        
        Parameters:
        -----------
        increment : int, optional
            増分値
        status_text : Optional[str], optional
            ステータステキスト
        """
        self.update(self.current_step + increment, status_text)
    
    def complete(self, status_text: str = "完了") -> None:
        """
        プログレスバーを完了
        
        Parameters:
        -----------
        status_text : str, optional
            完了時のステータステキスト
        """
        self.update(self.total_steps, status_text)
    
    def error(self, error_message: str) -> None:
        """
        エラー状態を表示
        
        Parameters:
        -----------
        error_message : str
            エラーメッセージ
        """
        self.status_text = f"エラー: {error_message}"
        self._update_display()
    
    def _update_display(self) -> None:
        """プログレスバーの表示を更新"""
        progress = self.current_step / self.total_steps
        
        # プログレスバーの表示
        st.progress(progress, text=self.status_text)
        
        # 推定残り時間の表示
        if self.estimated_time is not None:
            st.caption(f"推定残り時間: {self.estimated_time:.1f}秒")
        elif self.start_time is not None and self.current_step > 0:
            elapsed_time = time.time() - self.start_time
            if self.current_step < self.total_steps:
                estimated_remaining = (elapsed_time / self.current_step) * \
                    (self.total_steps - self.current_step)
                st.caption(f"推定残り時間: {estimated_remaining:.1f}秒")


def create_progress_bar(
    total_steps: int = 100,
    status_text: str = "処理中..."
) -> ProgressBar:
    """
    プログレスバーを作成
    
    Parameters:
    -----------
    total_steps : int, optional
        総ステップ数
    status_text : str, optional
        初期ステータステキスト
        
    Returns:
    --------
    ProgressBar
        プログレスバーオブジェクト
    """
    progress_bar = ProgressBar(total_steps)
    progress_bar.start(status_text)
    return progress_bar


def with_progress_bar(
    total_steps: int = 100,
    status_text: str = "処理中..."
):
    """
    プログレスバーデコレータ
    
    Parameters:
    -----------
    total_steps : int, optional
        総ステップ数
    status_text : str, optional
        初期ステータステキスト
        
    Returns:
    --------
    Callable
        デコレートされた関数
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            progress_bar = create_progress_bar(total_steps, status_text)
            
            # プログレス更新用のコールバック
            def update_progress(step: int, status: Optional[str] = None):
                progress_bar.update(step, status)
            
            # 関数にプログレス更新コールバックを渡す
            kwargs['progress_callback'] = update_progress
            
            try:
                result = func(*args, **kwargs)
                progress_bar.complete()
                return result
            except Exception as e:
                progress_bar.error(str(e))
                raise
        
        return wrapper
    return decorator


def show_task_progress(task_id: str) -> None:
    """
    非同期タスクの進捗を表示
    
    Parameters:
    -----------
    task_id : str
        タスクID
    """
    if 'async_task_manager' not in st.session_state:
        st.error("タスクマネージャーが初期化されていません")
        return
    
    task_manager = st.session_state.async_task_manager
    status = task_manager.get_task_status(task_id)
    
    if status["status"] == "running":
        st.progress(0.5, text="処理中...")
    elif status["status"] == "completed":
        st.progress(1.0, text="完了")
    elif status["status"] == "error":
        st.error(f"エラー: {status['error']}")
    else:
        st.warning("タスクが見つかりません") 