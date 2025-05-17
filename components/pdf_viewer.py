import streamlit as st
from typing import Optional, Dict, Any
import base64
from datetime import datetime
import json
from utils.pdf_utils import load_pdf, get_pdf_metadata
from utils.cache_utils import SnowflakeCache

def render_pdf_viewer(
    pdf_data: Optional[Dict[str, Any]] = None,
    page_number: int = 1,
    cache: Optional[SnowflakeCache] = None
) -> None:
    """
    PDFビューアーコンポーネントをレンダリング
    
    Args:
        pdf_data: PDFデータ（メタデータ、コンテンツ、ページ情報を含む）
        page_number: 表示するページ番号
        cache: キャッシュインスタンス
    """
    if not pdf_data:
        st.info("PDFが選択されていません")
        return

    # メタデータの表示
    with st.expander("PDFメタデータ", expanded=False):
        metadata = pdf_data.get("metadata", {})
        st.json(metadata)

    # ページナビゲーション
    total_pages = pdf_data.get("total_pages", 1)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("← 前のページ", disabled=page_number <= 1):
            st.session_state.current_page = max(1, page_number - 1)
            st.rerun()
    
    with col2:
        st.write(f"ページ {page_number} / {total_pages}")
        new_page = st.number_input(
            "ページ番号",
            min_value=1,
            max_value=total_pages,
            value=page_number,
            key="page_input"
        )
        if new_page != page_number:
            st.session_state.current_page = new_page
            st.rerun()
    
    with col3:
        if st.button("次のページ →", disabled=page_number >= total_pages):
            st.session_state.current_page = min(total_pages, page_number + 1)
            st.rerun()

    # PDFコンテンツの表示
    try:
        # キャッシュからPDFデータを取得
        cache_key = f"pdf_content_{pdf_data['id']}_{page_number}"
        pdf_content = cache.get(cache_key) if cache else None
        
        if not pdf_content:
            # キャッシュになければPDFを読み込む
            pdf_content = load_pdf(pdf_data["id"], page_number)
            if cache:
                cache.set(cache_key, pdf_content)
        
        # PDFの表示
        if pdf_content:
            # Base64エンコードされたPDFデータを表示
            base64_pdf = base64.b64encode(pdf_content).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        else:
            st.error("PDFの読み込みに失敗しました")
    
    except Exception as e:
        st.error(f"PDFの表示中にエラーが発生しました: {str(e)}")

def render_pdf_thumbnail(pdf_data: Dict[str, Any], size: int = 200) -> None:
    """
    PDFのサムネイルを表示
    
    Args:
        pdf_data: PDFデータ
        size: サムネイルのサイズ（ピクセル）
    """
    try:
        # サムネイルの生成（最初のページ）
        thumbnail = get_pdf_metadata(pdf_data["id"]).get("thumbnail")
        if thumbnail:
            st.image(thumbnail, width=size)
        else:
            st.image("assets/pdf_icon.png", width=size)
    except Exception as e:
        st.error(f"サムネイルの表示に失敗しました: {str(e)}")

def render_pdf_info(pdf_data: Dict[str, Any]) -> None:
    """
    PDFの基本情報を表示
    
    Args:
        pdf_data: PDFデータ
    """
    metadata = pdf_data.get("metadata", {})
    
    # 基本情報の表示
    st.write("**ファイル名:**", metadata.get("filename", "不明"))
    st.write("**ページ数:**", metadata.get("pages", 0))
    st.write("**アップロード日時:**", metadata.get("upload_date", "不明"))
    
    # 追加情報（存在する場合）
    if "author" in metadata:
        st.write("**作成者:**", metadata["author"])
    if "title" in metadata:
        st.write("**タイトル:**", metadata["title"])
    if "subject" in metadata:
        st.write("**サブジェクト:**", metadata["subject"]) 