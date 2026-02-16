import numpy as np
from typing import List, Dict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class VectorMemory:
    def __init__(self, max_memories: int = 1000):
        self.max_memories = max_memories
        self.memories: List[Dict] = []
        self.vectorizer = TfidfVectorizer()
        self.memory_vectors = None
        
    def add_memory(self, memory: Dict):
        self.memories.append(memory)
        
        # If we exceed max memories, summarize old ones
        if len(self.memories) > self.max_memories:
            self._summarize_memories()
            
    def _summarize_memories(self):
        # Simple summarization: remove the oldest memories
        # In a real implementation, you would use LLM to summarize
        while len(self.memories) > self.max_memories * 0.8:
            self.memories.pop(0)
            
    def search_memories(self, query: str, top_k: int = 5) -> List[Dict]:
        if not self.memories:
            return []
            
        # Vectorize all memories and the query
        memory_texts = [mem["content"] for mem in self.memories]
        
        try:
            # Fit vectorizer and transform memories
            memory_vectors = self.vectorizer.fit_transform(memory_texts)
            
            # Transform query
            query_vector = self.vectorizer.transform([query])
            
            # Calculate similarities
            similarities = cosine_similarity(query_vector, memory_vectors).flatten()
            
            # Get top-k most similar memories
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            
            # Return memories with similarity scores
            results = []
            for idx in top_indices:
                if similarities[idx] > 0:
                    results.append({
                        "memory": self.memories[idx],
                        "similarity": float(similarities[idx])
                    })
                    
            return results
        except:
            # If vectorization fails, return recent memories
            return [{"memory": mem, "similarity": 0} for mem in self.memories[-top_k:]]