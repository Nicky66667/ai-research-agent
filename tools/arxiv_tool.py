import arxiv # access the arXiv paper database
import httpx # HTTP client to make requests
import tempfile
from pathlib import Path # handle filesystem path handling
from langchain_core.tools import tool
from rag.pipeline import RAGPipeline

"""
dataflow for arXiv API:

-> Paper metadata + PDF URL
    -> Download PDF binary via httpx
      -> Write to a temporary file
        -> RAGPipeline.add_pdf()
          -> Parse / chunk / vectorize
            -> Store in the vector database (_rag)
              -> rag_query() retrieves relevant chunks
                -> Return relevant chunks to the user
"""

# shared RAGPipeline instance
_rag = RAGPipeline()

def _download_and_ingest(paper, metadata: dict) -> int:
    """
    download PDF and feed into RAG Pipleine, return number of new chunks added.
    """

    paper_id = paper.entry_id.split("/")[-1]

    # skip already downloaded files
    if f"arxiv:{paper_id}" in _rag.loaded_ids:
        return 0

    try:
        # use temp dir to store PDFs, auto-clean after function returns
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "paper.pdf"

            # download PDF (30s time-out)
            response = httpx.get(
                paper.pdf_url,
                follow_redirects=True,
                timeout=30
            )

            response.raise_for_status() # if status code is not 200, raise exception
            pdf_path.write_bytes(response.content) # write downloaded binary PDF content to file

            return _rag.add_pdf(str(pdf_path), metadata) # Process PDF: parse, chunk, embed, write to vector DB, return chunk count.

    # print error log
    except Exception as e:
        print(f"[arxiv_tool] Failed to download {paper.title}:{e}")
        return 0


@tool # Register as a LangChain tool
def arxiv_search(query:str,max_results:int=3) -> str:
    """
    Search arXiv for academic papers on a topic.
    Use this to find relevant research papers and auto add them to the knowledge base.

    Args:
        query: Research keywords (in English)
        max_results: Number of papers to retrieve (default 3, max 5)
    """

    max_results = min(max_results, 5)

    client = arxiv.Client() # client for interacting with arxiv API

    search = arxiv.Search(  # Define a search query for arXiv papers
        query = query,
        max_results = max_results,
        sort_by = arxiv.SortCriterion.Relevance
    )

    # use client to send request of searching query
    try:
        results = list(client.results(search))
    except Exception as e:
        return f"Arxiv search temporarily unavailable: {str(e)}. Try again later or use web_search instead."

    if not results:
        return f"No papers found for query:{query}"

    summaries = []

    # format paper's info
    for paper in results:
        paper_id = paper.entry_id.split("/")[-1] # # https://arxiv.org/abs/2401.12345 -> 2401.12345
        metadata = {
            "source_id" : f"arxiv:{paper_id}",
            "title":paper.title,
            "authors":",".join(a.name for a in paper.authors[:3]),
            "year": paper.published.year
        }

        # download PDF and add it to RAD knowledge base
        chunk_count = _download_and_ingest(paper, metadata)

        summaries.append(
            f"Title:{paper.title}\n"
            f"Authors：{metadata['authors']}({metadata['year']})\n"
            f"ArXiv ID:{paper_id}\n"
            f"Abstract:{paper.summary[:400]}...\n"
            f"Status:{chunk_count} chunks added to knowledge base"
        )

    return "\n\n --- \n\n".join(summaries)

@tool
def rag_query(query:str, top_k:int=5) -> str:
    """
    Query the local knowledge base built from downloaded papers.
    Use AFTER arxiv_search has ingested papers.

    Returns relevant text chunks with source citations.

    Args:
        query: Question to search in the knowledge base
        top_k: Number of chunks to retrieve (default 5)
    """

    results = _rag.query(query, top_k = top_k)

    if not results:
        return "Knowledge base is empty. Please run arxiv_search first."

    formatted = []

    for r in results: # each r -> { "title": ..., "authors": ..., ...}
        formatted.append(
            f"[{r['title']} - {r['authors']} ({r['year']})]"
            f"Relevance:{r['score']}\n"
            f"Content:{r['text'][:600]}..."
        )

    return "\n\n---\n\n".join(formatted)