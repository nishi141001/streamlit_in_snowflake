"""
エクスポートユーティリティ

データのエクスポート
フォーマット変換
エクスポート履歴管理
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
import json
import csv
import io
from pathlib import Path
import hashlib


class ExportManager:
    """エクスポート管理クラス"""
    
    def __init__(self):
        """初期化"""
        if 'export_history' not in st.session_state:
            st.session_state.export_history = []
    
    def export_data(
        self,
        data: Union[Dict, List, pd.DataFrame],
        format: str = 'json',
        filename: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        データをエクスポート
        
        Parameters:
        -----------
        data : Union[Dict, List, pd.DataFrame]
            エクスポートするデータ
        format : str, optional
            エクスポート形式（'json', 'csv', 'excel'）
        filename : Optional[str], optional
            ファイル名
        metadata : Optional[Dict], optional
            メタデータ
            
        Returns:
        --------
        Dict[str, Any]
            エクスポート情報
        """
        # ファイル名の生成
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"export_{timestamp}.{format}"
        
        # データの変換
        if format == 'json':
            if isinstance(data, pd.DataFrame):
                export_data = data.to_dict(orient='records')
            else:
                export_data = data
            content = json.dumps(export_data, ensure_ascii=False, indent=2)
            mime_type = 'application/json'
        
        elif format == 'csv':
            if isinstance(data, pd.DataFrame):
                buffer = io.StringIO()
                data.to_csv(buffer, index=False, encoding='utf-8-sig')
                content = buffer.getvalue()
            else:
                df = pd.DataFrame(data)
                buffer = io.StringIO()
                df.to_csv(buffer, index=False, encoding='utf-8-sig')
                content = buffer.getvalue()
            mime_type = 'text/csv'
        
        elif format == 'excel':
            if not isinstance(data, pd.DataFrame):
                data = pd.DataFrame(data)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                data.to_excel(writer, index=False, sheet_name='Sheet1')
            content = buffer.getvalue()
            mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # エクスポート情報の記録
        export_info = {
            'timestamp': datetime.now().isoformat(),
            'filename': filename,
            'format': format,
            'size': len(content) if isinstance(content, str) else len(content),
            'metadata': metadata or {},
            'hash': hashlib.md5(
                content.encode() if isinstance(content, str) else content
            ).hexdigest()
        }
        st.session_state.export_history.append(export_info)
        
        return {
            'content': content,
            'filename': filename,
            'mime_type': mime_type,
            'export_info': export_info
        }
    
    def get_export_history(self) -> List[Dict]:
        """
        エクスポート履歴を取得
        
        Returns:
        --------
        List[Dict]
            エクスポート履歴
        """
        return st.session_state.export_history
    
    def clear_export_history(self) -> None:
        """エクスポート履歴をクリア"""
        st.session_state.export_history.clear()


def render_export_ui(
    data: Union[Dict, List, pd.DataFrame],
    title: str = "データのエクスポート",
    default_filename: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> None:
    """
    エクスポートUIを表示
    
    Parameters:
    -----------
    data : Union[Dict, List, pd.DataFrame]
        エクスポートするデータ
    title : str, optional
        UIのタイトル
    default_filename : Optional[str], optional
        デフォルトのファイル名
    metadata : Optional[Dict], optional
        メタデータ
    """
    export_manager = ExportManager()
    
    st.subheader(title)
    
    # エクスポート形式の選択
    format = st.radio(
        "エクスポート形式",
        ['JSON', 'CSV', 'Excel'],
        horizontal=True
    ).lower()
    
    # ファイル名の入力
    filename = st.text_input(
        "ファイル名",
        value=default_filename or f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
    )
    
    # エクスポートボタン
    if st.button("エクスポート"):
        try:
            export_result = export_manager.export_data(
                data=data,
                format=format,
                filename=filename,
                metadata=metadata
            )
            
            # ダウンロードボタンの表示
            st.download_button(
                label="ダウンロード",
                data=export_result['content'],
                file_name=export_result['filename'],
                mime=export_result['mime_type']
            )
            
            st.success("エクスポートが完了しました")
            
        except Exception as e:
            st.error(f"エクスポート中にエラーが発生しました: {str(e)}")


def render_export_history() -> None:
    """エクスポート履歴を表示"""
    export_manager = ExportManager()
    history = export_manager.get_export_history()
    
    if not history:
        st.info("エクスポート履歴がありません")
        return
    
    st.subheader("エクスポート履歴")
    
    for export in reversed(history):
        with st.expander(
            f"{export['filename']} - {datetime.fromisoformat(export['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}"
        ):
            st.write(f"**形式:** {export['format']}")
            st.write(f"**サイズ:** {export['size']} バイト")
            if export['metadata']:
                st.write("**メタデータ:**")
                st.json(export['metadata'])
    
    if st.button("履歴をクリア"):
        export_manager.clear_export_history()
        st.experimental_rerun()


# グローバルなエクスポートマネージャーのインスタンス
export_manager = ExportManager() 