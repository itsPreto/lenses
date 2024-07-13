import numpy as np
from scipy.spatial.distance import cosine
import networkx as nx
import requests
import json
import os
import time

EMBEDDING_API_URL = "http://localhost:11434/api/embeddings"
CODE_EMBEDDING_MODEL = "unclemusclez/jina-embeddings-v2-base-code:q4"
CODEBASE_DB_PATH = "./assets/codebase_embeddings.db"
LLM_API_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "qwen2:7b"


class RaggedyRag:
    def __init__(self, embeddings_db, file_trees, full_graph_data, repos_graph_data):
        self.embeddings_db = embeddings_db
        self.file_trees = file_trees
        self.full_graph = self._create_graph_from_data(full_graph_data)
        self.repos_graph = self._create_graph_from_data(repos_graph_data)

    def _create_graph_from_data(self, graph_data):
        G = nx.DiGraph()
        for node in graph_data.get('nodes', []):
            G.add_node(node['id'], **node)
        for link in graph_data.get('links', []):
            G.add_edge(link['source'], link['target'])
        return G

    def query(self, user_query, top_k=5, max_depth=2):
        query_embedding = self.generate_embedding(user_query)
        initial_results = self._embedding_based_retrieval(query_embedding, top_k)

        print("\nTop initial results:")
        for key, similarity in initial_results:
            print(f"Similarity: {similarity:.4f} - {key}")

        expanded_results = self._traverse_and_collect(initial_results, max_depth)
        summaries = self._generate_summaries(expanded_results)
        final_summary = self._generate_final_summary(summaries)
        response = self._generate_response(user_query, final_summary)

        # Create a list of tuples (file_path, score) for the expanded results
        relevant_snippets = [(file_path, 1.0) for file_path in expanded_results]  # Using 1.0 as a placeholder score

        return response, relevant_snippets

    def generate_embedding(self, text):
        payload = json.dumps({"model": CODE_EMBEDDING_MODEL, "prompt": text})
        headers = {'Content-Type': 'application/json'}
        response = requests.post(EMBEDDING_API_URL, data=payload, headers=headers)
        return np.array(response.json()['embedding'])

    def _embedding_based_retrieval(self, query_embedding, top_k):
        results = []
        for key, embedding in self.embeddings_db.items():
            similarity = 1 - cosine(query_embedding, embedding)
            results.append((key, similarity))
        return sorted(results, key=lambda x: x[1], reverse=True)[:top_k]

    def _traverse_and_collect(self, initial_results, max_depth):
        expanded_results = set()
        for i, (key, similarity) in enumerate(initial_results, 1):
            file_path = key.split('|path:')[-1]
            print(f"Traversing from initial result {i}/{len(initial_results)}: {file_path}")
            self._dfs(file_path, max_depth, expanded_results)
        return list(expanded_results)

    def _dfs(self, node, depth, visited):
        if depth == 0 or node in visited:
            return
        visited.add(node)
        print(f"  Visited: {node}")
        for neighbor in self.full_graph.neighbors(node):
            self._dfs(neighbor, depth - 1, visited)

    def _generate_summaries(self, file_paths):
        summaries = []
        for i, file_path in enumerate(file_paths, 1):
            print(f"Generating summary for file {i}/{len(file_paths)}: {file_path}")
            snippet = self._get_snippet(file_path)
            summary = self._call_llm(f"Summarize the following code:\n{snippet}")
            summaries.append(f"Summary for {file_path}:\n{summary}")
        return summaries

    def _generate_final_summary(self, summaries):
        combined_summaries = "\n".join(summaries)
        return self._call_llm(f"Provide a concise summary of the following summaries:\n{combined_summaries}")

    def _generate_response(self, query, final_summary):
        return self._call_llm(f"""Based on the following summary of relevant code, answer the user's question:

Summary:
{final_summary}

User Question: {query}

Response:
""")

    def _get_snippet(self, file_path):
        file_info = self.file_trees.get(file_path, {})
        if file_info:
            content = ""
            for func in file_info.get('functions', []):
                content += f"Function: {func['name']}\n{func['body']}\n\n"
            return content[:1000]  # Return first 1000 characters
        return "Snippet not available"

    def _call_llm(self, prompt):
        payload = json.dumps({
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False
        })
        headers = {'Content-Type': 'application/json'}
        response = requests.post(LLM_API_URL, data=payload, headers=headers)
        return response.json()['response']






def loaded_graph(path):
    with open(path, 'r') as file:
        return json.load(file)

def load_file_trees():
    file_path = "./frontend/public/api/tree-node-data/file_trees.json"
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            return json.load(file)
    return {}



def load_embeddings_db():
    if os.path.exists(CODEBASE_DB_PATH):
        with open(CODEBASE_DB_PATH, "r") as file:
            return {k: np.array(v) for k, v in json.load(file).items()}
    return {}


def save_embeddings_db(embeddings_db):
    with open(CODEBASE_DB_PATH, "w") as file:
        json.dump({k: v.tolist() for k, v in embeddings_db.items()}, file)
