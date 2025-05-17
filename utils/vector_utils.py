"""
ベクトル操作ユーティリティ

Snowflake VECTOR型を使用した効率的なベクトル検索
インデックスベースの類似度計算
キャッシュ管理
Cortex LLMによる類似語生成
"""

import streamlit as st
from typing import List, Dict, Optional, Union, Any
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import col, lit, array_construct
from snowflake.snowpark.types import VectorType, FloatType
import numpy as np
from datetime import datetime
import json
from config import SETTINGS
from utils.cache_utils import SnowflakeCache


def create_vector_index(table_name: str, vector_column: str, index_name: str) -> None:
    """
    ベクトルインデックスを作成
    
    Parameters:
    -----------
    table_name : str
        テーブル名
    vector_column : str
        ベクトルカラム名
    index_name : str
        インデックス名
    """
    session = get_active_session()
    
    # インデックスの作成
    create_index_sql = f"""
    CREATE OR REPLACE VECTOR INDEX {index_name}
    ON {table_name} ({vector_column})
    TYPE HNSW
    WITH (
        metric = 'cosine',
        dimension = 1024,
        ef_construction = 40,
        ef_search = 16
    )
    """
    
    try:
        session.sql(create_index_sql).collect()
        print(f"ベクトルインデックス {index_name} を作成しました")
    except Exception as e:
        print(f"インデックス作成中にエラー: {str(e)}")


@st.cache_data(ttl=SETTINGS["CACHE_EXPIRE"])
def embed_text(text_list: List[str]) -> List[List[float]]:
    """
    テキストリストをSnowflake Cortexでベクトル化
    
    Parameters:
    -----------
    text_list : list[str]
        ベクトル化するテキストのリスト
        
    Returns:
    --------
    list[list[float]]
        埋め込みベクトルのリスト
    """
    if not text_list:
        return []
    
    try:
        session = get_active_session()
        embeddings = session.cortex.embed(
            model=SETTINGS["MODEL_EMBED"],
            input=text_list
        )
        return embeddings
    except Exception as e:
        print(f"ベクトル化中にエラー: {str(e)}")
        return [[0.0] * 1024] * len(text_list)


def find_relevant_chunks(
    query_embedding: List[float],
    pdf_contents: List[Dict],
    top_n: int = 5,
    threshold: Optional[float] = None,
    use_index: bool = True
) -> List[Dict]:
    """
    関連するチャンクを検索（VECTOR型とインデックスを活用）
    
    Parameters:
    -----------
    query_embedding : list[float]
        クエリの埋め込みベクトル
    pdf_contents : list[dict]
        PDF内容の辞書リスト
    top_n : int, optional
        取得する結果数
    threshold : Optional[float], optional
        類似度閾値
    use_index : bool, optional
        インデックスを使用するかどうか
        
    Returns:
    --------
    list[dict]
        検索結果のリスト
    """
    session = get_active_session()
    
    # 一時テーブルに文書ベクトルをロード
    df = session.create_dataframe(
        [(c["file_name"], c["page"], c["embedding"]) for c in pdf_contents],
        schema=["file_name", "page", "vec"]
    )
    
    # VECTOR型に変換
    df = df.with_column("vec", col("vec").cast(VectorType(FloatType(), 1024)))
    
    # インデックスを使用する場合
    if use_index:
        try:
            # インデックスを使用した検索
            search_sql = f"""
            SELECT file_name, page, vec,
                   VECTOR_COSINE_SIMILARITY(vec, {query_embedding}::VECTOR) as similarity
            FROM {df.table_name}
            WHERE VECTOR_COSINE_SIMILARITY(vec, {query_embedding}::VECTOR) >= {threshold or SETTINGS["SIMILARITY_THRESHOLD"]}
            ORDER BY similarity DESC
            LIMIT {top_n}
            """
            results = session.sql(search_sql).collect()
        except Exception as e:
            print(f"インデックス検索中にエラー: {str(e)}")
            # フォールバック: 通常の検索
            results = _fallback_search(df, query_embedding, top_n, threshold)
    else:
        # 通常の検索
        results = _fallback_search(df, query_embedding, top_n, threshold)
    
    # 結果の整形
    return [
        {
            "file_name": r["FILE_NAME"],
            "page": r["PAGE"],
            "score": float(r["SIMILARITY"]),
            "embedding": r["VEC"]
        }
        for r in results
    ]


def _fallback_search(
    df: Any,
    query_embedding: List[float],
    top_n: int,
    threshold: Optional[float]
) -> List[Dict]:
    """
    フォールバック検索（インデックスを使用しない）
    
    Parameters:
    -----------
    df : Any
        Snowpark DataFrame
    query_embedding : list[float]
        クエリの埋め込みベクトル
    top_n : int
        取得する結果数
    threshold : Optional[float]
        類似度閾値
        
    Returns:
    --------
    list[dict]
        検索結果のリスト
    """
    # クエリベクトルをVECTOR型に変換
    query_vec = array_construct(*[lit(x) for x in query_embedding]).cast(VectorType(FloatType(), 1024))
    
    # 類似度計算と結果の取得
    results = df.with_column(
        "similarity",
        col("vec").cast(VectorType(FloatType(), 1024)).cosine_similarity(query_vec)
    ).filter(
        col("similarity") >= (threshold or SETTINGS["SIMILARITY_THRESHOLD"])
    ).order_by(
        col("similarity").desc()
    ).limit(top_n).collect()
    
    return results


def generate_similar_terms(query: str, num_terms: int = 3) -> List[str]:
    """
    Cortex LLMを使用して類似語を生成
    
    Parameters:
    -----------
    query : str
        元のクエリ
    num_terms : int
        生成する類似語の数
        
    Returns:
    --------
    list[str]
        生成された類似語のリスト
    """
    session = get_active_session()
    
    # プロンプトの作成
    prompt = f"""
    以下のクエリに関連する類似語を{num_terms}個生成してください。
    生成する類似語は、元のクエリと同じ文脈で使用できる単語やフレーズである必要があります。
    回答はJSON形式で、'similar_terms'キーに配列として返してください。
    
    クエリ: {query}
    """
    
    try:
        # Cortex LLMを使用して類似語を生成
        response = session.cortex.complete(
            model=SETTINGS["MODEL_COMPLETE"],
            prompt=prompt,
            temperature=0.7,
            max_tokens=100
        )
        
        # レスポンスの解析
        try:
            result = json.loads(response)
            similar_terms = result.get("similar_terms", [])
            # 元のクエリを除外
            similar_terms = [term for term in similar_terms if term.lower() != query.lower()]
            return similar_terms[:num_terms]
        except json.JSONDecodeError:
            # JSON形式でない場合は、テキストを分割して処理
            terms = response.split(",")
            terms = [term.strip() for term in terms if term.strip()]
            terms = [term for term in terms if term.lower() != query.lower()]
            return terms[:num_terms]
            
    except Exception as e:
        print(f"類似語生成中にエラー: {str(e)}")
        return []


def _expand_query_with_similar_terms(query: str, num_terms: int = 3) -> str:
    """
    クエリを類似語で展開
    
    Parameters:
    -----------
    query : str
        元のクエリ
    num_terms : int
        生成する類似語の数
        
    Returns:
    --------
    str
        展開されたクエリ
    """
    # 類似語の生成
    similar_terms = generate_similar_terms(query, num_terms)
    
    # クエリの展開
    expanded_terms = [query] + similar_terms
    
    # 重複を除去して結合
    return " OR ".join(f'"{term}"' for term in set(expanded_terms))


def _keyword_search(query: str, pdf_contents: List[Dict], top_n: int) -> List[Dict]:
    """
    キーワード検索（類似語対応版）
    
    Parameters:
    -----------
    query : str
        検索クエリ
    pdf_contents : list[dict]
        PDF内容の辞書リスト
    top_n : int
        取得する結果数
        
    Returns:
    --------
    list[dict]
        検索結果のリスト
    """
    session = get_active_session()
    
    # 類似語でクエリを展開
    expanded_query = _expand_query_with_similar_terms(query)
    
    # 一時テーブルにテキストをロード
    df = session.create_dataframe(
        [(c["file_name"], c["page"], c["text"]) for c in pdf_contents],
        schema=["file_name", "page", "text"]
    )
    
    # 全文検索の実行（類似語を含む）
    search_sql = f"""
    SELECT file_name, page, text,
           SCORE() as relevance,
           MATCHED_TERMS() as matched_terms
    FROM {df.table_name}
    WHERE CONTAINS(text, '{expanded_query}', FUZZY_MATCH = TRUE)
    ORDER BY relevance DESC
    LIMIT {top_n}
    """
    
    try:
        results = session.sql(search_sql).collect()
        return [
            {
                "file_name": r["FILE_NAME"],
                "page": r["PAGE"],
                "text": r["TEXT"],
                "score": float(r["RELEVANCE"]),
                "matched_terms": r["MATCHED_TERMS"],
                "type": "keyword",
                "original_query": query,
                "expanded_query": expanded_query
            }
            for r in results
        ]
    except Exception as e:
        print(f"キーワード検索中にエラー: {str(e)}")
        return []


def hybrid_search(
    query: str,
    pdf_contents: List[Dict],
    top_n: int = 5,
    threshold: Optional[float] = None,
    use_similar_terms: bool = True
) -> List[Dict]:
    """
    ハイブリッド検索（キーワード + ベクトル）
    
    Parameters:
    -----------
    query : str
        検索クエリ
    pdf_contents : list[dict]
        PDF内容の辞書リスト
    top_n : int, optional
        取得する結果数
    threshold : Optional[float], optional
        類似度閾値
    use_similar_terms : bool, optional
        類似語検索を使用するかどうか
        
    Returns:
    --------
    list[dict]
        検索結果のリスト
    """
    # クエリのベクトル化
    query_embedding = embed_text([query])[0]
    
    # ベクトル検索
    vector_results = find_relevant_chunks(
        query_embedding,
        pdf_contents,
        top_n=top_n,
        threshold=threshold
    )
    
    # キーワード検索（類似語対応）
    keyword_results = _keyword_search(
        query,
        pdf_contents,
        top_n=top_n
    ) if use_similar_terms else []
    
    # 結果の統合と重複除去
    combined_results = _merge_search_results(vector_results, keyword_results, top_n)
    
    # 検索メタデータの追加
    for result in combined_results:
        result["search_metadata"] = {
            "original_query": query,
            "search_type": "hybrid",
            "use_similar_terms": use_similar_terms,
            "timestamp": datetime.now().isoformat()
        }
    
    return combined_results


def _merge_search_results(
    vector_results: List[Dict],
    keyword_results: List[Dict],
    top_n: int
) -> List[Dict]:
    """
    検索結果の統合
    
    Parameters:
    -----------
    vector_results : list[dict]
        ベクトル検索結果
    keyword_results : list[dict]
        キーワード検索結果
    top_n : int
        取得する結果数
        
    Returns:
    --------
    list[dict]
        統合された検索結果
    """
    # 結果の重複除去とスコアの正規化
    seen = set()
    merged_results = []
    
    for result in vector_results + keyword_results:
        key = (result["file_name"], result["page"])
        if key not in seen:
            seen.add(key)
            # スコアの正規化（0-1の範囲に）
            if "score" in result:
                result["normalized_score"] = min(1.0, max(0.0, result["score"]))
            merged_results.append(result)
    
    # スコアでソート
    merged_results.sort(key=lambda x: x.get("normalized_score", 0), reverse=True)
    
    return merged_results[:top_n]


def search_in_tables_and_figures(
    query: str,
    pdf_contents: List[Dict],
    top_n: int = 3
) -> List[Dict]:
    """
    テーブルと図表の検索
    
    Parameters:
    -----------
    query : str
        検索クエリ
    pdf_contents : list[dict]
        PDF内容の辞書リスト
    top_n : int, optional
        取得する結果数
        
    Returns:
    --------
    list[dict]
        検索結果のリスト
    """
    session = get_active_session()
    
    # テーブルと図表のデータを一時テーブルにロード
    table_data = []
    figure_data = []
    
    for content in pdf_contents:
        if "tables" in content:
            for table in content["tables"]:
                table_data.append({
                    "file_name": content["file_name"],
                    "page": table["page"],
                    "table_num": table["table_num"],
                    "data": json.dumps(table["data"], ensure_ascii=False),
                    "bbox": json.dumps(table["bbox"])
                })
        
        if "figures" in content:
            for figure in content["figures"]:
                figure_data.append({
                    "file_name": content["file_name"],
                    "page": figure["page"],
                    "figure_num": figure["figure_num"],
                    "bbox": json.dumps(figure["bbox"])
                })
    
    # テーブル検索
    table_df = session.create_dataframe(table_data)
    table_results = []
    if not table_df.is_empty():
        table_sql = f"""
        SELECT file_name, page, table_num, data, bbox,
               SCORE() as relevance
        FROM {table_df.table_name}
        WHERE CONTAINS(data, '{query}')
        ORDER BY relevance DESC
        LIMIT {top_n}
        """
        try:
            table_results = session.sql(table_sql).collect()
        except Exception as e:
            print(f"テーブル検索中にエラー: {str(e)}")
    
    # 図表検索（メタデータベース）
    figure_df = session.create_dataframe(figure_data)
    figure_results = []
    if not figure_df.is_empty():
        figure_sql = f"""
        SELECT file_name, page, figure_num, bbox,
               SCORE() as relevance
        FROM {figure_df.table_name}
        WHERE CONTAINS(bbox::string, '{query}')
        ORDER BY relevance DESC
        LIMIT {top_n}
        """
        try:
            figure_results = session.sql(figure_sql).collect()
        except Exception as e:
            print(f"図表検索中にエラー: {str(e)}")
    
    # 結果の整形
    results = []
    
    for r in table_results:
        results.append({
            "file_name": r["FILE_NAME"],
            "page": r["PAGE"],
            "type": "table",
            "table_num": r["TABLE_NUM"],
            "data": json.loads(r["DATA"]),
            "bbox": json.loads(r["BBOX"]),
            "score": float(r["RELEVANCE"])
        })
    
    for r in figure_results:
        results.append({
            "file_name": r["FILE_NAME"],
            "page": r["PAGE"],
            "type": "figure",
            "figure_num": r["FIGURE_NUM"],
            "bbox": json.loads(r["BBOX"]),
            "score": float(r["RELEVANCE"])
        })
    
    return results


def calculate_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    2つのベクトル間のコサイン類似度を計算
    
    Parameters:
    -----------
    vec1 : list[float]
        ベクトル1
    vec2 : list[float]
        ベクトル2
        
    Returns:
    --------
    float
        コサイン類似度（-1から1の間）
    """
    try:
        session = get_active_session()
        # SnowflakeのVECTOR型を使用して類似度を計算
        result = session.sql(f"""
            SELECT VECTOR_COSINE_SIMILARITY(
                {vec1}::VECTOR,
                {vec2}::VECTOR
            ) as similarity
        """).collect()
        return float(result[0]["SIMILARITY"])
    except Exception as e:
        print(f"類似度計算中にエラー: {str(e)}")
        # フォールバック: NumPyを使用した計算
        try:
            vec1_np = np.array(vec1)
            vec2_np = np.array(vec2)
            return float(np.dot(vec1_np, vec2_np) / (np.linalg.norm(vec1_np) * np.linalg.norm(vec2_np)))
        except:
            return 0.0
