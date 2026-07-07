"""
Sentence-BERT + FAISS — duplicate detection via semantic similarity.
"""
import json
import numpy as np
from pathlib import Path
from backend.config import settings

_sbert = None
_index = None
_metadata = None


def get_index():
    """Load and cache FAISS index and SBERT model."""
    global _sbert, _index, _metadata
    if _sbert is not None:
        return _sbert, _index, _metadata

    index_path = Path(settings.FAISS_INDEX_PATH)
    meta_path = Path(settings.FAISS_METADATA_PATH)

    if not index_path.exists():
        print(f"WARNING: FAISS index not found at {index_path}")
        return None, None, []

    import faiss
    from sentence_transformers import SentenceTransformer

    _sbert = SentenceTransformer("all-MiniLM-L6-v2")
    _index = faiss.read_index(str(index_path))

    if meta_path.exists():
        with open(meta_path) as f:
            _metadata = json.load(f)
    else:
        _metadata = []

    return _sbert, _index, _metadata


def find_duplicates(text: str, top_k: int = 3) -> list:
    """Find top-k most similar known fake posts."""
    sbert, index, metadata = get_index()
    if sbert is None or index is None:
        return []

    embedding = sbert.encode([text], normalize_embeddings=True).astype(np.float32)
    distances, indices = index.search(embedding, k=top_k)

    results = []
    for i in range(top_k):
        idx = int(indices[0][i])
        similarity = float(distances[0][i])
        excerpt = metadata[idx].get("text", "") if idx < len(metadata) else ""
        results.append({
            "similarity": similarity,
            "excerpt": excerpt,
            "index": idx,
        })
    return results
