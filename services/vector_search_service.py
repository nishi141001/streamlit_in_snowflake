class VectorSearchService:
    def __init__(self, session: Session):
        self.session = session
        self.vector_dim = 384  # デフォルトのベクトル次元数
        self._init_tables()

    def _init_tables(self):
        """必要なテーブルの初期化"""
        try:
            # 既存のテーブルを個別に削除
            self.session.sql("DROP TABLE IF EXISTS vector_search_results").collect()
            self.session.sql("DROP TABLE IF EXISTS vector_search_queries").collect()

            # ベクトル検索クエリテーブルを個別に作成
            create_vector_search_queries = """
            CREATE TABLE IF NOT EXISTS vector_search_queries (
                query_id STRING,
                user_id STRING,
                query_text STRING,
                query_vector VECTOR(FLOAT, {self.vector_dim}),
                timestamp TIMESTAMP,
                filters VARIANT,
                PRIMARY KEY (query_id)
            )
            """
            self.session.sql(create_vector_search_queries).collect()

            # ベクトル検索結果テーブルを個別に作成
            create_vector_search_results = """
            CREATE TABLE IF NOT EXISTS vector_search_results (
                result_id STRING,
                query_id STRING,
                doc_id STRING,
                chunk_id STRING,
                similarity FLOAT,
                rank INTEGER,
                metadata VARIANT,
                PRIMARY KEY (result_id),
                FOREIGN KEY (query_id) REFERENCES vector_search_queries(query_id)
            )
            """
            self.session.sql(create_vector_search_results).collect()

        except Exception as e:
            print(f"テーブル初期化中にエラー: {str(e)}")
            raise 