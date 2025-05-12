"""
PDF操作ユーティリティ

PDFファイルの読み込み、テキスト抽出、メタデータ解析、テーブル/図表抽出などの機能
"""

import os
import tempfile
from datetime import datetime
import re
import streamlit as st
from pypdf import PdfReader
import pdfplumber
from PIL import Image
import io
from config import SETTINGS


@st.cache_data(ttl=SETTINGS["CACHE_EXPIRE"])
def load_pdf(uploaded_file):
    """
    アップロードされたPDFファイルをバイト列として読み込む
    
    Parameters:
    -----------
    uploaded_file : streamlit.UploadedFile
        アップロードされたPDFファイル
        
    Returns:
    --------
    bytes
        PDFのバイト列
    """
    return uploaded_file.read()


@st.cache_data(ttl=SETTINGS["CACHE_EXPIRE"])
def extract_text(pdf_bytes):
    """
    PDFからテキストを抽出
    
    Parameters:
    -----------
    pdf_bytes : bytes
        PDFのバイト列
        
    Returns:
    --------
    tuple
        (PdfReaderオブジェクト, ページごとのテキストリスト)
    """
    # 一時ファイルにPDFを書き込み
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    
    try:
        # PDFリーダーでファイルを開く
        reader = PdfReader(tmp_path)
        
        # 各ページからテキストを抽出
        text_pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            # テキストクリーニング
            text = clean_text(text)
            text_pages.append(text)
        
        return reader, text_pages
    except Exception as e:
        print(f"PDFテキスト抽出中にエラー: {str(e)}")
        return None, []
    finally:
        # 一時ファイルを削除
        try:
            os.unlink(tmp_path)
        except:
            pass


def clean_text(text):
    """
    抽出されたテキストをクリーニング
    
    Parameters:
    -----------
    text : str
        クリーニングするテキスト
        
    Returns:
    --------
    str
        クリーニングされたテキスト
    """
    if not text:
        return ""
    
    # 余分な空白を削除
    text = re.sub(r'\s+', ' ', text)
    
    # 先頭と末尾の空白を削除
    text = text.strip()
    
    # 特殊文字の処理
    text = text.replace('\x00', '')
    
    return text


@st.cache_data(ttl=SETTINGS["CACHE_EXPIRE"])
def get_pdf_metadata(reader):
    """
    PDFのメタデータを抽出
    
    Parameters:
    -----------
    reader : PdfReader
        PdfReaderオブジェクト
        
    Returns:
    --------
    dict
        PDFのメタデータ辞書
    """
    if not reader or not hasattr(reader, 'metadata'):
        return {
            "タイトル": "不明",
            "作成者": "不明",
            "ページ数": "0",
            "作成日時": "不明"
        }
    
    meta = reader.metadata
    info = {
        "タイトル": meta.title or "不明",
        "作成者": meta.author or "不明",
        "ページ数": str(len(reader.pages)),
    }
    
    # 作成日の処理
    raw_date = meta.get('/CreationDate', '')
    if raw_date.startswith('D:'):
        try:
            # PDFの日付形式 'D:YYYYMMDDHHmmSS' を解析
            d = datetime.strptime(raw_date[2:16], '%Y%m%d%H%M%S')
            info["作成日時"] = d.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            info["作成日時"] = "解析失敗"
    else:
        info["作成日時"] = "不明"
    
    return info


def split_text_into_chunks(text, chunk_size=1000, overlap=200):
    """
    長いテキストを重複付きチャンクに分割
    
    Parameters:
    -----------
    text : str
        分割するテキスト
    chunk_size : int, optional
        各チャンクの最大サイズ
    overlap : int, optional
        チャンク間の重複文字数
        
    Returns:
    --------
    list[str]
        分割されたテキストチャンクのリスト
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        
        # なるべく文の途中で切らないように調整
        if end < len(text):
            # 区切り文字を探す
            for delimiter in ["\n\n", "\n", "。", ".", "！", "!", "？", "?"]:
                pos = text.rfind(delimiter, start, end)
                if pos > start:  # 適切な位置で見つかった場合
                    end = pos + len(delimiter)
                    break
        
        # チャンクを追加
        chunks.append(text[start:end])
        
        # 次の開始位置（重複を考慮）
        start = end - overlap
        
        # 開始位置が進まない場合の対策
        if start >= end:
            start = end
    
    return chunks


def highlight_text(text, query, max_context=100):
    """
    検索クエリに一致するテキスト部分をハイライト
    
    Parameters:
    -----------
    text : str
        対象テキスト
    query : str
        検索クエリ
    max_context : int, optional
        表示するコンテキストの最大長
        
    Returns:
    --------
    str
        ハイライト付きHTML
    """
    if not query or not text:
        return text
    
    # クエリに一致する箇所を見つける
    query_lower = query.lower()
    text_lower = text.lower()
    
    if query_lower not in text_lower:
        return text
    
    # 一致位置を特定
    start_pos = text_lower.find(query_lower)
    query_len = len(query)
    
    # コンテキスト範囲を計算
    context_start = max(0, start_pos - max_context // 2)
    context_end = min(len(text), start_pos + query_len + max_context // 2)
    
    # 表示テキストの取得
    prefix = "..." if context_start > 0 else ""
    suffix = "..." if context_end < len(text) else ""
    
    display_text = prefix + text[context_start:start_pos] + \
                   f"<mark>{text[start_pos:start_pos+query_len]}</mark>" + \
                   text[start_pos+query_len:context_end] + suffix
    
    return display_text


@st.cache_data(ttl=SETTINGS["CACHE_EXPIRE"])
def extract_tables_and_figures(pdf_bytes):
    """
    PDFからテーブルと図表を抽出（pdfplumberのみを使用）
    
    Parameters:
    -----------
    pdf_bytes : bytes
        PDFのバイト列
        
    Returns:
    --------
    tuple
        (テーブルリスト, 図表リスト)
        テーブルリスト: 各ページのテーブル情報のリスト
        図表リスト: 各ページの図表情報のリスト
    """
    tables = []
    figures = []
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    
    try:
        with pdfplumber.open(tmp_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # テーブル抽出
                page_tables = page.extract_tables()
                if page_tables:
                    for table_num, table in enumerate(page_tables):
                        tables.append({
                            'page': page_num + 1,
                            'table_num': table_num + 1,
                            'data': table,
                            'bbox': page.find_tables()[table_num].bbox
                        })
                
                # 図表抽出（pdfplumberの画像抽出機能を使用）
                images = page.images
                for img_num, img in enumerate(images):
                    figures.append({
                        'page': page_num + 1,
                        'figure_num': img_num + 1,
                        'bbox': img['bbox'],
                        'width': img['width'],
                        'height': img['height']
                    })
        
        return tables, figures
    except Exception as e:
        print(f"テーブル/図表抽出中にエラー: {str(e)}")
        return [], []
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


def extract_text_with_tables(pdf_bytes):
    """
    PDFからテキストとテーブルを抽出し、構造化されたデータを返す
    
    Parameters:
    -----------
    pdf_bytes : bytes
        PDFのバイト列
        
    Returns:
    --------
    list[dict]
        ページごとの構造化データのリスト
        各要素は {'text': str, 'tables': list, 'figures': list} の形式
    """
    reader, text_pages = extract_text(pdf_bytes)
    tables, figures = extract_tables_and_figures(pdf_bytes)
    
    structured_pages = []
    for page_num, text in enumerate(text_pages):
        page_data = {
            'text': text,
            'tables': [t for t in tables if t['page'] == page_num + 1],
            'figures': [f for f in figures if f['page'] == page_num + 1]
        }
        structured_pages.append(page_data)
    
    return structured_pages
