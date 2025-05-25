"""
検索インターフェースコンポーネント

機能
- 複数PDF検索モードと個別PDF検索モードの切り替え
- 検索結果のグループ化と階層表示
- 強化されたプレビュー表示
- 詳細な検索結果の分析情報
- ページ内の検索ハイライト
- ドラッグ&ドロップでのファイルアップロード
- レスポンシブデザイン
- ダークモード対応
- フィルタリングと並び替え機能
"""

import streamlit as st
from typing import List, Dict, Optional, Union, Any
from datetime import datetime, timedelta
import json
import pandas as pd
from services.search_service import SearchService
from services.document_service import DocumentService
from services.ai_service import AIService
from utils.export_utils import export_manager
import numpy as np
import plotly.express as px

class SearchInterface:
    def __init__(self):
        self.search_service = SearchService()
        self.document_service = DocumentService()
        self.ai_service = AIService()
        self._init_session_state()
    
    def _init_session_state(self):
        """セッション状態の初期化"""
        if "search_history" not in st.session_state:
            st.session_state.search_history = []
        if "current_filters" not in st.session_state:
            st.session_state.current_filters = {}
        if "search_mode" not in st.session_state:
            st.session_state.search_mode = "all"  # "all" or "single"
        if "selected_document" not in st.session_state:
            st.session_state.selected_document = None
        if "dark_mode" not in st.session_state:
            st.session_state.dark_mode = False
    
    def render_search_interface(self):
        """検索インターフェースの表示"""
        # 検索モードの選択
        st.markdown("### 検索モード")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(
                "📚 複数PDF検索",
                use_container_width=True,
                type="primary" if st.session_state.search_mode == "all" else "secondary"
            ):
                st.session_state.search_mode = "all"
                st.session_state.selected_document = None
                st.rerun()
        
        with col2:
            if st.button(
                "📄 個別PDF検索",
                use_container_width=True,
                type="primary" if st.session_state.search_mode == "single" else "secondary"
            ):
                st.session_state.search_mode = "single"
                st.rerun()
        
        # 検索モードに応じた説明
        if st.session_state.search_mode == "all":
            st.info("""
            📚 **複数PDF検索モード**
            - すべてのPDFドキュメントを対象に検索
            - 高度なフィルタリング機能が利用可能
            - 複数ドキュメントにまたがる検索結果を表示
            """)
        else:
            st.info("""
            📄 **個別PDF検索モード**
            - 選択した1つのPDFドキュメント内を検索
            - ページ単位での詳細な検索が可能
            - コンテキストを考慮した検索結果を表示
            """)
        
        # 検索フォーム
        with st.form("search_form"):
            # 個別PDF検索モードの場合、ドキュメント選択
            if st.session_state.search_mode == "single":
                documents = self.document_service.get_document_list()
                selected_doc = st.selectbox(
                    "検索対象のドキュメント",
                    options=[d["file_name"] for d in documents],
                    index=0 if not st.session_state.selected_document else
                    [d["file_name"] for d in documents].index(st.session_state.selected_document)
                )
                st.session_state.selected_document = selected_doc
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                query = st.text_input(
                    "検索クエリ",
                    placeholder="検索したい内容を入力してください",
                    help="キーワード、フレーズ、または自然言語で検索できます"
                )
            
            with col2:
                search_type = st.selectbox(
                    "検索タイプ",
                    ["ハイブリッド", "ベクトル", "キーワード"],
                    help="検索方法を選択してください"
                )
            
            # 高度な検索オプション（複数PDF検索モードの場合のみ表示）
            if st.session_state.search_mode == "all":
                with st.expander("高度な検索オプション"):
                    col3, col4 = st.columns(2)
                    
                    with col3:
                        # 日付範囲
                        date_range = st.date_input(
                            "日付範囲",
                            value=(
                                datetime.now() - timedelta(days=30),
                                datetime.now()
                            ),
                            help="ドキュメントのアップロード日時で絞り込み"
                        )
                        
                        # ファイルタイプ
                        file_types = st.multiselect(
                            "ファイルタイプ",
                            ["PDF", "DOCX", "XLSX", "PPTX"],
                            default=["PDF"],
                            help="検索対象のファイルタイプを選択"
                        )
                    
                    with col4:
                        # ページ範囲
                        page_range = st.slider(
                            "ページ範囲",
                            min_value=1,
                            max_value=1000,
                            value=(1, 100),
                            help="検索対象のページ範囲を指定"
                        )
                        
                        # タグ
                        tags = st.multiselect(
                            "タグ",
                            self._get_available_tags(),
                            help="タグで絞り込み"
                        )
            
            # 検索ボタン
            search_button = st.form_submit_button("検索")
        
        # 検索実行
        if search_button and query:
            filters = None
            if st.session_state.search_mode == "all":
                filters = {
                    "date_range": date_range,
                    "file_types": file_types,
                    "page_range": page_range,
                    "tags": tags
                }
            
            self._execute_search(
                query=query,
                search_type=search_type,
                mode=st.session_state.search_mode,
                target_document=st.session_state.selected_document,
                filters=filters
            )
        
        # 検索履歴の表示
        self._render_search_history()
        
        # 検索結果の表示
        if "search_results" in st.session_state:
            self._render_search_results()
    
    def _render_theme_switch(self):
        """テーマ切り替えスイッチの表示"""
        col1, col2 = st.columns([6, 1])
        
        with col2:
            if st.button("🌙" if not st.session_state.dark_mode else "☀️"):
                st.session_state.dark_mode = not st.session_state.dark_mode
                st.rerun()
        
        # ダークモードの適用
        if st.session_state.dark_mode:
            st.markdown("""
            <style>
            .stApp {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
            .stButton>button {
                background-color: #2D2D2D;
                color: #FFFFFF;
            }
            </style>
            """, unsafe_allow_html=True)
    
    def _execute_search(
        self,
        query: str,
        search_type: str,
        mode: str,
        target_document: Optional[str] = None,
        filters: Optional[Dict] = None
    ):
        """検索の実行"""
        # 検索オプションの設定
        search_options = {
            "search_type": search_type.lower(),
            "use_similar_terms": True
        }
        
        # 検索の実行
        results = self.search_service.search(
            query=query,
            mode=mode,
            target_document=target_document,
            filters=filters,
            search_options=search_options,
            top_n=10
        )
        
        # 結果の保存
        st.session_state.search_results = results
        st.session_state.current_filters = filters
    
    def _render_search_results(self):
        """検索結果の表示（改善版）"""
        results = st.session_state.search_results
        
        # 検索モードに応じた結果表示
        if results["metadata"]["mode"] == "single":
            st.markdown(f"### 📄 {results['metadata']['target_document']} の検索結果")
        else:
            st.markdown("### 📚 複数PDF検索結果")
        
        # 結果の統計情報と分析
        self._render_search_analytics(results)
        
        # エクスポートオプション
        self._render_export_options(results)
        
        # 検索結果のグループ化と表示
        grouped_results = self._group_search_results(results["results"])
        self._render_grouped_results(grouped_results)
    
    def _render_search_analytics(self, results: Dict):
        """検索結果の分析情報の表示（詳細版）"""
        with st.expander("📊 検索結果の分析", expanded=True):
            # 基本統計情報
            self._render_basic_stats(results)
            
            # 詳細な分析情報
            tab1, tab2, tab3 = st.tabs([
                "📈 スコア分析",
                "📑 ドキュメント分析",
                "🔍 マッチング分析"
            ])
            
            with tab1:
                self._render_score_analysis(results)
            
            with tab2:
                self._render_document_analysis(results)
            
            with tab3:
                self._render_matching_analysis(results)
    
    def _render_basic_stats(self, results: Dict):
        """基本統計情報の表示"""
        col1, col2, col3, col4 = st.columns(4)
        
        # ドキュメント数
        doc_matches = {}
        for result in results["results"]:
            doc_name = result["file_name"]
            doc_matches[doc_name] = doc_matches.get(doc_name, 0) + 1
        
        with col1:
            st.metric(
                "検索対象ドキュメント数",
                len(doc_matches),
                help="マッチしたドキュメントの総数"
            )
        
        # 平均スコア
        scores = [
            result.get("similarity", result.get("match_score", 0))
            for result in results["results"]
        ]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        with col2:
            st.metric(
                "平均マッチスコア",
                f"{avg_score:.2f}",
                help="全検索結果の平均スコア"
            )
        
        # 検索結果数
        with col3:
            st.metric(
                "検索結果の総数",
                len(results["results"]),
                help="マッチした箇所の総数"
            )
        
        # 高スコアの結果数
        high_scores = len([s for s in scores if s > 0.8])
        
        with col4:
            st.metric(
                "高スコアの結果数",
                high_scores,
                help="スコアが0.8以上の結果数"
            )
    
    def _render_score_analysis(self, results: Dict):
        """スコア分析の表示"""
        scores = [
            result.get("similarity", result.get("match_score", 0))
            for result in results["results"]
        ]
        
        if not scores:
            st.info("スコア分析を行うための検索結果がありません。")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            # スコア分布のヒストグラム
            st.markdown("#### スコア分布")
            hist_values = np.histogram(
                scores,
                bins=10,
                range=(0, 1)
            )
            
            # ヒストグラムの表示
            hist_data = pd.DataFrame({
                "スコア範囲": [f"{hist_values[1][i]:.1f}-{hist_values[1][i+1]:.1f}" for i in range(len(hist_values[0]))],
                "件数": hist_values[0]
            })
            st.bar_chart(hist_data.set_index("スコア範囲"))
        
        with col2:
            # スコア統計情報
            st.markdown("#### スコア統計")
            score_stats = {
                "最高スコア": max(scores),
                "最低スコア": min(scores),
                "平均スコア": sum(scores) / len(scores),
                "中央値": sorted(scores)[len(scores)//2],
                "標準偏差": np.std(scores)
            }
            
            for key, value in score_stats.items():
                st.metric(key, f"{value:.3f}")
    
    def _render_document_analysis(self, results: Dict):
        """ドキュメント分析の表示"""
        # ドキュメントごとの統計
        doc_stats = {}
        for result in results["results"]:
            doc_name = result["file_name"]
            score = result.get("similarity", result.get("match_score", 0))
            
            if doc_name not in doc_stats:
                doc_stats[doc_name] = {
                    "matches": 0,
                    "scores": [],
                    "pages": set(),
                    "matched_terms": set()
                }
            
            doc_stats[doc_name]["matches"] += 1
            doc_stats[doc_name]["scores"].append(score)
            doc_stats[doc_name]["pages"].add(result["page"])
            if "matched_terms" in result:
                doc_stats[doc_name]["matched_terms"].update(result["matched_terms"])
        
        # ドキュメント分析の表示
        st.markdown("#### ドキュメント別分析")
        
        # データフレームの作成
        df_data = []
        for doc_name, stats in doc_stats.items():
            df_data.append({
                "ドキュメント": doc_name,
                "マッチ数": stats["matches"],
                "平均スコア": sum(stats["scores"]) / len(stats["scores"]),
                "マッチしたページ数": len(stats["pages"]),
                "マッチした用語数": len(stats["matched_terms"])
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(
            df.style.background_gradient(subset=["平均スコア"]),
            use_container_width=True
        )
        
        # ドキュメントタイプ別の分析
        st.markdown("#### ドキュメントタイプ別分析")
        doc_types = {}
        for doc_name in doc_stats:
            doc_type = doc_name.split(".")[-1].upper()
            if doc_type not in doc_types:
                doc_types[doc_type] = 0
            doc_types[doc_type] += doc_stats[doc_name]["matches"]
        
        # 円グラフの表示
        fig = px.pie(
            values=list(doc_types.values()),
            names=list(doc_types.keys()),
            title="ドキュメントタイプ別の検索結果分布"
        )
        st.plotly_chart(fig)
    
    def _render_matching_analysis(self, results: Dict):
        """マッチング分析の表示"""
        # マッチした用語の分析
        term_stats = {}
        similar_term_stats = {}
        
        for result in results["results"]:
            # マッチした用語の集計
            if "matched_terms" in result:
                for term in result["matched_terms"]:
                    term_stats[term] = term_stats.get(term, 0) + 1
            
            # 類似語の集計
            if "similar_terms" in result:
                for term in result["similar_terms"]:
                    similar_term_stats[term] = similar_term_stats.get(term, 0) + 1
        
        col1, col2 = st.columns(2)
        
        with col1:
            # マッチした用語のランキング
            st.markdown("#### マッチした用語TOP10")
            if term_stats:
                term_df = pd.DataFrame([
                    {"用語": term, "出現回数": count}
                    for term, count in sorted(
                        term_stats.items(),
                        key=lambda x: x[1],
                        reverse=True
                    )[:10]
                ])
                st.bar_chart(term_df.set_index("用語"))
            else:
                st.info("マッチした用語がありません。")
        
        with col2:
            # 類似語のランキング
            st.markdown("#### 使用された類似語TOP10")
            if similar_term_stats:
                similar_term_df = pd.DataFrame([
                    {"類似語": term, "使用回数": count}
                    for term, count in sorted(
                        similar_term_stats.items(),
                        key=lambda x: x[1],
                        reverse=True
                    )[:10]
                ])
                st.bar_chart(similar_term_df.set_index("類似語"))
            else:
                st.info("使用された類似語がありません。")
        
        # マッチングパターンの分析
        st.markdown("#### マッチングパターンの分析")
        pattern_stats = {
            "完全一致": 0,
            "部分一致": 0,
            "類似語マッチ": 0
        }
        
        for result in results["results"]:
            if result.get("match_type") == "exact":
                pattern_stats["完全一致"] += 1
            elif result.get("match_type") == "partial":
                pattern_stats["部分一致"] += 1
            elif result.get("match_type") == "similar":
                pattern_stats["類似語マッチ"] += 1
        
        # 棒グラフの表示
        pattern_df = pd.DataFrame([
            {"パターン": k, "件数": v}
            for k, v in pattern_stats.items()
        ])
        st.bar_chart(pattern_df.set_index("パターン"))
    
    def _group_search_results(self, results: List[Dict]) -> Dict[str, Dict]:
        """検索結果のグループ化"""
        grouped = {}
        
        for result in results:
            doc_name = result["file_name"]
            page = result["page"]
            
            if doc_name not in grouped:
                grouped[doc_name] = {
                    "total_matches": 0,
                    "avg_score": 0,
                    "pages": {}
                }
            
            if page not in grouped[doc_name]["pages"]:
                grouped[doc_name]["pages"][page] = []
            
            grouped[doc_name]["pages"][page].append(result)
            grouped[doc_name]["total_matches"] += 1
            
            # スコアの更新
            scores = [
                r.get("similarity", r.get("match_score", 0))
                for r in grouped[doc_name]["pages"][page]
            ]
            grouped[doc_name]["avg_score"] = sum(scores) / len(scores)
        
        return grouped
    
    def _render_grouped_results(self, grouped_results: Dict[str, Dict]):
        """グループ化された検索結果の表示"""
        # フィルタリングと並び替えオプション
        with st.expander("🔍 検索結果のフィルタリングと並び替え", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                # スコアによるフィルタリング
                min_score = st.slider(
                    "最小スコア",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.3,
                    step=0.1,
                    help="このスコア以上の結果のみを表示"
                )
                
                # ドキュメントタイプによるフィルタリング
                doc_types = self._get_document_types(grouped_results)
                selected_types = st.multiselect(
                    "ドキュメントタイプ",
                    options=doc_types,
                    default=doc_types,
                    help="表示するドキュメントタイプを選択"
                )
            
            with col2:
                # 並び替え基準
                sort_by = st.selectbox(
                    "並び替え基準",
                    options=[
                        "スコア（高い順）",
                        "スコア（低い順）",
                        "マッチ数（多い順）",
                        "マッチ数（少ない順）",
                        "ファイル名（昇順）",
                        "ファイル名（降順）",
                        "更新日時（新しい順）",
                        "更新日時（古い順）"
                    ],
                    help="検索結果の並び替え方法を選択"
                )
                
                # 表示件数
                results_per_page = st.number_input(
                    "表示件数",
                    min_value=5,
                    max_value=100,
                    value=10,
                    step=5,
                    help="1ページあたりの表示件数"
                )
        
        # フィルタリングと並び替えの適用
        filtered_docs = self._apply_result_filters(
            grouped_results,
            min_score=min_score,
            selected_types=selected_types
        )
        
        sorted_docs = self._sort_results(
            filtered_docs,
            sort_by=sort_by
        )
        
        # ページネーション
        total_pages = (len(sorted_docs) + results_per_page - 1) // results_per_page
        if total_pages > 1:
            current_page = st.selectbox(
                "ページ",
                options=range(1, total_pages + 1),
                format_func=lambda x: f"ページ {x}/{total_pages}"
            )
            start_idx = (current_page - 1) * results_per_page
            end_idx = start_idx + results_per_page
            display_docs = sorted_docs[start_idx:end_idx]
        else:
            display_docs = sorted_docs
        
        # 結果の表示
        for doc_name, doc_data in display_docs:
            with st.expander(
                f"📄 {doc_name} "
                f"(マッチ数: {doc_data['total_matches']}, "
                f"平均スコア: {doc_data['avg_score']:.2f})",
                expanded=True
            ):
                # ページごとの結果
                for page, page_results in sorted(doc_data["pages"].items()):
                    st.markdown(f"#### ページ {page}")
                    
                    for result in page_results:
                        self._render_enhanced_result_preview(result)
    
    def _get_document_types(self, grouped_results: Dict[str, Dict]) -> List[str]:
        """ドキュメントタイプの一覧を取得"""
        doc_types = set()
        for doc_name in grouped_results:
            doc_type = doc_name.split(".")[-1].upper()
            doc_types.add(doc_type)
        return sorted(list(doc_types))
    
    def _apply_result_filters(
        self,
        grouped_results: Dict[str, Dict],
        min_score: float,
        selected_types: List[str]
    ) -> List[tuple]:
        """検索結果にフィルターを適用"""
        filtered = []
        
        for doc_name, doc_data in grouped_results.items():
            # ドキュメントタイプのフィルタリング
            doc_type = doc_name.split(".")[-1].upper()
            if doc_type not in selected_types:
                continue
            
            # スコアによるフィルタリング
            if doc_data["avg_score"] < min_score:
                continue
            
            filtered.append((doc_name, doc_data))
        
        return filtered
    
    def _sort_results(
        self,
        filtered_docs: List[tuple],
        sort_by: str
    ) -> List[tuple]:
        """検索結果を指定された基準で並び替え"""
        if sort_by == "スコア（高い順）":
            return sorted(
                filtered_docs,
                key=lambda x: x[1]["avg_score"],
                reverse=True
            )
        elif sort_by == "スコア（低い順）":
            return sorted(
                filtered_docs,
                key=lambda x: x[1]["avg_score"]
            )
        elif sort_by == "マッチ数（多い順）":
            return sorted(
                filtered_docs,
                key=lambda x: x[1]["total_matches"],
                reverse=True
            )
        elif sort_by == "マッチ数（少ない順）":
            return sorted(
                filtered_docs,
                key=lambda x: x[1]["total_matches"]
            )
        elif sort_by == "ファイル名（昇順）":
            return sorted(filtered_docs, key=lambda x: x[0])
        elif sort_by == "ファイル名（降順）":
            return sorted(filtered_docs, key=lambda x: x[0], reverse=True)
        elif sort_by == "更新日時（新しい順）":
            return sorted(
                filtered_docs,
                key=lambda x: self.document_service.get_document_metadata(x[0])["last_modified"],
                reverse=True
            )
        else:  # "更新日時（古い順）"
            return sorted(
                filtered_docs,
                key=lambda x: self.document_service.get_document_metadata(x[0])["last_modified"]
            )
    
    def _render_enhanced_result_preview(self, result: Dict):
        """強化された検索結果のプレビュー表示"""
        # スコアに基づく色分け
        score = result.get("similarity", result.get("match_score", 0))
        score_color = (
            "green" if score > 0.8
            else "orange" if score > 0.5
            else "red"
        )
        
        # プレビューのスタイル設定
        st.markdown(f"""
        <style>
        .result-preview {{
            border-left: 4px solid {score_color};
            padding: 10px;
            margin: 10px 0;
            background-color: #f8f9fa;
            border-radius: 4px;
        }}
        .context-text {{
            font-family: monospace;
            background-color: #e9ecef;
            padding: 8px;
            border-radius: 4px;
            margin: 5px 0;
        }}
        .matched-text {{
            font-family: monospace;
            background-color: #fff3cd;
            padding: 8px;
            border-radius: 4px;
            margin: 5px 0;
        }}
        .metadata-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin: 10px 0;
        }}
        </style>
        """, unsafe_allow_html=True)
        
        # 結果の表示
        st.markdown(
            '<div class="result-preview">',
            unsafe_allow_html=True
        )
        
        # ヘッダー情報
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown(f"**📄 {result['file_name']}**")
        with col2:
            st.markdown(f"**ページ:** {result['page']}")
        with col3:
            st.markdown(f"**スコア:** {score:.2f}")
        
        # コンテキストの表示（改善版）
        if "context" in result:
            st.markdown("**前後のコンテキスト**")
            context = result["context"]
            query = st.session_state.get("last_query", "")
            
            if query:
                # クエリの前後でコンテキストを分割
                parts = context.split(query)
                if len(parts) > 1:
                    # 前のコンテキスト
                    st.markdown(
                        f'<div class="context-text">{parts[0]}</div>',
                        unsafe_allow_html=True
                    )
                    # マッチしたテキスト
                    st.markdown(
                        f'<div class="matched-text">{query}</div>',
                        unsafe_allow_html=True
                    )
                    # 後のコンテキスト
                    st.markdown(
                        f'<div class="context-text">{parts[1]}</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f'<div class="context-text">{context}</div>',
                        unsafe_allow_html=True
                    )
        
        # マッチしたテキストの表示（改善版）
        st.markdown("**マッチしたテキスト**")
        text = result["text"]
        query = st.session_state.get("last_query", "")
        similar_terms = result.get("similar_terms", [])
        
        if query or similar_terms:
            highlighted_text = text
            # クエリのハイライト
            if query:
                highlighted_text = highlighted_text.replace(
                    query,
                    f'<span style="background-color: #ffd700; padding: 2px;">{query}</span>'
                )
            # 類似語のハイライト
            for term in similar_terms:
                highlighted_text = highlighted_text.replace(
                    term,
                    f'<span style="background-color: #90ee90; padding: 2px;">{term}</span>'
                )
            st.markdown(
                f'<div class="matched-text">{highlighted_text}</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div class="matched-text">{text}</div>',
                unsafe_allow_html=True
            )
        
        # 詳細情報の表示（改善版）
        with st.expander("📋 詳細情報"):
            st.markdown('<div class="metadata-grid">', unsafe_allow_html=True)
            
            # 基本情報
            st.markdown("**基本情報**")
            st.json({
                "ファイル名": result["file_name"],
                "ページ": result["page"],
                "スコア": f"{score:.2f}",
                "タイプ": result.get("type", "unknown"),
                "更新日時": result.get("last_modified", "不明")
            })
            
            # マッチ情報
            if "matched_terms" in result or "similar_terms" in result:
                st.markdown("**マッチ情報**")
                match_info = {}
                if "matched_terms" in result:
                    match_info["マッチした用語"] = result["matched_terms"]
                if "similar_terms" in result:
                    match_info["類似語"] = result["similar_terms"]
                st.json(match_info)
            
            # 追加のメタデータ
            if "metadata" in result:
                st.markdown("**追加のメタデータ**")
                st.json(result["metadata"])
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # アクションボタン
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📄 PDFで表示", key=f"view_{result['file_name']}_{result['page']}"):
                self._show_pdf_preview(result)
        with col2:
            if st.button("📋 コピー", key=f"copy_{result['file_name']}_{result['page']}"):
                self._copy_to_clipboard(result)
        with col3:
            if st.button("⭐ ブックマーク", key=f"bookmark_{result['file_name']}_{result['page']}"):
                self._add_to_bookmarks(result)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def _show_pdf_preview(self, result: Dict):
        """PDFプレビューの表示"""
        try:
            pdf_data = self.document_service.get_page_preview(
                file_name=result["file_name"],
                page=result["page"]
            )
            st.image(pdf_data, caption=f"{result['file_name']} - ページ {result['page']}")
        except Exception as e:
            st.error(f"PDFプレビューの表示に失敗しました: {str(e)}")
    
    def _copy_to_clipboard(self, result: Dict):
        """テキストをクリップボードにコピー"""
        text = result.get("text", "")
        st.write("クリップボードにコピーしました！")
        st.session_state["clipboard"] = text
    
    def _add_to_bookmarks(self, result: Dict):
        """検索結果をブックマークに追加"""
        if "bookmarks" not in st.session_state:
            st.session_state.bookmarks = []
        
        bookmark = {
            "file_name": result["file_name"],
            "page": result["page"],
            "text": result.get("text", ""),
            "added_at": datetime.now().isoformat()
        }
        
        st.session_state.bookmarks.append(bookmark)
        st.write("ブックマークに追加しました！")
    
    def _render_export_options(self, results: Dict):
        """エクスポートオプションの表示"""
        with st.expander("📥 エクスポートオプション", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                export_format = st.selectbox(
                    "エクスポート形式",
                    ["CSV", "Excel", "PDF"],
                    key="export_format"
                )
            
            with col2:
                export_options = st.multiselect(
                    "エクスポート項目",
                    ["基本情報", "コンテキスト", "メタデータ", "分析情報"],
                    default=["基本情報", "メタデータ"]
                )
            
            if st.button("エクスポート", key="export_button"):
                export_data = self.search_service.export_results(
                    results=results["results"],
                    format=export_format.lower(),
                    options=export_options
                )
                
                st.download_button(
                    label=f"{export_format}でダウンロード",
                    data=export_data,
                    file_name=f"search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format.lower()}",
                    mime=f"application/{export_format.lower()}"
                )
    
    def _render_search_history(self):
        """検索履歴の表示"""
        if st.session_state.search_history:
            with st.expander("検索履歴"):
                for history in st.session_state.search_history[-5:]:
                    if st.button(
                        f"{history['query']} ({history['timestamp']})",
                        key=f"history_{history['timestamp']}"
                    ):
                        self._execute_search(
                            query=history["query"],
                            search_type=history.get("search_type", "hybrid"),
                            filters=history.get("filters", {})
                        )
    
    def _get_available_tags(self) -> List[str]:
        """利用可能なタグの取得"""
        # 実装は既存のコードに依存
        return ["重要", "レビュー済み", "要確認", "完了"]
    
    def render_file_upload(self):
        """ファイルアップロードインターフェースの表示"""
        st.write("### ファイルアップロード")
        
        # ドラッグ&ドロップエリア
        uploaded_files = st.file_uploader(
            "ファイルをドラッグ&ドロップまたはクリックしてアップロード",
            type=["pdf", "docx", "xlsx", "pptx"],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            # アップロードオプション
            with st.expander("アップロードオプション"):
                folder_path = st.text_input(
                    "フォルダパス",
                    value="/",
                    help="ドキュメントを保存するフォルダパス"
                )
                
                tags = st.multiselect(
                    "タグ",
                    self._get_available_tags(),
                    help="ドキュメントに付けるタグ"
                )
                
                metadata = st.text_area(
                    "メタデータ (JSON形式)",
                    value="{}",
                    help="追加のメタデータをJSON形式で入力"
                )
            
            # アップロードボタン
            if st.button("アップロード"):
                try:
                    # メタデータの解析
                    metadata_dict = json.loads(metadata)
                    
                    # ファイルのアップロード
                    files = [
                        {
                            "file_data": file.getvalue(),
                            "file_name": file.name
                        }
                        for file in uploaded_files
                    ]
                    
                    results = self.document_service.upload_multiple_documents(
                        files=files,
                        folder_path=folder_path,
                        tags={file.name: tags for file in uploaded_files},
                        metadata={file.name: metadata_dict for file in uploaded_files}
                    )
                    
                    # 結果の表示
                    for result in results:
                        if result["status"] == "success":
                            st.success(f"{result['file_name']} のアップロードに成功しました")
                        else:
                            st.error(f"{result['file_name']} のアップロードに失敗しました: {result['error']}")
                
                except json.JSONDecodeError:
                    st.error("メタデータのJSON形式が不正です")
                except Exception as e:
                    st.error(f"アップロード中にエラーが発生しました: {str(e)}") 