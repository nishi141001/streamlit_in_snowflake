"""
AIインターフェースコンポーネント

機能
- ドキュメント要約生成
- 質問応答
- 多言語翻訳
- カスタムプロンプト管理
- 回答履歴表示
"""

import streamlit as st
from typing import List, Dict, Optional
from services.ai_service import AIService
from services.document_service import DocumentService

class AIInterface:
    def __init__(self):
        """初期化"""
        self.ai_service = AIService()
        self.document_service = DocumentService()
        
        # セッション状態の初期化
        if "ai_tab" not in st.session_state:
            st.session_state.ai_tab = "summary"
        if "custom_prompt_name" not in st.session_state:
            st.session_state.custom_prompt_name = ""
        if "custom_prompt_description" not in st.session_state:
            st.session_state.custom_prompt_description = ""
        if "custom_prompt_template" not in st.session_state:
            st.session_state.custom_prompt_template = ""
    
    def render(self):
        """インターフェースの描画"""
        # タブの選択
        tabs = st.tabs([
            "要約生成",
            "質問応答",
            "翻訳",
            "カスタムプロンプト",
            "回答履歴"
        ])
        
        # 要約生成タブ
        with tabs[0]:
            self._render_summary_tab()
        
        # 質問応答タブ
        with tabs[1]:
            self._render_qa_tab()
        
        # 翻訳タブ
        with tabs[2]:
            self._render_translation_tab()
        
        # カスタムプロンプトタブ
        with tabs[3]:
            self._render_custom_prompt_tab()
        
        # 回答履歴タブ
        with tabs[4]:
            self._render_history_tab()
    
    def _render_summary_tab(self):
        """要約生成タブの描画"""
        st.header("ドキュメント要約生成")
        
        # ドキュメント選択
        documents = self.document_service.get_document_list()
        selected_doc = st.selectbox(
            "ドキュメントを選択",
            options=[d["file_name"] for d in documents],
            format_func=lambda x: x
        )
        
        if selected_doc:
            # 要約オプション
            col1, col2 = st.columns(2)
            with col1:
                max_length = st.number_input(
                    "最大文字数",
                    min_value=100,
                    max_value=1000,
                    value=200,
                    step=50
                )
                language = st.selectbox(
                    "出力言語",
                    options=["ja", "en", "zh", "ko"],
                    format_func=lambda x: {
                        "ja": "日本語",
                        "en": "英語",
                        "zh": "中国語",
                        "ko": "韓国語"
                    }[x]
                )
            with col2:
                style = st.selectbox(
                    "スタイル",
                    options=["formal", "casual", "technical"],
                    format_func=lambda x: {
                        "formal": "フォーマル",
                        "casual": "カジュアル",
                        "technical": "技術的"
                    }[x]
                )
            
            # 要約生成
            if st.button("要約を生成"):
                with st.spinner("要約を生成中..."):
                    # ドキュメントの取得
                    doc_info = self.document_service.get_document_info(selected_doc)
                    if doc_info:
                        # 要約の生成
                        result = self.ai_service.generate_summary(
                            document_text=doc_info["content"],
                            max_length=max_length,
                            language=language,
                            style=style
                        )
                        
                        # 結果の表示
                        st.subheader("要約")
                        st.write(result["summary"])
                        
                        st.subheader("重要なポイント")
                        for point in result["key_points"]:
                            st.write(f"• {point}")
                        
                        # メタデータの表示
                        with st.expander("メタデータ"):
                            st.json(result["metadata"])
    
    def _render_qa_tab(self):
        """質問応答タブの描画"""
        st.header("質問応答")
        
        # ドキュメント選択（複数選択可）
        documents = self.document_service.get_document_list()
        selected_docs = st.multiselect(
            "ドキュメントを選択",
            options=[d["file_name"] for d in documents],
            format_func=lambda x: x
        )
        
        if selected_docs:
            # 質問入力
            question = st.text_area("質問を入力")
            
            # 回答オプション
            col1, col2 = st.columns(2)
            with col1:
                language = st.selectbox(
                    "回答言語",
                    options=["ja", "en", "zh", "ko"],
                    format_func=lambda x: {
                        "ja": "日本語",
                        "en": "英語",
                        "zh": "中国語",
                        "ko": "韓国語"
                    }[x]
                )
                include_explanation = st.checkbox("説明を含める", value=True)
            with col2:
                # カスタムプロンプトの選択
                custom_prompts = self.ai_service.get_custom_prompts()
                custom_prompt_id = st.selectbox(
                    "カスタムプロンプト",
                    options=[None] + [p["prompt_id"] for p in custom_prompts],
                    format_func=lambda x: "デフォルト" if x is None else next(
                        (p["name"] for p in custom_prompts if p["prompt_id"] == x),
                        "不明なプロンプト"
                    )
                )
            
            # 質問実行
            if st.button("質問を実行") and question:
                with st.spinner("回答を生成中..."):
                    # コンテキストの準備
                    context = []
                    for doc_name in selected_docs:
                        doc_info = self.document_service.get_document_info(doc_name)
                        if doc_info:
                            context.append({
                                "file_name": doc_name,
                                "text": doc_info["content"],
                                "page": 1  # ページ番号は要実装
                            })
                    
                    # 回答の生成
                    result = self.ai_service.answer_question(
                        question=question,
                        context=context,
                        custom_prompt_id=custom_prompt_id,
                        include_explanation=include_explanation,
                        language=language
                    )
                    
                    # 結果の表示
                    st.subheader("回答")
                    st.write(result["answer"])
                    
                    if include_explanation and result.get("explanation"):
                        st.subheader("説明")
                        st.write(result["explanation"])
                    
                    # 信頼度の表示
                    st.metric("信頼度", f"{result.get('confidence', 0.0):.1%}")
                    
                    # ソースの表示
                    if result.get("sources"):
                        st.subheader("参照ソース")
                        for source in result["sources"]:
                            st.write(f"• {source['file_name']} (ページ {source['page']}) - 関連度: {source['relevance']:.1%}")
    
    def _render_translation_tab(self):
        """翻訳タブの描画"""
        st.header("テキスト翻訳")
        
        # 翻訳オプション
        col1, col2 = st.columns(2)
        with col1:
            source_language = st.selectbox(
                "元の言語",
                options=["ja", "en", "zh", "ko"],
                format_func=lambda x: {
                    "ja": "日本語",
                    "en": "英語",
                    "zh": "中国語",
                    "ko": "韓国語"
                }[x]
            )
        with col2:
            target_language = st.selectbox(
                "翻訳先の言語",
                options=["ja", "en", "zh", "ko"],
                format_func=lambda x: {
                    "ja": "日本語",
                    "en": "英語",
                    "zh": "中国語",
                    "ko": "韓国語"
                }[x]
            )
        
        style = st.selectbox(
            "翻訳スタイル",
            options=["formal", "casual", "technical"],
            format_func=lambda x: {
                "formal": "フォーマル",
                "casual": "カジュアル",
                "technical": "技術的"
            }[x]
        )
        
        # テキスト入力
        text = st.text_area("翻訳するテキストを入力")
        
        # 翻訳実行
        if st.button("翻訳") and text:
            with st.spinner("翻訳中..."):
                result = self.ai_service.translate_text(
                    text=text,
                    source_language=source_language,
                    target_language=target_language,
                    style=style
                )
                
                # 結果の表示
                st.subheader("翻訳結果")
                st.write(result["translated_text"])
                
                # メタデータの表示
                with st.expander("メタデータ"):
                    st.json(result["metadata"])
    
    def _render_custom_prompt_tab(self):
        """カスタムプロンプトタブの描画"""
        st.header("カスタムプロンプト管理")
        
        # タブの選択
        prompt_tabs = st.tabs(["プロンプト一覧", "新規作成"])
        
        # プロンプト一覧タブ
        with prompt_tabs[0]:
            prompts = self.ai_service.get_custom_prompts()
            if prompts:
                for prompt in prompts:
                    with st.expander(f"{prompt['name']} ({prompt['description']})"):
                        st.write("テンプレート:")
                        st.code(prompt["prompt_template"], language="text")
                        
                        if prompt["parameters"]:
                            st.write("パラメータ:")
                            st.json(prompt["parameters"])
                        
                        st.write(f"作成日時: {prompt['created_at']}")
                        st.write(f"更新日時: {prompt['updated_at']}")
                        
                        # プロンプトの削除
                        if st.button("削除", key=f"delete_{prompt['prompt_id']}"):
                            # TODO: 削除機能の実装
                            st.warning("削除機能は未実装です")
            else:
                st.info("カスタムプロンプトがありません")
        
        # 新規作成タブ
        with prompt_tabs[1]:
            st.subheader("新規プロンプト作成")
            
            # プロンプト情報の入力
            st.text_input(
                "プロンプト名",
                key="custom_prompt_name",
                help="プロンプトを識別するための名前"
            )
            
            st.text_area(
                "説明",
                key="custom_prompt_description",
                help="プロンプトの用途や特徴の説明"
            )
            
            st.text_area(
                "プロンプトテンプレート",
                key="custom_prompt_template",
                help="""使用可能な変数:
                - {question}: 質問文
                - {context}: コンテキスト
                - {language}: 出力言語
                - {include_explanation}: 説明を含めるかどうか
                """
            )
            
            # パラメータ定義
            st.subheader("パラメータ定義（オプション）")
            st.json({
                "example_parameter": {
                    "type": "string",
                    "description": "パラメータの説明",
                    "default": "デフォルト値"
                }
            })
            
            # プロンプトの保存
            if st.button("保存"):
                if not st.session_state.custom_prompt_name:
                    st.error("プロンプト名を入力してください")
                elif not st.session_state.custom_prompt_template:
                    st.error("プロンプトテンプレートを入力してください")
                else:
                    result = self.ai_service.save_custom_prompt(
                        name=st.session_state.custom_prompt_name,
                        description=st.session_state.custom_prompt_description,
                        prompt_template=st.session_state.custom_prompt_template
                    )
                    
                    if result["status"] == "success":
                        st.success("プロンプトを保存しました")
                        # 入力フィールドのクリア
                        st.session_state.custom_prompt_name = ""
                        st.session_state.custom_prompt_description = ""
                        st.session_state.custom_prompt_template = ""
                    else:
                        st.error(f"プロンプトの保存に失敗しました: {result.get('error')}")
    
    def _render_history_tab(self):
        """回答履歴タブの描画"""
        st.header("回答履歴")
        
        # 履歴の取得
        history = self.ai_service.get_answer_history(limit=20)
        
        if history:
            for item in history:
                with st.expander(f"{item['query']} ({item['created_at']})"):
                    st.write("回答:")
                    st.write(item["answer"])
                    
                    if item.get("explanation"):
                        st.write("説明:")
                        st.write(item["explanation"])
                    
                    # メタデータの表示
                    with st.expander("メタデータ"):
                        st.json(item["metadata"])
                    
                    # コンテキストの表示
                    with st.expander("コンテキスト"):
                        for ctx in item["context"]:
                            st.write(f"• {ctx['file_name']} (ページ {ctx['page']})")
        else:
            st.info("回答履歴がありません") 