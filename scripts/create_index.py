"""
一次性脚本：在 OpenSearch Serverless 里创建向量索引。
只需要跑一次，索引建好之后就不用再跑了。
"""
import os
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

HOST = os.environ["OPENSEARCH_ENDPOINT"]  # xxxxx.us-east-1.aoss.amazonaws.com
REGION = os.environ.get("AWS_REGION", "us-east-1")
INDEX_NAME = "papers"

credentials = boto3.Session().get_credentials()
auth = AWSV4SignerAuth(credentials, REGION, "aoss")  # 注意 service 固定填 "aoss"

client = OpenSearch(
    hosts=[{"host": HOST, "port": 443}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=30,
)

index_body = {
    "settings": {"index.knn": True},
    "mappings": {
        "properties": {
            "embedding": {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                },
            },
            "text": {"type": "text"},
            "source_id": {"type": "keyword"},
            "title": {"type": "text"},
            "authors": {"type": "text"},
            "year": {"type": "integer"},
            "chunk_index": {"type": "integer"},
        }
    },
}

if not client.indices.exists(index=INDEX_NAME):
    client.indices.create(index=INDEX_NAME, body=index_body)
    print(f"index {INDEX_NAME} create successfully")
else:
    print(f"index {INDEX_NAME} existed，skip")