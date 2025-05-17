import streamlit as st
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
from utils.vector_utils import hybrid_search
from utils.cache_utils import SnowflakeCache

def render_search_panel(
    cache: Optional[SnowflakeCache] = None,
    on_search: Optional[callable] = None
) -> Dict[str, Any]:
    """
    検索パネルコンポーネントをレンダリング
    
    Args:
        cache: キャッシュインスタンス
        on_search: 検索実行時のコールバック関数
    
    Returns:
        Dict[str, Any]: 検索パラメータ
    """
    # 検索モードの選択
    search_mode = st.radio(
        "検索モード",
        ["複数PDF検索", "個別PDF検索"],
        horizontal=True,
        key="search_mode"
    )
    
    # 検索タイプの選択
    search_type = st.selectbox(
        "検索タイプ",
        ["ハイブリッド検索", "ベクトル検索", "キーワード検索"],
        key="search_type"
    )
    
    # 検索クエリの入力
    query = st.text_input(
        "検索クエリ",
        key="search_query",
        help="検索したいキーワードや文章を入力してください"
    )
    
    # 検索オプション
    with st.expander("検索オプション", expanded=False):
        # スコア閾値
        score_threshold = st.slider(
            "スコア閾値",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.1,
            key="score_threshold"
        )
        
        # 検索対象のドキュメント
        if search_mode == "複数PDF検索":
            doc_types = st.multiselect(
                "ドキュメントタイプ",
                ["PDF", "テキスト", "表", "図"],
                default=["PDF"],
                key="doc_types"
            )
        else:
            selected_doc = st.selectbox(
                "対象ドキュメント",
                st.session_state.get("available_docs", []),
                key="selected_doc"
            )
        
        # 高度なオプション
        advanced_options = st.checkbox("高度なオプションを表示", key="show_advanced")
        if advanced_options:
            # 類似語の使用
            use_synonyms = st.checkbox("類似語を使用", value=True, key="use_synonyms")
            
            # ブール演算子の使用（キーワード検索の場合）
            if search_type == "キーワード検索":
                use_boolean = st.checkbox("ブール演算子を使用", value=False, key="use_boolean")
                if use_boolean:
                    st.info("使用可能な演算子: AND, OR, NOT, ()")
            
            # コンテキストウィンドウサイズ
            context_window = st.slider(
                "コンテキストウィンドウサイズ",
                min_value=100,
                max_value=1000,
                value=300,
                step=50,
                key="context_window"
            )
    
    # 検索ボタン
    search_params = {
        "mode": search_mode,
        "type": search_type,
        "query": query,
        "score_threshold": score_threshold,
        "doc_types": doc_types if search_mode == "複数PDF検索" else [selected_doc],
        "use_synonyms": use_synonyms if advanced_options else True,
        "use_boolean": use_boolean if advanced_options and search_type == "キーワード検索" else False,
        "context_window": context_window if advanced_options else 300
    }
    
    if st.button("検索", key="search_button", disabled=not query):
        if on_search:
            on_search(search_params)
        else:
            # デフォルトの検索処理
            results = perform_search(search_params, cache)
            st.session_state.search_results = results
            st.session_state.last_search_params = search_params
            st.rerun()
    
    return search_params

def perform_search(
    params: Dict[str, Any],
    cache: Optional[SnowflakeCache] = None
) -> List[Dict[str, Any]]:
    """
    検索を実行
    
    Args:
        params: 検索パラメータ
        cache: キャッシュインスタンス
    
    Returns:
        List[Dict[str, Any]]: 検索結果
    """
    try:
        # キャッシュキーの生成
        cache_key = f"search_{hash(json.dumps(params, sort_keys=True))}"
        
        # キャッシュから結果を取得
        if cache:
            cached_results = cache.get(cache_key)
            if cached_results:
                return cached_results
        
        # 検索の実行
        results = hybrid_search(
            query=params["query"],
            search_type=params["type"],
            score_threshold=params["score_threshold"],
            doc_types=params["doc_types"],
            use_synonyms=params.get("use_synonyms", True),
            use_boolean=params.get("use_boolean", False),
            context_window=params.get("context_window", 300)
        )
        
        # 結果をキャッシュに保存
        if cache:
            cache.set(cache_key, results)
        
        return results
    
    except Exception as e:
        st.error(f"検索中にエラーが発生しました: {str(e)}")
        return []

def render_search_filters(
    results: List[Dict[str, Any]],
    on_filter: Optional[callable] = None
) -> None:
    """
    検索結果のフィルタリングUIをレンダリング
    
    Args:
        results: 検索結果
        on_filter: フィルター適用時のコールバック関数
    """
    if not results:
        return
    
    st.subheader("フィルター")
    
    # スコアによるフィルタリング
    min_score = st.slider(
        "最小スコア",
        min_value=0.0,
        max_value=1.0,
        value=0.0,
        step=0.1,
        key="min_score"
    )
    
    # ドキュメントタイプによるフィルタリング
    doc_types = list(set(r.get("doc_type", "PDF") for r in results))
    selected_types = st.multiselect(
        "ドキュメントタイプ",
        doc_types,
        default=doc_types,
        key="filter_doc_types"
    )
    
    # 並び替え
    sort_by = st.selectbox(
        "並び替え",
        ["スコア（降順）", "スコア（昇順）", "マッチ数", "ファイル名", "更新日時"],
        key="sort_by"
    )
    
    # フィルターの適用
    if st.button("フィルターを適用", key="apply_filters"):
        filtered_results = apply_filters(results, min_score, selected_types, sort_by)
        if on_filter:
            on_filter(filtered_results)
        else:
            st.session_state.filtered_results = filtered_results
            st.rerun()

def apply_filters(
    results: List[Dict[str, Any]],
    min_score: float,
    doc_types: List[str],
    sort_by: str
) -> List[Dict[str, Any]]:
    """
    フィルターを適用
    
    Args:
        results: 検索結果
        min_score: 最小スコア
        doc_types: 選択されたドキュメントタイプ
        sort_by: 並び替え基準
    
    Returns:
        List[Dict[str, Any]]: フィルター適用後の結果
    """
    # フィルタリング
    filtered = [
        r for r in results
        if r.get("score", 0) >= min_score
        and r.get("doc_type", "PDF") in doc_types
    ]
    
    # 並び替え
    if sort_by == "スコア（降順）":
        filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
    elif sort_by == "スコア（昇順）":
        filtered.sort(key=lambda x: x.get("score", 0))
    elif sort_by == "マッチ数":
        filtered.sort(key=lambda x: len(x.get("matches", [])), reverse=True)
    elif sort_by == "ファイル名":
        filtered.sort(key=lambda x: x.get("filename", ""))
    elif sort_by == "更新日時":
        filtered.sort(key=lambda x: x.get("updated_at", datetime.min), reverse=True)
    
    return filtered 