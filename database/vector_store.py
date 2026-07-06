from __future__ import annotations
from pathlib import Path
import chromadb
from services.splitter import TextChunk

class VectorStore:
    def __init__(self, db_path: Path, collection_name: str) -> None:
        db_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(db_path))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space":"cosine"},
        )

    def add_chunks(
        self,
        ids: list[str],
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None:
        if not chunks:
            return
        self.collection.add(
            ids=ids,
            documents=[chunk.text for chunk in chunks],
            metadatas=[chunk.metadata for chunk in chunks],
            embeddings=embeddings,
        )

    def delete_source(self, source_id: str) -> None:
        self.collection.delete(where={"source_id": source_id})

    def search(self, query_embedding: list[float], n_results: int = 5) -> list[dict[str, object]]:
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        rows: list[dict[str, object]] = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for row_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
            rows.append(
                {
                    "id": row_id,
                    "document": document,
                    "metadata": metadata or {},
                    "distance": float(distance),
                }
            )
        return rows
    
    def count(self) -> int:
        return self.collection.count()