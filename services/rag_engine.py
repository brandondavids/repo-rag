from __future__ import annotations

from google import genai

from database.vector_store import VectorStore
from services.embeddings import LocalEmbeddingService

class RagEngine:
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: LocalEmbeddingService,
        gemini_api_key: str,
        model_name: str,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.client = genai.Client(api_key=gemini_api_key)
        self.model_name = model_name

    def retrieve(self, query: str, n_results: int = 5) -> list[dict[str, object]]:
        query_embedding = self.embedding_service.embed_query(query)
        return self.vector_store.search(query_embedding, n_results=n_results)
    
    def ask(self, query: str, n_results: int = 5) -> str:
        results = self.retrieve(query, n_results=n_results)
        if not results:
            return "I do not know. No relevant knowledge-base chunks were found."
        
        context = self._format_context(results)
        prompt_lines = [
            "You are Repo, a private personal knowledge assistant.",
            "",
            "You are a teacher yet a friend for the user, you are friendly and easygoing, likes to crack jokes and be sarcastic. Over time, you adapt your personality to the user.", 
            "Answer the user's question using only the provided context.",
            "If the context does not contain the answer, say you do not know.",
            "Cite sources inline using the source labels shown in the context, for example [notes.pdf p.3].",
            "Keep the answer concise and avoid inventing facts."
            "",
            "Context:",
            context,
            "",
            "Question:",
            query
        ]
        prompt = "\n".join(prompt_lines)

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )
        return response.text or "I do not know. The model returned an empty response."
    
    @staticmethod
    def _format_context(results: list[dict[str, object]]) -> str:
        blocks: list[str] = []
        for index, result in enumerate(results, start=1):
            metadata = result["metadata"]
            if not isinstance(metadata, dict):
                metadata = {}
            
            source = metadata.get("source", "unknown source")
            page = metadata.get("page")
            slide = metadata.get("slide")
            subject = metadata.get("subject")
            label = str(source)
            if page:
                label += f" p. {page}"
            if slide:
                label += f" slide {slide}"
            if subject:
                label += f" subject: {subject}"

            blocks.append(
                f"---\n"
                f"Chunk {index}\n"
                f"Source: {label}\n"
                f"Text:\n{result['document']}"
            )
        return "\n\n".join(blocks)