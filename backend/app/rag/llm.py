class LLMClient:
    def generate_response(self, prompt: str, context: str | None = None) -> str:
        if context:
            return f"Based on context '{context[:50]}...': Answer to query '{prompt}'"
        return f"Response to '{prompt}'"
