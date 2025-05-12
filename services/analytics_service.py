"""
分析サービス

PDFの使用状況、検索パターン、会話分析などの機能を提供
"""

import streamlit as st
from typing import List, Dict, Optional, Union, Any
from datetime import datetime, timedelta
import pandas as pd
from collections import Counter
from snowflake.snowpark.context import get_active_session
from config import SETTINGS
from utils.export_utils import export_manager, render_export_ui


class AnalyticsService:
    def __init__(self):
        self.session = get_active_session()
        self.model = SETTINGS["MODEL_CHAT"]
    
    def analyze_usage_patterns(self, chat_history: List[Dict]) -> Dict:
        """
        使用パターンを分析
        
        Parameters:
        -----------
        chat_history : list[dict]
            チャット履歴
            
        Returns:
        --------
        dict
            分析結果
        """
        if not chat_history:
            return {
                'total_queries': 0,
                'avg_query_length': 0,
                'time_distribution': [],
                'source_types': {},
                'feedback_stats': {'likes': 0, 'dislikes': 0},
                'response_times': [],
                'session_stats': {'total_sessions': 0, 'avg_session_length': 0}
            }
        
        # 基本統計
        queries = [h['query'] for h in chat_history if 'query' in h]
        total_queries = len(queries)
        avg_query_length = sum(len(q) for q in queries) / total_queries if total_queries > 0 else 0
        
        # 時間分布
        timestamps = [datetime.fromisoformat(h['timestamp']) for h in chat_history]
        time_distribution = []
        for i in range(0, 24, 1):
            hour_count = sum(1 for ts in timestamps if ts.hour == i)
            time_distribution.append({
                'hour': i,
                'count': hour_count
            })
        
        # ソースタイプの分布
        source_types = Counter()
        for h in chat_history:
            if 'sources' in h:
                for source in h['sources']:
                    source_types[source.get('type', 'text')] += 1
        
        # フィードバック統計
        feedback_stats = {
            'likes': sum(1 for h in chat_history if h.get('feedback') == 'like'),
            'dislikes': sum(1 for h in chat_history if h.get('feedback') == 'dislike')
        }
        
        # 応答時間の分析
        response_times = []
        for i in range(1, len(chat_history), 2):
            if i < len(chat_history) and 'timestamp' in chat_history[i-1] and 'timestamp' in chat_history[i]:
                query_time = datetime.fromisoformat(chat_history[i-1]['timestamp'])
                response_time = datetime.fromisoformat(chat_history[i]['timestamp'])
                response_times.append((response_time - query_time).total_seconds())
        
        # セッション統計
        sessions = self._analyze_sessions(chat_history)
        
        return {
            'total_queries': total_queries,
            'avg_query_length': avg_query_length,
            'time_distribution': time_distribution,
            'source_types': dict(source_types),
            'feedback_stats': feedback_stats,
            'response_times': response_times,
            'session_stats': sessions
        }
    
    def _analyze_sessions(self, chat_history: List[Dict]) -> Dict:
        """
        セッション分析
        
        Parameters:
        -----------
        chat_history : list[dict]
            チャット履歴
            
        Returns:
        --------
        dict
            セッション統計
        """
        if not chat_history:
            return {'total_sessions': 0, 'avg_session_length': 0}
        
        # セッションの分割（30分以上の間隔で新しいセッションとみなす）
        sessions = []
        current_session = []
        last_timestamp = None
        
        for entry in chat_history:
            if 'timestamp' not in entry:
                continue
                
            current_time = datetime.fromisoformat(entry['timestamp'])
            
            if last_timestamp is None:
                current_session.append(entry)
            else:
                time_diff = (current_time - last_timestamp).total_seconds()
                if time_diff > 1800:  # 30分
                    if current_session:
                        sessions.append(current_session)
                    current_session = [entry]
                else:
                    current_session.append(entry)
            
            last_timestamp = current_time
        
        if current_session:
            sessions.append(current_session)
        
        # セッション統計の計算
        total_sessions = len(sessions)
        session_lengths = [len(s) for s in sessions]
        avg_session_length = sum(session_lengths) / total_sessions if total_sessions > 0 else 0
        
        return {
            'total_sessions': total_sessions,
            'avg_session_length': avg_session_length,
            'session_details': [
                {
                    'start_time': datetime.fromisoformat(s[0]['timestamp']),
                    'end_time': datetime.fromisoformat(s[-1]['timestamp']),
                    'length': len(s),
                    'queries': [e['query'] for e in s if 'query' in e]
                }
                for s in sessions
            ]
        }
    
    def analyze_search_patterns(self, chat_history: List[Dict]) -> Dict:
        """
        検索パターンを分析
        
        Parameters:
        -----------
        chat_history : list[dict]
            チャット履歴
            
        Returns:
        --------
        dict
            分析結果
        """
        if not chat_history:
            return {
                'common_terms': [],
                'query_categories': {},
                'source_effectiveness': {},
                'query_complexity': {'simple': 0, 'complex': 0},
                'topic_evolution': []
            }
        
        # 頻出単語の抽出
        all_queries = ' '.join(h['query'] for h in chat_history if 'query' in h)
        words = [w for w in all_queries.split() if len(w) > 1]
        common_terms = Counter(words).most_common(10)
        
        # クエリのカテゴリ分類
        categories = {
            '要約': ['要約', 'まとめ', '概要'],
            '詳細': ['詳細', '詳しく', '説明'],
            '比較': ['比較', '違い', '対比'],
            '数値': ['数値', '数字', '統計'],
            'その他': []
        }
        
        query_categories = {cat: 0 for cat in categories}
        queries = [h['query'] for h in chat_history if 'query' in h]
        
        # クエリの複雑さ分析
        query_complexity = {'simple': 0, 'complex': 0}
        for query in queries:
            words = query.split()
            if len(words) <= 5:
                query_complexity['simple'] += 1
            else:
                query_complexity['complex'] += 1
            
            categorized = False
            for cat, keywords in categories.items():
                if any(kw in query for kw in keywords):
                    query_categories[cat] += 1
                    categorized = True
                    break
            if not categorized:
                query_categories['その他'] += 1
        
        # ソースの有効性分析
        source_effectiveness = {}
        for h in chat_history:
            if 'sources' in h and 'feedback' in h:
                for source in h['sources']:
                    source_type = source.get('type', 'text')
                    if source_type not in source_effectiveness:
                        source_effectiveness[source_type] = {'likes': 0, 'total': 0}
                    source_effectiveness[source_type]['total'] += 1
                    if h['feedback'] == 'like':
                        source_effectiveness[source_type]['likes'] += 1
        
        # 有効性スコアの計算
        for source_type in source_effectiveness:
            stats = source_effectiveness[source_type]
            stats['effectiveness'] = stats['likes'] / stats['total'] if stats['total'] > 0 else 0
        
        # トピックの進化分析
        topic_evolution = self._analyze_topic_evolution(chat_history)
        
        return {
            'common_terms': common_terms,
            'query_categories': query_categories,
            'source_effectiveness': source_effectiveness,
            'query_complexity': query_complexity,
            'topic_evolution': topic_evolution
        }
    
    def _analyze_topic_evolution(self, chat_history: List[Dict]) -> List[Dict]:
        """
        トピックの進化を分析
        
        Parameters:
        -----------
        chat_history : list[dict]
            チャット履歴
            
        Returns:
        --------
        list[dict]
            トピックの進化データ
        """
        if not chat_history:
            return []
        
        # 時間枠で分割（1日ごと）
        time_windows = {}
        for entry in chat_history:
            if 'query' not in entry:
                continue
                
            timestamp = datetime.fromisoformat(entry['timestamp'])
            date_key = timestamp.date()
            
            if date_key not in time_windows:
                time_windows[date_key] = []
            time_windows[date_key].append(entry['query'])
        
        # 各時間枠のトピックを抽出
        evolution = []
        for date, queries in sorted(time_windows.items()):
            # その日の頻出単語を抽出
            all_words = ' '.join(queries).split()
            topics = Counter(w for w in all_words if len(w) > 1).most_common(3)
            
            evolution.append({
                'date': date.isoformat(),
                'topics': [{'term': term, 'count': count} for term, count in topics],
                'query_count': len(queries)
            })
        
        return evolution
    
    def generate_usage_report(self, chat_history: List[Dict], report_type: str = 'summary') -> str:
        """
        使用状況レポートを生成
        
        Parameters:
        -----------
        chat_history : list[dict]
            チャット履歴
        report_type : str, optional
            レポートタイプ（'summary' or 'detailed'）
            
        Returns:
        --------
        str
            レポート内容
        """
        usage_patterns = self.analyze_usage_patterns(chat_history)
        search_patterns = self.analyze_search_patterns(chat_history)
        
        try:
            # レポート用のプロンプトを構築
            prompt = f"""
            以下の分析データに基づいて、PDFの使用状況に関する{'詳細な' if report_type == 'detailed' else '簡潔な'}レポートを生成してください。
            
            基本統計:
            - 総質問数: {usage_patterns['total_queries']}
            - 平均質問長: {usage_patterns['avg_query_length']:.1f}文字
            - 総セッション数: {usage_patterns['session_stats']['total_sessions']}
            - 平均セッション長: {usage_patterns['session_stats']['avg_session_length']:.1f}質問
            
            検索パターン:
            - 主要な検索語: {', '.join(term for term, _ in search_patterns['common_terms'])}
            - カテゴリ分布: {', '.join(f'{cat}: {count}' for cat, count in search_patterns['query_categories'].items())}
            - クエリの複雑さ: 単純 {search_patterns['query_complexity']['simple']} / 複雑 {search_patterns['query_complexity']['complex']}
            
            フィードバック:
            - 良い評価: {usage_patterns['feedback_stats']['likes']}
            - 改善要望: {usage_patterns['feedback_stats']['dislikes']}
            
            レポートは以下の点を含めてください：
            1. 使用状況の概要
            2. 主要な検索パターン
            3. セッション分析
            4. トピックの進化
            5. 改善提案
            """
            
            # レポートを生成
            report = self.session.cortex.complete(
                model=self.model,
                prompt=prompt,
                temperature=0.3,
                max_tokens=1000 if report_type == 'detailed' else 500
            )
            
            return report
            
        except Exception as e:
            print(f"レポート生成中にエラー: {str(e)}")
            return "レポートの生成中にエラーが発生しました。"
    
    def analyze_chat_history(self, chat_history: List[Dict]) -> Dict[str, Any]:
        """
        チャット履歴を分析
        
        Parameters:
        -----------
        chat_history : List[Dict]
            チャット履歴
            
        Returns:
        --------
        Dict[str, Any]
            分析結果
        """
        # 使用パターンの分析
        usage_patterns = self.analyze_usage_patterns(chat_history)
        
        # 検索パターンの分析
        search_patterns = self.analyze_search_patterns(chat_history)
        
        # 分析結果の統合
        analytics_data = {
            **usage_patterns,
            **search_patterns,
            'analyzed_at': datetime.now().isoformat()
        }
        
        return analytics_data
    
    def export_analytics_data(
        self,
        analytics_data: Dict[str, Any],
        format: str = 'json',
        filename: Optional[str] = None
    ) -> None:
        """
        分析データをエクスポート
        
        Parameters:
        -----------
        analytics_data : Dict[str, Any]
            エクスポートする分析データ
        format : str, optional
            エクスポート形式（'json', 'csv', 'excel'）
        filename : Optional[str], optional
            ファイル名
        """
        if not analytics_data:
            st.warning("エクスポートする分析データがありません")
            return
        
        # データの準備
        export_data = {}
        for key, value in analytics_data.items():
            if isinstance(value, (list, dict)):
                export_data[key] = value
            elif isinstance(value, pd.DataFrame):
                export_data[key] = value.to_dict(orient='records')
            else:
                export_data[key] = str(value)
        
        # エクスポートUIの表示
        render_export_ui(
            data=export_data,
            title="分析データのエクスポート",
            default_filename=filename or f"analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}",
            metadata={
                'export_type': 'analytics',
                'data_types': list(analytics_data.keys()),
                'export_timestamp': datetime.now().isoformat()
            }
        )

    def get_trending_topics(self, chat_history: List[Dict], days: int = 7) -> List[Dict]:
        """
        トレンドトピックを抽出
        
        Parameters:
        -----------
        chat_history : list[dict]
            チャット履歴
        days : int, optional
            分析期間（日数）
            
        Returns:
        --------
        list[dict]
            トレンドトピックのリスト
        """
        if not chat_history:
            return []
        
        # 指定期間内のデータを抽出
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_history = [
            h for h in chat_history
            if datetime.fromisoformat(h['timestamp']) > cutoff_date
        ]
        
        # トピックの抽出と集計
        topics = Counter()
        for h in recent_history:
            if 'query' in h:
                # 単語の抽出と重み付け
                words = [w for w in h['query'].split() if len(w) > 1]
                for word in words:
                    topics[word] += 1
        
        # トレンドトピックの生成
        trending = []
        for topic, count in topics.most_common(5):
            trending.append({
                'topic': topic,
                'count': count,
                'trend': 'up' if count > 3 else 'stable'
            })
        
        return trending 