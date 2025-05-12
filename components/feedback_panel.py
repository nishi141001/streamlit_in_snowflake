"""
フィードバックパネルコンポーネント

回答品質の評価
ユーザーフィードバックの収集
フィードバック分析
"""

import streamlit as st
from typing import Dict, List, Optional, Callable, Union, Any
import pandas as pd
from datetime import datetime
import json
from utils.export_utils import export_manager, render_export_ui


class FeedbackManager:
    """フィードバック管理クラス"""
    
    def __init__(self):
        """初期化"""
        if 'feedback_data' not in st.session_state:
            st.session_state.feedback_data = []
    
    def add_feedback(
        self,
        question: str,
        answer: str,
        rating: int,
        comment: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        フィードバックを追加
        
        Parameters:
        -----------
        question : str
            質問内容
        answer : str
            回答内容
        rating : int
            評価（1-5）
        comment : Optional[str], optional
            コメント
        metadata : Optional[Dict], optional
            メタデータ
        """
        feedback = {
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'answer': answer,
            'rating': rating,
            'comment': comment,
            'metadata': metadata or {}
        }
        st.session_state.feedback_data.append(feedback)
    
    def get_feedback_data(self) -> List[Dict]:
        """
        フィードバックデータを取得
        
        Returns:
        --------
        List[Dict]
            フィードバックデータのリスト
        """
        return st.session_state.feedback_data
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """
        フィードバック統計を取得
        
        Returns:
        --------
        Dict[str, Any]
            フィードバック統計
        """
        if not st.session_state.feedback_data:
            return {
                'total_feedback': 0,
                'average_rating': 0,
                'rating_distribution': {},
                'recent_feedback': []
            }
        
        df = pd.DataFrame(st.session_state.feedback_data)
        
        # 評価の分布
        rating_dist = df['rating'].value_counts().to_dict()
        
        # 平均評価
        avg_rating = df['rating'].mean()
        
        # 最近のフィードバック
        recent = df.sort_values('timestamp', ascending=False).head(5).to_dict('records')
        
        return {
            'total_feedback': len(df),
            'average_rating': round(avg_rating, 1),
            'rating_distribution': rating_dist,
            'recent_feedback': recent
        }
    
    def export_feedback(
        self,
        format: str = 'json',
        filename: Optional[str] = None
    ) -> None:
        """
        フィードバックをエクスポート
        
        Parameters:
        -----------
        format : str, optional
            エクスポート形式（'json', 'csv', 'excel'）
        filename : Optional[str], optional
            ファイル名
        """
        feedback_data = self.get_feedback_data()
        if not feedback_data:
            st.warning("エクスポートするフィードバックがありません")
            return
        
        # エクスポートUIの表示
        render_export_ui(
            data=feedback_data,
            title="フィードバックのエクスポート",
            default_filename=filename or f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}",
            metadata={
                'export_type': 'feedback',
                'feedback_count': len(feedback_data),
                'export_timestamp': datetime.now().isoformat()
            }
        )


def render_feedback_panel(
    question: str,
    answer: str,
    on_submit: Optional[callable] = None
) -> None:
    """
    フィードバックパネルを表示
    
    Parameters:
    -----------
    question : str
        質問内容
    answer : str
        回答内容
    on_submit : Optional[callable], optional
        送信時のコールバック関数
    """
    feedback_manager = FeedbackManager()
    
    st.subheader("フィードバック")
    
    # 評価スライダー
    rating = st.slider(
        "評価",
        min_value=1,
        max_value=5,
        value=3,
        step=1,
        format="%d 星"
    )
    
    # コメント入力
    comment = st.text_area(
        "コメント（任意）",
        height=100
    )
    
    # 送信ボタン
    if st.button("フィードバックを送信"):
        feedback_manager.add_feedback(
            question=question,
            answer=answer,
            rating=rating,
            comment=comment if comment else None,
            metadata={
                'page': st.session_state.get('current_page', ''),
                'session_id': st.session_state.get('session_id', '')
            }
        )
        
        if on_submit:
            on_submit(rating, comment)
        
        st.success("フィードバックを送信しました")


def render_feedback_stats() -> None:
    """フィードバック統計を表示"""
    feedback_manager = FeedbackManager()
    stats = feedback_manager.get_feedback_stats()
    
    if stats['total_feedback'] == 0:
        st.info("フィードバックがまだありません")
        return
    
    st.subheader("フィードバック統計")
    
    # 統計情報の表示
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            "総フィードバック数",
            stats['total_feedback']
        )
        st.metric(
            "平均評価",
            f"{stats['average_rating']} 星"
        )
    
    with col2:
        st.write("評価の分布")
        for rating, count in sorted(stats['rating_distribution'].items()):
            st.progress(
                count / stats['total_feedback'],
                text=f"{rating} 星: {count}件"
            )
    
    # 最近のフィードバック
    st.write("最近のフィードバック")
    for feedback in stats['recent_feedback']:
        with st.expander(
            f"{datetime.fromisoformat(feedback['timestamp']).strftime('%Y-%m-%d %H:%M:%S')} - {feedback['rating']}星"
        ):
            st.write(f"**質問:** {feedback['question']}")
            st.write(f"**回答:** {feedback['answer']}")
            if feedback['comment']:
                st.write(f"**コメント:** {feedback['comment']}")
    
    # エクスポートセクション
    st.subheader("フィードバックのエクスポート")
    feedback_manager.export_feedback() 