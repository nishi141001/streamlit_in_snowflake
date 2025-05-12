"""
非同期処理ユーティリティ

長時間実行処理のバックグラウンド実行
プログレスバー管理
パラレル処理制御
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Dict, List
import streamlit as st
from functools import wraps
import time


class AsyncTaskManager:
    """非同期タスク管理クラス"""
    
    def __init__(self, max_workers: int = 4):
        """
        初期化
        
        Parameters:
        -----------
        max_workers : int, optional
            最大ワーカー数（デフォルト: 4）
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, Any] = {}
        self.progress_bars: Dict[str, st.progress] = {}
    
    def run_task(
        self,
        task_id: str,
        func: Callable,
        *args,
        total_steps: int = 100,
        **kwargs
    ) -> None:
        """
        タスクを非同期で実行
        
        Parameters:
        -----------
        task_id : str
            タスクID
        func : Callable
            実行する関数
        total_steps : int, optional
            総ステップ数
        *args, **kwargs
            関数に渡す引数
        """
        if task_id in self.tasks:
            raise ValueError(f"Task {task_id} is already running")
        
        # プログレスバーの作成
        progress_bar = st.progress(0)
        self.progress_bars[task_id] = progress_bar
        
        # タスクの実行
        future = self.executor.submit(self._run_with_progress, task_id, func, total_steps, *args, **kwargs)
        self.tasks[task_id] = future
    
    def _run_with_progress(
        self,
        task_id: str,
        func: Callable,
        total_steps: int,
        *args,
        **kwargs
    ) -> Any:
        """
        プログレスバー付きでタスクを実行
        
        Parameters:
        -----------
        task_id : str
            タスクID
        func : Callable
            実行する関数
        total_steps : int
            総ステップ数
        *args, **kwargs
            関数に渡す引数
            
        Returns:
        --------
        Any
            関数の実行結果
        """
        try:
            # プログレス更新用のコールバック
            def update_progress(step: int, total: int = total_steps):
                progress = step / total
                self.progress_bars[task_id].progress(progress)
            
            # 関数にプログレス更新コールバックを渡す
            kwargs['progress_callback'] = update_progress
            result = func(*args, **kwargs)
            
            # 完了時にプログレスバーを100%に
            self.progress_bars[task_id].progress(1.0)
            return result
            
        except Exception as e:
            # エラー時にプログレスバーを赤色に
            self.progress_bars[task_id].progress(1.0, text="エラーが発生しました")
            raise e
        finally:
            # タスク完了後のクリーンアップ
            self._cleanup_task(task_id)
    
    def _cleanup_task(self, task_id: str) -> None:
        """
        タスクのクリーンアップ
        
        Parameters:
        -----------
        task_id : str
            タスクID
        """
        if task_id in self.tasks:
            del self.tasks[task_id]
        if task_id in self.progress_bars:
            del self.progress_bars[task_id]
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        タスクの状態を取得
        
        Parameters:
        -----------
        task_id : str
            タスクID
            
        Returns:
        --------
        Dict[str, Any]
            タスクの状態情報
        """
        if task_id not in self.tasks:
            return {"status": "not_found"}
        
        future = self.tasks[task_id]
        if future.done():
            try:
                result = future.result()
                return {
                    "status": "completed",
                    "result": result
                }
            except Exception as e:
                return {
                    "status": "error",
                    "error": str(e)
                }
        else:
            return {"status": "running"}
    
    def cancel_task(self, task_id: str) -> bool:
        """
        タスクをキャンセル
        
        Parameters:
        -----------
        task_id : str
            タスクID
            
        Returns:
        --------
        bool
            キャンセル成功時はTrue
        """
        if task_id in self.tasks:
            future = self.tasks[task_id]
            if not future.done():
                future.cancel()
                self._cleanup_task(task_id)
                return True
        return False


def async_task(total_steps: int = 100):
    """
    非同期タスクデコレータ
    
    Parameters:
    -----------
    total_steps : int, optional
        総ステップ数
        
    Returns:
    --------
    Callable
        デコレートされた関数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # セッション状態からタスクマネージャーを取得
            if 'async_task_manager' not in st.session_state:
                st.session_state.async_task_manager = AsyncTaskManager()
            
            task_manager = st.session_state.async_task_manager
            task_id = f"{func.__name__}_{int(time.time())}"
            
            # タスクを実行
            task_manager.run_task(
                task_id,
                func,
                *args,
                total_steps=total_steps,
                **kwargs
            )
            
            return task_id
        
        return wrapper
    return decorator


def parallel_process(items: List[Any], func: Callable, max_workers: int = 4) -> List[Any]:
    """
    アイテムを並列処理
    
    Parameters:
    -----------
    items : List[Any]
        処理するアイテムのリスト
    func : Callable
        各アイテムに適用する関数
    max_workers : int, optional
        最大ワーカー数
        
    Returns:
    --------
    List[Any]
        処理結果のリスト
    """
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(func, item) for item in items]
        return [future.result() for future in futures] 