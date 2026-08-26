"""
2.7 节本地测试脚本：验证 RAG Pipeline 能否正常向 OpenSearch 写入和检索数据。

运行前请确认以下环境变量已经在当前终端设置好：
    $env:OPENSEARCH_ENDPOINT = "你的endpoint（不带 https://）"
    $env:AWS_REGION = "us-east-1"
    $env:OPENAI_API_KEY = "你的 OpenAI Key"  （如果 rag/pipeline.py 里用到了 OpenAIEmbeddings）

运行方式（在项目根目录下）：
    python test_rag_pipeline.py
"""

from rag.pipeline import RAGPipeline

# 提示：这里用的是一个真实存在的本地 PDF 文件路径，请把下面这行换成你本地实际
# 存在的一个 PDF 文件路径，比如随便找一篇论文 PDF 放在项目根目录，改成对应文件名。
PDF_PATH = "../sample.pdf"

rag = RAGPipeline()

added_count = rag.add_pdf(
    PDF_PATH,
    {
        "source_id": "arxiv:test",
        "title": "Test Paper",
        "authors": "Someone",
        "year": 2024,
    },
)
print(f"新增 chunk 数: {added_count}")

results = rag.query("这篇论文的核心贡献是什么", top_k=3)

for r in results:
    print(r["score"], r["title"], r["text"][:50])