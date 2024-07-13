from flask import Flask, request, jsonify
from flask_cors import CORS
import networkx as nx
import numpy as np
from scipy.spatial.distance import cosine
import logging
from tqdm import tqdm
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial

# Import your custom modules
from app import (
    process_codebase, load_file_trees, load_embeddings_db, load_requirements_db,
    extended_retrieval, query_embeddings, build_dynamic_graph, process_full_graph, get_snippet
)

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load data
file_trees = load_file_trees()
code_embeddings_db = load_embeddings_db()
requirements_db = load_requirements_db()

# Create a ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=4)

@app.route('/test', methods=['GET'])
def test():
    logger.info("Test route accessed")
    return "Test route working!"

@app.route('/similarity-matrix', methods=['GET'])
async def get_similarity_matrix():
    logger.info("Received request for similarity matrix")
    loop = asyncio.get_event_loop()
    matrix = await loop.run_in_executor(executor, compute_similarity_matrix)
    logger.info("Sending response")
    return jsonify(matrix)

@app.route('/process', methods=['POST'])
async def process():
    try:
        data = request.get_json()
        root_dir = data.get('root_dir')
        if not root_dir:
            return jsonify({"error": "root_dir is required"}), 400

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, partial(process_codebase, root_dir))
        return jsonify({"message": "Codebase processing complete. Embeddings have been saved."}), 200
    except Exception as e:
        logger.error(f"Error in /process: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/query', methods=['POST'])
async def query():
    try:
        logger.info("Received request for /query")
        data = request.get_json()
        query_text = data.get('query')
        top_k = data.get('top_k', 5)
        if not query_text:
            return jsonify({"error": "query is required"}), 400

        initial_files = sorted(file_trees.keys())
        logger.info(f"initial_retrieval from /query: {initial_files}")

        loop = asyncio.get_event_loop()
        extended_files = await loop.run_in_executor(executor, partial(extended_retrieval, file_trees, initial_files, top_k))
        combined_file_trees = {k: file_trees[k] for k in extended_files}
        logger.info(f"extended_retrieval from /query: {combined_file_trees}")

        code_results, requirement_results = await loop.run_in_executor(
            executor,
            partial(query_embeddings, query_text, code_embeddings_db, requirements_db, combined_file_trees, top_k)
        )

        enhanced_results = []

        for result in code_results + requirement_results:
            key, similarity, node_tree, source = result
            logger.info(f"Processing result: {key}, source: {source}")
            snippets = []

            if source == 'code':
                path = key.split('|path:')[-1]
                node_tree = file_trees.get(path, None)
                logger.info(f"Node tree for {key}: {node_tree}")
                snippets = await loop.run_in_executor(executor, partial(get_snippets_for_file, node_tree))
            elif source == 'requirement':
                snippets = await loop.run_in_executor(executor, partial(get_snippets_for_requirement, node_tree))

            enhanced_results.append((key, similarity, snippets, source))

        logger.info(f"enhanced_results from /query: {enhanced_results}")
        return jsonify({"results": enhanced_results}), 200
    except Exception as e:
        logger.error(f"Error in /query: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/generate_dependency_graph', methods=['POST'])
async def generate_dependency_graph():
    try:
        data = request.get_json()
        top_k_results = data.get('top_k_results')
        file_paths = data.get('file_paths', [])

        if not top_k_results and not file_paths:
            return jsonify({"error": "Either top_k_results or file_paths is required"}), 400

        if not file_paths:
            file_paths = [result[0].split('|path:')[-1] for result in top_k_results]

        loop = asyncio.get_event_loop()
        graph_data = await loop.run_in_executor(
            executor,
            partial(process_full_graph, './project_multi_scale_embed/assets/file_trees.json')
        )
        logger.info(f"graph_data: {graph_data}")
        return jsonify({"graph": graph_data}), 200
    except Exception as e:
        logger.error(f"Error in /generate_dependency_graph: {str(e)}")
        return jsonify({"error": str(e)}), 500

def compute_similarity_matrix():
    logger.info("Starting similarity matrix computation")
    start_time = time.time()

    similarity_matrix = []

    total_requirements = len(requirements_db)
    logger.info(f"Processing {total_requirements} requirements")

    for i, (req_id, req_data) in enumerate(tqdm(requirements_db.items(), total=total_requirements, desc="Processing requirements")):
        req_description = req_data['data']['Description']
        req_embedding = np.array(req_data['embedding'])

        code_similarities = []
        for j, (code_key, code_embedding) in enumerate(code_embeddings_db.items()):
            similarity = 1 - cosine(req_embedding, code_embedding)
            code_similarities.append((code_key, similarity))

            if j % 1000 == 0:
                logger.info(f"Requirement {i+1}/{total_requirements}: Processed {j+1}/{len(code_embeddings_db)} code snippets")

        top_10_code = sorted(code_similarities, key=lambda x: x[1], reverse=True)[:10]

        row = {
            'requirement_id': req_id,
            'requirement_description': req_description,
            'code_snippets': [
                {
                    'code_key': code_key,
                    'similarity': float(similarity),
                    'snippet': get_snippet(file_trees.get(code_key.split('|path:')[-1]), code_key.split('|')[0])
                }
                for code_key, similarity in top_10_code
            ]
        }
        similarity_matrix.append(row)

        if (i + 1) % 10 == 0:
            logger.info(f"Processed {i+1}/{total_requirements} requirements")

    end_time = time.time()
    logger.info(f"Similarity matrix computation completed in {end_time - start_time:.2f} seconds")

    return similarity_matrix

def get_snippets_for_file(node_tree):
    if not node_tree:
        logger.error("Node tree is None or empty.")
        return []

    snippets = []
    if isinstance(node_tree, dict):
        functions = node_tree.get('functions', [])
    else:
        logger.error(f"Expected node_tree to be dict, got {type(node_tree).__name__}.")
        return []

    for func in functions:
        func_body = func.get('body', '')
        body_chunks = chunk_text(func_body) if func_body else []
        logger.debug(f"Processing function: {func.get('name')}, body chunks: {body_chunks}")
        for i, chunk in enumerate(body_chunks):
            chunk_name = f"{func.get('name', 'unknown')}_body_chunk_{i}"
            snippet = chunk[:200] + "..." if len(chunk) > 200 else chunk
            snippets.append({"name": chunk_name, "snippet": snippet})

    logger.info(f"Generated snippets: {snippets}")
    return snippets

def chunk_text(text, tokens_per_chunk=500):
    words = text.split()
    return [' '.join(words[i:i + tokens_per_chunk]) for i in range(0, len(words), tokens_per_chunk)]

def get_snippets_for_requirement(requirement_data):
    if not requirement_data:
        return []

    description = requirement_data.get('data', {}).get('Description', 'No description available')
    snippet = description[:200] + "..." if len(description) > 200 else description
    return [{"name": "Description", "snippet": snippet}]

if __name__ == '__main__':
    app.run(debug=True)
