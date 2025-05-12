"""
分析パネルコンポーネント

分析結果の表示とインタラクティブな可視化を提供
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Dict, Optional, Union, Any
from datetime import datetime
import pandas as pd
import json
from services.analytics_service import AnalyticsService
from utils.export_utils import export_manager, render_export_ui


def init_analytics_state():
    """
    分析の状態を初期化
    """
    if 'analytics_service' not in st.session_state:
        st.session_state.analytics_service = AnalyticsService()


def plot_time_distribution(time_distribution: List[Dict]):
    """
    時間分布をプロット
    
    Parameters:
    -----------
    time_distribution : list[dict]
        時間分布データ
    """
    if not time_distribution:
        st.info("時間分布データがありません。")
        return
    
    df = pd.DataFrame(time_distribution)
    fig = px.bar(
        df,
        x='hour',
        y='count',
        title='時間帯別の質問数',
        labels={'hour': '時間', 'count': '質問数'},
        color='count',
        color_continuous_scale='Viridis'
    )
    
    fig.update_layout(
        xaxis=dict(tickmode='linear', tick0=0, dtick=1),
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)


def plot_response_times(response_times: List[float]):
    """
    応答時間の分布をプロット
    
    Parameters:
    -----------
    response_times : list[float]
        応答時間データ（秒）
    """
    if not response_times:
        st.info("応答時間データがありません。")
        return
    
    df = pd.DataFrame({'response_time': response_times})
    fig = px.histogram(
        df,
        x='response_time',
        title='応答時間の分布',
        labels={'response_time': '応答時間（秒）'},
        nbins=20
    )
    
    fig.update_layout(
        showlegend=False,
        xaxis_title='応答時間（秒）',
        yaxis_title='頻度'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def plot_session_stats(session_stats: Dict):
    """
    セッション統計をプロット
    
    Parameters:
    -----------
    session_stats : dict
        セッション統計データ
    """
    if not session_stats or not session_stats.get('session_details'):
        st.info("セッション統計データがありません。")
        return
    
    # セッション長の分布
    session_lengths = [s['length'] for s in session_stats['session_details']]
    df_lengths = pd.DataFrame({'length': session_lengths})
    
    fig1 = px.histogram(
        df_lengths,
        x='length',
        title='セッション長の分布',
        labels={'length': 'セッション長（質問数）'},
        nbins=10
    )
    
    st.plotly_chart(fig1, use_container_width=True)
    
    # セッションの時間分布
    session_times = [
        {
            'start_time': s['start_time'],
            'duration': (s['end_time'] - s['start_time']).total_seconds() / 60
        }
        for s in session_stats['session_details']
    ]
    
    df_times = pd.DataFrame(session_times)
    df_times['hour'] = pd.to_datetime(df_times['start_time']).dt.hour
    
    fig2 = px.scatter(
        df_times,
        x='hour',
        y='duration',
        title='セッションの時間分布',
        labels={
            'hour': '開始時間（時）',
            'duration': 'セッション時間（分）'
        },
        size='duration',
        color='duration',
        color_continuous_scale='Viridis'
    )
    
    st.plotly_chart(fig2, use_container_width=True)


def plot_topic_evolution(topic_evolution: List[Dict]):
    """
    トピックの進化をプロット
    
    Parameters:
    -----------
    topic_evolution : list[dict]
        トピックの進化データ
    """
    if not topic_evolution:
        st.info("トピックの進化データがありません。")
        return
    
    # データの準備
    data = []
    for day_data in topic_evolution:
        date = datetime.fromisoformat(day_data['date']).date()
        for topic in day_data['topics']:
            data.append({
                'date': date,
                'term': topic['term'],
                'count': topic['count']
            })
    
    df = pd.DataFrame(data)
    
    # ヒートマップの作成
    pivot_df = df.pivot_table(
        values='count',
        index='term',
        columns='date',
        fill_value=0
    )
    
    fig = px.imshow(
        pivot_df,
        title='トピックの時系列変化',
        labels={'x': '日付', 'y': 'トピック', 'color': '出現回数'},
        color_continuous_scale='Viridis'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def plot_query_complexity(complexity: Dict[str, int]):
    """
    クエリの複雑さをプロット
    
    Parameters:
    -----------
    complexity : dict[str, int]
        クエリの複雑さデータ
    """
    if not complexity:
        st.info("クエリの複雑さデータがありません。")
        return
    
    fig = px.pie(
        values=[complexity['simple'], complexity['complex']],
        names=['単純なクエリ', '複雑なクエリ'],
        title='クエリの複雑さの分布',
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    st.plotly_chart(fig, use_container_width=True)


def plot_source_types(source_types: Dict[str, int]):
    """
    ソースタイプの分布をプロット
    
    Parameters:
    -----------
    source_types : dict[str, int]
        ソースタイプの分布データ
    """
    if not source_types:
        st.info("ソースタイプのデータがありません。")
        return
    
    fig = px.pie(
        values=list(source_types.values()),
        names=list(source_types.keys()),
        title='参照ソースの分布',
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    st.plotly_chart(fig, use_container_width=True)


def plot_query_categories(categories: Dict[str, int]):
    """
    クエリカテゴリの分布をプロット
    
    Parameters:
    -----------
    categories : dict[str, int]
        カテゴリ分布データ
    """
    if not categories:
        st.info("カテゴリデータがありません。")
        return
    
    fig = px.bar(
        x=list(categories.keys()),
        y=list(categories.values()),
        title='質問カテゴリの分布',
        labels={'x': 'カテゴリ', 'y': '質問数'},
        color=list(categories.values()),
        color_continuous_scale='Viridis'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def plot_source_effectiveness(effectiveness: Dict[str, Dict]):
    """
    ソースの有効性をプロット
    
    Parameters:
    -----------
    effectiveness : dict[str, dict]
        ソースの有効性データ
    """
    if not effectiveness:
        st.info("有効性データがありません。")
        return
    
    data = []
    for source_type, stats in effectiveness.items():
        data.append({
            'source_type': source_type,
            'effectiveness': stats['effectiveness'] * 100,
            'total': stats['total']
        })
    
    df = pd.DataFrame(data)
    fig = px.bar(
        df,
        x='source_type',
        y='effectiveness',
        title='ソースタイプ別の有効性',
        labels={'source_type': 'ソースタイプ', 'effectiveness': '有効性 (%)'},
        color='total',
        color_continuous_scale='Viridis',
        text_auto='.1f'
    )
    
    fig.update_traces(texttemplate='%{text}%', textposition='outside')
    st.plotly_chart(fig, use_container_width=True)


def display_trending_topics(trending: List[Dict]):
    """
    トレンドトピックを表示
    
    Parameters:
    -----------
    trending : list[dict]
        トレンドトピックデータ
    """
    if not trending:
        st.info("トレンドデータがありません。")
        return
    
    st.subheader("📈 トレンドトピック")
    
    for topic in trending:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.write(topic['topic'])
        with col2:
            st.write(f"出現回数: {topic['count']}")
        with col3:
            if topic['trend'] == 'up':
                st.write("📈")
            else:
                st.write("➡️")


def render_analytics_panel(chat_history: List[Dict]) -> None:
    """
    分析パネルを表示
    
    Parameters:
    -----------
    chat_history : List[Dict]
        チャット履歴
    """
    init_analytics_state()
    analytics_service = st.session_state.analytics_service
    
    # 分析データの取得
    analytics_data = analytics_service.analyze_chat_history(chat_history)
    
    # 分析結果の表示
    st.subheader("分析結果")
    
    # 時間分布
    st.write("### 時間分布")
    plot_time_distribution(analytics_data.get('time_distribution', []))
    
    # 応答時間
    st.write("### 応答時間")
    plot_response_times(analytics_data.get('response_times', []))
    
    # セッション統計
    st.write("### セッション統計")
    plot_session_stats(analytics_data.get('session_stats', {}))
    
    # トピックの進化
    st.write("### トピックの進化")
    plot_topic_evolution(analytics_data.get('topic_evolution', []))
    
    # クエリの複雑さ
    st.write("### クエリの複雑さ")
    plot_query_complexity(analytics_data.get('query_complexity', {}))
    
    # ソースタイプ
    st.write("### ソースタイプ")
    plot_source_types(analytics_data.get('source_types', {}))
    
    # クエリカテゴリ
    st.write("### クエリカテゴリ")
    plot_query_categories(analytics_data.get('query_categories', {}))
    
    # ソースの有効性
    st.write("### ソースの有効性")
    plot_source_effectiveness(analytics_data.get('source_effectiveness', {}))
    
    # トレンドトピック
    st.write("### トレンドトピック")
    display_trending_topics(analytics_data.get('trending_topics', []))
    
    # エクスポートセクション
    st.write("### 分析結果のエクスポート")
    render_analytics_export(analytics_data)


def render_analytics_export(analytics_data: Dict[str, Any]) -> None:
    """
    分析結果のエクスポートUIを表示
    
    Parameters:
    -----------
    analytics_data : Dict[str, Any]
        分析結果データ
    """
    if not analytics_data:
        st.warning("エクスポートする分析結果がありません")
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
        title="分析結果のエクスポート",
        default_filename=f"analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        metadata={
            'export_type': 'analytics',
            'data_types': list(analytics_data.keys()),
            'export_timestamp': datetime.now().isoformat()
        }
    ) 