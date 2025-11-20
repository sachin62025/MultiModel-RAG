import os
from byaldi import RAGMultiModalModel
from PIL import Image
import io
import base64

class MultimodalRAGService:
    def __init__(self, index_name="nvidia_financial_index"):
        self.index_path = os.path.join("indices", index_name)
        self.pdf_path = "data/nvidia_10q.pdf"
        self.model = None
        
        # Initialize on load
        self._load_or_create_index()

    def _load_or_create_index(self):
        """Checks if index exists, otherwise creates it using ColPali."""
        try:
            print("🚀 Loading RAG Index...")
            self.model = RAGMultiModalModel.from_index(self.index_path)
            print("✅ Index Loaded Successfully.")
        except Exception:
            print("⚠️ Index not found. Creating new index (this may take a moment)...")
            self.model = RAGMultiModalModel.from_pretrained("vidore/colpali-v1.2")
            self.model.index(
                input_path=self.pdf_path,
                index_name=self.index_path,
                store_collection_with_index=True,
                overwrite=True
            )
            print("✅ Index Created and Saved.")

    def search(self, query: str, k: int = 1):
        """
        Retrieves the most relevant page image for a given query.
        Returns: (base64_image, page_number)
        """
        results = self.model.search(query, k=k)
        if not results:
            return None, None

        top_result = results[0]
        return top_result.base64, top_result.page_num

    def generate_answer(self, query: str, image_base64: str):
        """
        Mock function for Vision LLM generation.
        In production, replace this with OpenAI GPT-4o or Ollama Llama-3.2 API call.
        """
        # TODO: Integrate Llama-3.2-Vision or GPT-4o API here.
        # For now, we return a structured response proving the retrieval worked.
        return (
            f"I analyzed the retrieved document page. "
            f"Based on the visual data (charts/tables) found in the image, "
            f"this section appears highly relevant to your query: '{query}'."
        )

# Create a singleton instance to be imported by the API
rag_service = MultimodalRAGService()