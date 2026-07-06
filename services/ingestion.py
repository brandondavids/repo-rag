from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from database.vector_store import VectorStore
from services.embeddings import LocalEmbeddingService
from services.loaders import SUPPORTED_EXTENSIONS, load_file
from services.splitter import RecursiveTextSplitter, TextChunk

@dataclass(frozen=True)
class IngestionResult:
    path: Path
    status: str
    chunks_added: int

class IngestionManager:
    def __init__(
        self,
        docs_source_dir: Path,
        manifest_path: Path,
        vector_store: VectorStore,
        embedding_service: LocalEmbeddingService,
        splitter: RecursiveTextSplitter,
    ) -> None:
        self.docs_source_dir = docs_source_dir
        self.manifest_path = manifest_path
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.splitter = splitter
        self.docs_source_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def ingest_directory(self) -> list[IngestionResult]:
        results: list[IngestionResult] = []
        for path in sorted(self.docs_source_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                results.append(self.ingest_file(path))
        return results
    
    def ingest_file(self, path: Path) -> IngestionResult:
        path = path.resolve()
        checksum = self._sha256(path)
        source_id = self._source_id(path)
        manifest = self._load_manifest()

        previous = manifest.get(source_id)
        if previous and previous.get("checksum") == checksum:
            return IngestionResult(path=path, status="unchanged", chunks_added=0)
        
        documents = load_file(path)
        for document in documents:
            document.metadata["source_id"] = source_id
            document.metadata["checksum"] = checksum

        chunks = self.splitter.split_documents(documents)
        chunk_ids = [f"{source_id}:{index}" for index in range(len(chunks))]
        embeddings = self.embedding_service.embed_documents([chunk.text for chunk in chunks])

        self.vector_store.delete_source(source_id)
        self.vector_store.add_chunks(chunk_ids, chunks, embeddings)

        manifest[source_id] = {
            "path": str(path),
            "checksum": checksum,
            "chunks": len(chunks),
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_manifest(manifest)

        status = "updated" if previous else "added"
        
        return IngestionResult(path=path, status=status, chunks_added=len(chunks))
    
    def status(self) -> dict[str, object]:
        manifest = self._load_manifest()
        return {
            "indexed_files": len(manifest),
            "chunks": self.vector_store.count(),
            "files": [entry["path"] for entry in manifest.values()],
        }
    
    def _load_manifest(self) -> dict[str, dict[str, object]]:
        if not self.manifest_path.exists():
            return {}
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))
    
    def _save_manifest(self, manifest: dict[str, dict[str, object]]) -> None:
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    
    @staticmethod
    def _source_id(path: Path) -> str:
        return hashlib.sha1(str(path).lower().encode("utf-8")).hexdigest()