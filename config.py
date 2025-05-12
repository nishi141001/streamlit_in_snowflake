"""
ChatPDF in Snowflake - 設定ファイル

アプリケーションの定数と設定を管理
"""

import os

# 基本設定
SETTINGS = {
    # Snowflake関連設定
    "SNOWFLAKE_STAGE": os.environ.get("SNOWFLAKE_STAGE", "@my_pdf_stage"),
    
    # Cortexモデル設定
    "MODEL_EMBED": os.environ.get("MODEL_EMBED", "snowflake-arctic-embed-m"),
    "MODEL_CHAT": os.environ.get("MODEL_CHAT", "mistral-large"),
    
    # キャッシュ設定
    "CACHE_EXPIRE": int(os.environ.get("CACHE_EXPIRE", "3600")),
    
    # アプリケーション設定
    "MAX_TOKENS": 2048,
    "MAX_CHUNKS_FOR_QUERY": 5,
    "SIMILARITY_THRESHOLD": 0.65,
    "SUMMARY_MAX_LENGTH": 1000,
    
    # デバッグモード
    "DEBUG": os.environ.get("DEBUG", "false").lower() == "true",
}

# メッセージテンプレート
MESSAGES = {
    # ユーザー向けメッセージ
    "UPLOAD_PROMPT": "👈 サイドバーからPDFファイルをアップロードしてください。",
    "COMBINED_QUESTION_PLACEHOLDER": "例: これらの文書の主要な論点は何ですか？共通する課題はありますか？",
    "FILE_PROCESSING_ERROR": "ファイル処理中にエラーが発生しました。別のファイルを試してください。",
    "ANALYZING": "文書を分析中です...",
    "SUMMARIZING": "要約を生成中です...",
    "SEARCH_PLACEHOLDER": "検索キーワードを入力（複数の単語で検索可能）",
    
    # AI指示プロンプト
    "CROSS_DOC_PROMPT": """
    あなたは複数のPDFドキュメントを分析するAIアシスタントです。
    以下の文脈情報を基に、質問に対して正確かつ詳細に回答してください。
    
    回答のガイドライン:
    1. 与えられた文脈情報のみに基づいて回答する
    2. 文脈に情報がない場合は「この情報は提供された文書には含まれていません」と伝える
    3. 出典情報を明記し、どの文書のどのページから情報を得たかを示す
    4. 箇条書きや段落を適切に使い、読みやすく構造化された回答を作成する
    """,
    
    "SINGLE_DOC_PROMPT": """
    あなたはPDF文書専門のAIアシスタントです。
    以下のPDFから抽出された情報に基づいて質問に答えてください。
    
    回答のガイドライン:
    1. 与えられた文脈情報のみに基づいて回答する
    2. 文脈に情報がない場合は「この情報は提供された文書には含まれていません」と伝える
    3. 引用元のページ番号を明記する
    4. 専門用語があれば簡潔に説明を加える
    """,
    
    "SUMMARY_PROMPT": """
    あなたは文書要約の専門家です。以下の文書を要約してください。
    
    要約のガイドライン:
    1. 主要なポイントと論点を抽出する
    2. 簡潔かつ包括的な要約を作成する
    3. 原文の意図や主張を正確に反映する
    4. 個人的な意見や解釈を加えない
    """,
}

# UI設定
UI_CONFIG = {
    "PAGE_TITLE": "ChatPDF in Snowflake",
    "PAGE_ICON": "📄",
    "APP_TITLE": "📄 ChatPDF in Snowflake",
    "LAYOUT": "wide",
    "SIDEBAR_STATE": "expanded",
    
    # カスタムCSS
    "CUSTOM_CSS": """
    <style>
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            padding-left: 1rem;
            padding-right: 1rem;
        }
        
        .chat-message {
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            display: flex;
            flex-direction: column;
            position: relative;
        }
        
        .chat-message.user {
            background-color: #e6f7ff;
            border-left: 4px solid #1890ff;
        }
        
        .chat-message.assistant {
            background-color: #f6f6f6;
            border-left: 4px solid #888888;
        }
        
        .chat-message .source {
            font-size: 0.85rem;
            color: #666;
            margin-top: 0.5rem;
        }
        
        .pdf-viewer {
            border: 1px solid #eee;
            border-radius: 0.5rem;
        }
        
        .search-result {
            border: 1px solid #ddd;
            border-radius: 0.5rem;
            padding: 0.75rem;
            margin-bottom: 0.75rem;
        }
        
        .search-result .highlight {
            background-color: #fff4c8;
            padding: 0 0.2rem;
        }
        
        .stButton > button {
            min-height: 2.5rem;
        }
    </style>
    """,
    
    # フッター
    "FOOTER": """
    <div style='text-align:center;color:#888;'>
        <p>Powered by Snowflake Cortex & Streamlit ©2025</p>
    </div>
    """,
}
