from __future__ import annotations
from sentence_transformers import SentenceTransformer

class LocalEmbeddingService:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
    
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        
        vectors = self.model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()
    
    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]