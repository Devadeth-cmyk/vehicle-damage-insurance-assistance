class KnowledgeRetriever:
    def retrieve(self, query: str, top_k: int = 3) -> list[str]:
        return [
            f"Policy context chunk 1 for '{query}'",
            f"Policy context chunk 2 for '{query}'",
        ][:top_k]
