"""
可視化サービス

データの可視化
グラフ生成
レポート作成
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional, Union, Tuple, Any
import numpy as np
from datetime import datetime, timedelta
import json
from utils.export_utils import export_manager, render_export_ui


class VisualizationService:
    """可視化サービス"""
    
    def __init__(self):
        """初期化"""
        # デフォルトのカラーパレット
        self.color_palette = px.colors.qualitative.Set3
    
    def create_time_series(
        self,
        data: pd.DataFrame,
        date_column: str,
        value_column: str,
        title: str,
        group_column: Optional[str] = None,
        aggregation: str = 'sum',
        interval: str = 'D'
    ) -> go.Figure:
        """
        時系列グラフを作成
        
        Parameters:
        -----------
        data : pd.DataFrame
            データ
        date_column : str
            日付カラム名
        value_column : str
            値カラム名
        title : str
            グラフタイトル
        group_column : Optional[str], optional
            グループ化カラム名
        aggregation : str, optional
            集計方法（'sum', 'mean', 'count'）
        interval : str, optional
            時間間隔（'D': 日, 'W': 週, 'M': 月）
            
        Returns:
        --------
        go.Figure
            時系列グラフ
        """
        # 日付カラムをdatetime型に変換
        data[date_column] = pd.to_datetime(data[date_column])
        
        # データの集計
        if group_column:
            grouped_data = data.groupby([
                pd.Grouper(key=date_column, freq=interval),
                group_column
            ])[value_column].agg(aggregation).reset_index()
        else:
            grouped_data = data.groupby(
                pd.Grouper(key=date_column, freq=interval)
            )[value_column].agg(aggregation).reset_index()
        
        # グラフの作成
        if group_column:
            fig = px.line(
                grouped_data,
                x=date_column,
                y=value_column,
                color=group_column,
                title=title,
                color_discrete_sequence=self.color_palette
            )
        else:
            fig = px.line(
                grouped_data,
                x=date_column,
                y=value_column,
                title=title,
                color_discrete_sequence=self.color_palette
            )
        
        # レイアウトの設定
        fig.update_layout(
            xaxis_title="日付",
            yaxis_title=value_column,
            hovermode="x unified",
            showlegend=True,
            legend_title=group_column if group_column else None
        )
        
        return fig
    
    def create_bar_chart(
        self,
        data: pd.DataFrame,
        x_column: str,
        y_column: str,
        title: str,
        group_column: Optional[str] = None,
        orientation: str = 'v',
        aggregation: str = 'sum'
    ) -> go.Figure:
        """
        棒グラフを作成
        
        Parameters:
        -----------
        data : pd.DataFrame
            データ
        x_column : str
            X軸カラム名
        y_column : str
            Y軸カラム名
        title : str
            グラフタイトル
        group_column : Optional[str], optional
            グループ化カラム名
        orientation : str, optional
            グラフの向き（'v': 縦, 'h': 横）
        aggregation : str, optional
            集計方法（'sum', 'mean', 'count'）
            
        Returns:
        --------
        go.Figure
            棒グラフ
        """
        # データの集計
        if group_column:
            grouped_data = data.groupby([x_column, group_column])[y_column].agg(
                aggregation
            ).reset_index()
        else:
            grouped_data = data.groupby(x_column)[y_column].agg(
                aggregation
            ).reset_index()
        
        # グラフの作成
        if group_column:
            fig = px.bar(
                grouped_data,
                x=x_column,
                y=y_column,
                color=group_column,
                title=title,
                orientation=orientation,
                color_discrete_sequence=self.color_palette
            )
        else:
            fig = px.bar(
                grouped_data,
                x=x_column,
                y=y_column,
                title=title,
                orientation=orientation,
                color_discrete_sequence=self.color_palette
            )
        
        # レイアウトの設定
        fig.update_layout(
            xaxis_title=x_column,
            yaxis_title=y_column,
            hovermode="x unified",
            showlegend=True,
            legend_title=group_column if group_column else None
        )
        
        return fig
    
    def create_pie_chart(
        self,
        data: pd.DataFrame,
        names_column: str,
        values_column: str,
        title: str,
        hole: float = 0.0
    ) -> go.Figure:
        """
        円グラフを作成
        
        Parameters:
        -----------
        data : pd.DataFrame
            データ
        names_column : str
            カテゴリ名カラム
        values_column : str
            値カラム
        title : str
            グラフタイトル
        hole : float, optional
            中心の穴の大きさ（0.0-1.0）
            
        Returns:
        --------
        go.Figure
            円グラフ
        """
        # データの集計
        grouped_data = data.groupby(names_column)[values_column].sum().reset_index()
        
        # グラフの作成
        fig = px.pie(
            grouped_data,
            names=names_column,
            values=values_column,
            title=title,
            hole=hole,
            color_discrete_sequence=self.color_palette
        )
        
        # レイアウトの設定
        fig.update_layout(
            showlegend=True,
            legend_title=names_column
        )
        
        return fig
    
    def create_heatmap(
        self,
        data: pd.DataFrame,
        x_column: str,
        y_column: str,
        value_column: str,
        title: str,
        aggregation: str = 'sum'
    ) -> go.Figure:
        """
        ヒートマップを作成
        
        Parameters:
        -----------
        data : pd.DataFrame
            データ
        x_column : str
            X軸カラム名
        y_column : str
            Y軸カラム名
        value_column : str
            値カラム名
        title : str
            グラフタイトル
        aggregation : str, optional
            集計方法（'sum', 'mean', 'count'）
            
        Returns:
        --------
        go.Figure
            ヒートマップ
        """
        # データの集計
        pivot_data = data.pivot_table(
            values=value_column,
            index=y_column,
            columns=x_column,
            aggfunc=aggregation
        ).fillna(0)
        
        # グラフの作成
        fig = px.imshow(
            pivot_data,
            title=title,
            color_continuous_scale='Viridis'
        )
        
        # レイアウトの設定
        fig.update_layout(
            xaxis_title=x_column,
            yaxis_title=y_column,
            coloraxis_colorbar_title=value_column
        )
        
        return fig
    
    def create_scatter_plot(
        self,
        data: pd.DataFrame,
        x_column: str,
        y_column: str,
        title: str,
        color_column: Optional[str] = None,
        size_column: Optional[str] = None,
        hover_columns: Optional[List[str]] = None
    ) -> go.Figure:
        """
        散布図を作成
        
        Parameters:
        -----------
        data : pd.DataFrame
            データ
        x_column : str
            X軸カラム名
        y_column : str
            Y軸カラム名
        title : str
            グラフタイトル
        color_column : Optional[str], optional
            色分けカラム名
        size_column : Optional[str], optional
            サイズカラム名
        hover_columns : Optional[List[str]], optional
            ホバー表示カラム名のリスト
            
        Returns:
        --------
        go.Figure
            散布図
        """
        # グラフの作成
        fig = px.scatter(
            data,
            x=x_column,
            y=y_column,
            color=color_column,
            size=size_column,
            hover_data=hover_columns,
            title=title,
            color_discrete_sequence=self.color_palette
        )
        
        # レイアウトの設定
        fig.update_layout(
            xaxis_title=x_column,
            yaxis_title=y_column,
            hovermode="closest",
            showlegend=True,
            legend_title=color_column if color_column else None
        )
        
        return fig
    
    def create_dashboard(
        self,
        data: pd.DataFrame,
        config: Dict
    ) -> List[go.Figure]:
        """
        ダッシュボードを作成
        
        Parameters:
        -----------
        data : pd.DataFrame
            データ
        config : Dict
            ダッシュボード設定
            
        Returns:
        --------
        List[go.Figure]
            グラフのリスト
        """
        figures = []
        
        for chart_config in config['charts']:
            chart_type = chart_config['type']
            
            if chart_type == 'time_series':
                fig = self.create_time_series(
                    data=data,
                    date_column=chart_config['date_column'],
                    value_column=chart_config['value_column'],
                    title=chart_config['title'],
                    group_column=chart_config.get('group_column'),
                    aggregation=chart_config.get('aggregation', 'sum'),
                    interval=chart_config.get('interval', 'D')
                )
            
            elif chart_type == 'bar_chart':
                fig = self.create_bar_chart(
                    data=data,
                    x_column=chart_config['x_column'],
                    y_column=chart_config['y_column'],
                    title=chart_config['title'],
                    group_column=chart_config.get('group_column'),
                    orientation=chart_config.get('orientation', 'v'),
                    aggregation=chart_config.get('aggregation', 'sum')
                )
            
            elif chart_type == 'pie_chart':
                fig = self.create_pie_chart(
                    data=data,
                    names_column=chart_config['names_column'],
                    values_column=chart_config['values_column'],
                    title=chart_config['title'],
                    hole=chart_config.get('hole', 0.0)
                )
            
            elif chart_type == 'heatmap':
                fig = self.create_heatmap(
                    data=data,
                    x_column=chart_config['x_column'],
                    y_column=chart_config['y_column'],
                    value_column=chart_config['value_column'],
                    title=chart_config['title'],
                    aggregation=chart_config.get('aggregation', 'sum')
                )
            
            elif chart_type == 'scatter_plot':
                fig = self.create_scatter_plot(
                    data=data,
                    x_column=chart_config['x_column'],
                    y_column=chart_config['y_column'],
                    title=chart_config['title'],
                    color_column=chart_config.get('color_column'),
                    size_column=chart_config.get('size_column'),
                    hover_columns=chart_config.get('hover_columns')
                )
            
            figures.append(fig)
        
        return figures
    
    def export_dashboard(
        self,
        dashboard_data: Dict[str, Any],
        format: str = 'json',
        filename: Optional[str] = None
    ) -> None:
        """
        ダッシュボードデータをエクスポート
        
        Parameters:
        -----------
        dashboard_data : Dict[str, Any]
            エクスポートするダッシュボードデータ
        format : str, optional
            エクスポート形式（'json', 'csv', 'excel'）
        filename : Optional[str], optional
            ファイル名
        """
        if not dashboard_data:
            st.warning("エクスポートするダッシュボードデータがありません")
            return
        
        # データの準備
        export_data = {}
        for key, value in dashboard_data.items():
            if isinstance(value, (list, dict)):
                export_data[key] = value
            elif isinstance(value, pd.DataFrame):
                export_data[key] = value.to_dict(orient='records')
            elif isinstance(value, (go.Figure, px.Figure)):
                export_data[key] = value.to_json()
            else:
                export_data[key] = str(value)
        
        # エクスポートUIの表示
        render_export_ui(
            data=export_data,
            title="ダッシュボードのエクスポート",
            default_filename=filename or f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}",
            metadata={
                'export_type': 'dashboard',
                'data_types': list(dashboard_data.keys()),
                'export_timestamp': datetime.now().isoformat()
            }
        )
    
    def export_visualization(
        self,
        figure: Union[go.Figure, px.Figure],
        format: str = 'json',
        filename: Optional[str] = None
    ) -> None:
        """
        可視化データをエクスポート
        
        Parameters:
        -----------
        figure : Union[go.Figure, px.Figure]
            エクスポートする可視化データ
        format : str, optional
            エクスポート形式（'json', 'html', 'png'）
        filename : Optional[str], optional
            ファイル名
        """
        if not figure:
            st.warning("エクスポートする可視化データがありません")
            return
        
        # データの準備
        if format == 'json':
            content = figure.to_json()
            mime_type = 'application/json'
        elif format == 'html':
            content = figure.to_html(include_plotlyjs='cdn')
            mime_type = 'text/html'
        elif format == 'png':
            content = figure.to_image(format='png')
            mime_type = 'image/png'
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # エクスポートUIの表示
        render_export_ui(
            data=content,
            title="可視化データのエクスポート",
            default_filename=filename or f"visualization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}",
            metadata={
                'export_type': 'visualization',
                'format': format,
                'export_timestamp': datetime.now().isoformat()
            }
        ) 