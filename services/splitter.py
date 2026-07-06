from __future__ import annotations
from dataclasses import dataclass
from services.loaders import LoadedDocument

@dataclass(frozen=True)
class TextChunk:
    text: str
    metadata: dict[str, str | int | float | bool]

class RecursiveTextSplitter:
    def __init__(self, chunk_size: int = 900, chunk_overlap: int = 150) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", ". ", " ", ""]

    def split_documents(self, documents: list[LoadedDocument]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for document in documents:
            pieces = self._split_text(document.text)
            for index, piece in enumerate(pieces):
                metadata = dict(document.metadata)
                metadata["chunk_index"] = index
                chunks.append(TextChunk(text=piece, metadata=metadata))
        return chunks

    def _split_text(self, text: str) -> list[str]:
        text = " ".join(text.split()) if "\n" not in text else text.strip()
        if len(text) <= self.chunk_size:
            return [text] if text else []
        
        pieces = self._recursive_split(text, self.separators)
        chunks: list[str] = []
        current = ""

        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            candidate = f"{current}{piece}".strip() if current else piece
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                    overlap = current[-self.chunk_overlap :].strip() if self.chunk_overlap else ""
                    overlap_candidate = f"{overlap}{piece}".strip() if overlap else piece
                    current = overlap_candidate if len(overlap_candidate) <= self.chunk_size else piece
                else:
                    chunks.append(piece)
                    current = ""
        
        if current:
            chunks.append(current)

        return chunks
    
    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]
        
        separator = separators[0]
        remaining = separators[1:]

        if separator == "":
            return [text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]
        if separator not in text:
            return self._recursive_split(text, remaining)
        
        pieces: list[str] = []
        for piece in text.split(separator):
            if len(piece) <= self.chunk_size:
                pieces.append(piece)
            else:
                pieces.extend(self._recursive_split(piece, remaining))
        return pieces
                    