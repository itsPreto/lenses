import os
import glob
import sys
import re
import csv
import json
import argparse
import pathlib
import tiktoken
import logging
import networkx as nx
import numpy as np
import requests
from scipy.spatial.distance import cosine
from tree_sitter import Parser, Language
from rag import RaggedyRag, load_embeddings_db, load_file_trees, loaded_graph


# custom written ast post-processing utils (there are prob better/cleaner ways of doing this?)
# the intent is to make retrieving file properties on demand a brainless & quick task.
# maybe there's a totally big brain way of looking at this in which case pls lmk!
from utils.grammar.ast_traversers import (
    TreeNode, traverse_tree_js, traverse_tree_go, traverse_tree_go, traverse_tree_java,
    traverse_tree_kt, traverse_tree_python, traverse_tree_swift, traverse_tree_cpp,traverse_tree_c,
)

# Constants
EMBEDDING_API_URL = "http://localhost:11434/api/embeddings"
LLM_API_URL = "http://localhost:11434/api/generate"
CODEBASE_DB_PATH = "./assets/codebase_embeddings.db"
REQUIREMENTS_DB_PATH = "./assets/requirements_embeddings.db"
CODE_EMBEDDING_MODEL = "unclemusclez/jina-embeddings-v2-base-code:q4"
REQUIREMENT_EMBEDDING_MODEL = "unclemusclez/jina-embeddings-v2-base-code:q4"
logging.basicConfig(level=logging.DEBUG)

LANGUAGE_SO_PATH = "./utils/grammar/language_grammars.so"
LANGUAGE_DATA = {
    "java": ("java", [".java"]),
    "kotlin": ("kotlin", [".kt"]),
    "javascript": ("javascript", [".js", ".jsx"]),
    "go": ("go", [".go"]),
    "python": ("python", [".py"]),
    "cpp": ("cpp", [".cpp", ".cc", ".cxx"]),
    "c": ("c", [".c"]),
    "swift": ("swift", [".swift"])}

# Initialize tiktoken encoder
enc = tiktoken.encoding_for_model("gpt-4")

def count_tokens(text):
    return len(enc.encode(text))

########################################################################################################################
#################################### THIS SECTION OF THE CODE DOES THE FOLLOWING #######################################
########################################################################################################################
#                                                                                                                      #
#     1. Crawl and parse the codebases                                                                                 #
#     2. Generate source code ASTs                                                                                     #
#     3. Traverse ASTs, extrect properties and store to custom TreeNode structure.                                     #
#         a. file_trees.json: dictionary containing all the parsed properties from each file.                          #
#     4. Create code-centric, strucurally coherent embeddings                                                          #
#     5. Compute various levels of dependency closure graphs:                                                          #
#         a. repos_graph.json: a repo level view of the relationship between all the repos processed (repo-to-repo).   #                                                                             #
#         b. <REPO_NAME>.json: invididual view of the interdependenies across a single processed repo (file-to-file).  #
#         c. full_graph.json: a world view of all the interdependencies across all the repos processed (file-to-file). #
#         d. repos_readme.json: a repo level view that maps the README docs to each other based on [repos_graph.json]. #
#                                                                                                                      #
########################################################################################################################
#################################### THIS SECTION OF THE CODE DOES THE FOLLOWING #######################################
########################################################################################################################

def create_language(name):
    return Language(LANGUAGE_SO_PATH, name)

def init_tree_sitter_languages():
    global extension_to_language
    extension_to_language = {
        lang: (create_language(data[0]), data[1])
        for lang, data in LANGUAGE_DATA.items()
    }

def generate_embeddings(text, model=CODE_EMBEDDING_MODEL):
    payload = json.dumps({"model": model, "prompt": text})
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(EMBEDDING_API_URL, data=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        embeddings = result.get('embedding')
        if not embeddings:
            logging.error(f"Invalid embedding format received. Expected 768 dimensions, got {len(embeddings) if embeddings else 'None'}")
            return None
        return np.array(embeddings, dtype=np.float32)
    except Exception as e:
        logging.error(f"Error in generate_embeddings: {str(e)}")
        return None

def query_embeddings(query_text, code_embeddings_db, requirements_db, file_trees, top_k=5):
    file_trees = load_file_trees()
    query_embedding = generate_embeddings(query_text)
    if query_embedding is None:
        return [], []

    code_results = []
    requirement_results = []

    # Query code embeddings
    for key, embedding in code_embeddings_db.items():
        if embedding is not None:
            similarity = 1 - cosine(query_embedding, embedding)
            file_path = key.split('|path:')[-1]
            snippet = get_snippet(file_trees.get(file_path), key.split('|')[0])
            code_results.append((key, similarity, snippet, "code"))

    # Query requirements embeddings
    for requirement_id, data in requirements_db.items():
        embedding = np.array(data.get("embedding", []))
        if embedding.size == 0:
            continue
        similarity = 1 - cosine(query_embedding, embedding)
        requirement_results.append((requirement_id, similarity, data, "requirement"))

    code_results.sort(key=lambda x: x[1], reverse=True)
    requirement_results.sort(key=lambda x: x[1], reverse=True)

    return code_results[:top_k], requirement_results[:top_k]



def layered_query_embeddings(query_text, embeddings_db, file_trees, top_k=5, min_repos=2, merge_mode='overall'):
    query_embedding = generate_embeddings(query_text)
    if query_embedding is None:
        return {}

    all_results = []
    for key, embedding in embeddings_db.items():
        if embedding is not None:
            similarity = 1 - cosine(query_embedding, embedding)
            file_path = key.split('|path:')[-1]
            repo_name = file_path.split(os.sep)[0]
            snippet = get_snippet(file_trees.get(file_path), key.split('|')[0])
            all_results.append((key, similarity, snippet, repo_name))

    all_results.sort(key=lambda x: x[1], reverse=True)

    top_results = []
    unique_repos = set()
    for result in all_results:
        top_results.append(result)
        unique_repos.add(result[3])
        if len(top_results) >= top_k and len(unique_repos) >= min_repos:
            break

    final_results = top_results[:top_k]

    return organize_results(file_trees, final_results, top_k)



def find_imported_elements(import_stmt, file_trees):
    imported_elements = []
    for file_path, node_tree in file_trees.items():
        if isinstance(node_tree, dict):
            class_names = node_tree.get('class_names', [])
            functions = node_tree.get('functions', [])
            properties = node_tree.get('property_declarations', [])
        else:
            class_names = node_tree.class_names
            functions = node_tree.functions
            properties = node_tree.property_declarations

        # Check if the import statement matches any class, function, or property
        for class_name in class_names:
            if import_stmt in class_name:
                imported_elements.append(f"class:{class_name}|{file_path}")

        for func in functions:
            if import_stmt == func.name:
                imported_elements.append(f"function:{func.name}|{file_path}")

        for prop in properties:
            if import_stmt in prop:
                imported_elements.append(f"property:{prop}|{file_path}")

    return imported_elements


def get_snippet(node_tree, element_type):
    if not node_tree:
        logging.error("Node tree is None or empty.")
        return "Snippet not available"

    parts = element_type.split(":")
    if len(parts) < 2:
        logging.error(f"Element type '{element_type}' does not have a second part.")
        return "Snippet not available"

    element_prefix = parts[0]
    element_name = parts[1]

    if isinstance(node_tree, dict):
        functions = node_tree.get('functions', [])
        class_names = node_tree.get('class_names', [])
        property_declarations = node_tree.get('property_declarations', [])
        imports = node_tree.get('imports', [])
    else:
        functions = node_tree.functions
        class_names = node_tree.class_names
        property_declarations = node_tree.property_declarations
        imports = node_tree.imports

    if element_prefix == "function":
        for func in functions:
            if func.get('name') == element_name:
                func_body = func.get('body', '')
                return func_body[:200] + "..." if len(func_body) > 200 else func_body
    elif element_prefix == "class":
        if element_name in class_names:
            return f"class {element_name}"
    elif element_prefix == "property":
        for prop in property_declarations:
            if element_name in prop:
                return prop
    elif element_prefix == "import":
        for imp in imports:
            if element_name in imp:
                return imp
            # Check if the element_name is a part of a longer import statement
            if any(part in imp for part in element_name.split('.')):
                return imp

    logging.warning(f"No matching element found for element type '{element_type}'.")
    return "Snippet not available"


def chunk_text(text, tokens_per_chunk=500):
    words = text.split()
    return [' '.join(words[i:i+tokens_per_chunk]) for i in range(0, len(words), tokens_per_chunk)]

def manage_embeddings(tree_node, file_path, embeddings_db):
    for class_name in tree_node.class_names:
        key = f"class:{class_name}|path:{file_path}"
        embeddings_db[key] = generate_embeddings(f"{key}: {class_name}")

    for import_stmt in tree_node.imports:
        key = f"import:{import_stmt}|path:{file_path}"
        embeddings_db[key] = generate_embeddings(f"{key}: {import_stmt}")

    for export_stmt in tree_node.exports:
        key = f"export:{export_stmt}|path:{file_path}"
        embeddings_db[key] = generate_embeddings(f"{key}: {export_stmt}")

    for prop in tree_node.property_declarations:
        key = f"property:{prop}|path:{file_path}"
        embeddings_db[key] = generate_embeddings(f"{key}: {prop}")

    for func in tree_node.functions:
        key = f"function:{func.name}|class:{func.class_name}|path:{file_path}"
        embeddings_db[key] = generate_embeddings(f"{key}: {func.name}")

        body_chunks = chunk_text(func.body)
        for i, chunk in enumerate(body_chunks):
            key = f"function_{func.name}_body_chunk_{i}|class:{func.class_name}|path:{file_path}"
            embeddings_db[key] = generate_embeddings(f"{key}: {chunk}")

def process_code_string(code_string, language, file_path):
    parser = Parser()
    parser.set_language(language)
    tree = parser.parse(bytes(code_string, "utf8"))
    root_node = tree.root_node

    node_tree = TreeNode(file_path=file_path)

    if language.name == "java":
        traverse_tree_java(root_node, bytes(code_string, "utf8"), node_tree, language)
    elif language.name == "kotlin":
        traverse_tree_kt(root_node, bytes(code_string, "utf8"), node_tree, language)
    elif language.name == "javascript":
        traverse_tree_js(root_node, bytes(code_string, "utf8"), node_tree, language)
    elif language.name == "go":
        traverse_tree_go(root_node, bytes(code_string, "utf8"), node_tree, language)
    elif language.name == "python":
        traverse_tree_python(root_node, bytes(code_string, "utf8"), node_tree, language)
    elif language.name == "cpp":
        traverse_tree_cpp(root_node, bytes(code_string, "utf8"), node_tree, language)
    elif language.name == "c":
        traverse_tree_c(root_node, bytes(code_string, "utf8"), node_tree, language)
    elif language.name == "swift":
        traverse_tree_swift(root_node, bytes(code_string, "utf8"), node_tree, language)
    else:
        raise ValueError(f"Unsupported language: {language.name}")

    return node_tree

def init_tree_sitter(root_dir):
    modules = {}
    file_trees = {}
    file_sizes = {}
    package_names = {}
    directories = [os.path.join(root_dir, d) for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d)) and not should_skip_path(os.path.join(root_dir, d))]
    total_directories = len(directories)
    processed_directories = 0
    readme_info_list = []
    global embeddings_db
    embeddings_db = {}

    for dir_name in directories:
        repo_path = os.path.join(root_dir, dir_name)
        if os.path.isdir(repo_path):
            module_dir = dir_name
            processed_directories += 1
            logging.info(f"Processing {dir_name}: {(processed_directories / total_directories) * 100:.2f}% complete")
            process_repository(repo_path, modules, file_trees, file_sizes, package_names, readme_info_list)

    save_file_trees(file_trees)
    save_embeddings_db(embeddings_db)

    json_data = process_full_graph("./frontend/public/api/tree-node-data/file_trees.json")

    with open("./frontend/public/api/graph-data/full_graph.json", "w") as outfile:
        json.dump(json_data, outfile, indent=4, sort_keys=True)

    with open("./assets/repos_readme.json", 'w', encoding='utf-8') as file:
        json.dump(readme_info_list, file, ensure_ascii=False, indent=4)

    generate_individual_user_jsons(json_data)
    generate_root_level_json(json_data)

    return modules, file_sizes, package_names, file_trees, json_data

def should_skip_path(path):
    skip_directories = [
        'node_modules', 'build', 'dist', 'out', 'bin', '.git', '.svn', '.vscode',
        '__pycache__', '.idea', 'obj', 'lib', 'vendor', 'target', '.next', 'pkg',
        'venv', '.tox', 'wheels', 'Debug', 'Release', 'deps'
    ]
    return any(skip_dir in path.split(os.path.sep) for skip_dir in skip_directories)
def save_file_trees(file_trees):
    with open("./frontend/public/api/tree-node-data/file_trees.json", "w") as file:
        json.dump({k: v.to_dict() for k, v in file_trees.items()}, file, indent=4)

def extract_component_name(file_path):
    match = re.search(r"/([^/]+)/(?:app/)?src/", file_path)
    if match:
        return match.group(1)
    return None
def process_codebase(root_directory):
    init_tree_sitter_languages()
    modules, file_sizes, package_names, file_trees, json_data = init_tree_sitter(root_directory)
    save_file_trees(file_trees)
    save_embeddings_db(embeddings_db)
    return "Codebase processing complete. Embeddings have been saved."


########################################################################################################################
#################################### CODE FOR QUERYING YOUR EMBEDDINGS DATABASE ########################################
########################################################################################################################
#                                                                                                                      #
# If you are running this for the first time you will need to index your repos first. Run the following:               #
#   > python3 tree_sit.py process --root_dir /path/to/your/folder/with/projects                                        #
#                                                                                                                      #
# once your codebase_embeddings.db is generated you may start querying your embeddings to retrieve top_k code refs   #
#                                                                                                                      #
#                                          >>>>>> EXAMPLE QUERY RUN <<<<<<                                             #
# ❯ python3 project_reqwire/services/tree_sitter_service.py query                                                      #
# Embeddings loaded. Ready for queries.                                                                                #
# Enter your queries (type 'exit' to quit):                                                                            #
# Query: how is the ambient light calibration done?                                                                    #
# DEBUG:urllib3.connectionpool:Starting new HTTP connection (1): localhost:11434                                       #
# DEBUG:urllib3.connectionpool:http://localhost:11434 "POST /api/embeddings HTTP/11" 200 None                          #
#                                                                                                                      #
# Top 5 results for query 'how is the ambient light calibration done?':                                                #
# Similarity: 0.6427 - function:ledCalibration|class:|path:/Users/.../lightSensor/sweepLEDBrightness.c.                #
# Similarity: 0.5968 - function:updateAmbienceLight|class:|path:/Users/.../lightSensor/lightSensor.c                   #
# Similarity: 0.5939 - function:ambientLight_sensor_initialize|class:|path:/Users/.../src/lightSensor/lightSensor.c.   #
# Similarity: 0.5765 - property:extern bool isCalibrationEnabled;|path:/Users/.../lightSensor/sweepLEDBrightness.c     #
# Similarity: 0.5720 - property:uint16_t ambienceValue = 0;|path:/Users/.../lightSensor/sweepLEDBrightness.c           #
#                                                                                                                      #
# Query: exit                                                                                                           #
# Querying done!                                                                                                       #
#                                                                                                                      #
########################################################################################################################
#################################### CODE FOR QUERYING YOUR EMBEDDINGS DATABASE ########################################
########################################################################################################################

def process_repository(repo_path, modules, file_trees, file_sizes, package_names, readme_info_list):
    for root, dirs, files in os.walk(repo_path):
        if should_skip_path(root):
            continue

        for file in files:
            file_path = os.path.join(root, file)
            process_file(file_path, modules, file_trees, file_sizes, package_names, readme_info_list)


def process_file(file_path, modules, file_trees, file_sizes, package_names, readme_info_list):
    _, file_extension = os.path.splitext(file_path)

    for lang, (language_obj, extensions) in extension_to_language.items():
        if file_extension in extensions:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()

                node_tree = process_code_string(file_content, language_obj, file_path)
                file_trees[file_path] = node_tree
                package_names[file_path] = "/".join(os.path.relpath(file_path, start=os.path.dirname(file_path)).split(os.sep)[:-1])
                file_sizes[file_path] = len(file_content.encode("utf-8")).__float__()

                manage_embeddings(node_tree, file_path, embeddings_db)

                repo_name = os.path.basename(os.path.dirname(file_path))
                if repo_name not in modules:
                    modules[repo_name] = {}
                modules[repo_name][file_path] = file_content

                if "README" in file_path.upper():
                    with open(file_path, 'r', encoding='utf-8') as file:
                        content = file.read()
                        readme_info_list.append({"id": os.path.basename(os.path.dirname(file_path)), "content": content})
            except UnicodeDecodeError:
                logging.warning(f"Skipping binary file: {file_path}")
                continue


def build_dynamic_graph(query_results, file_trees):
    G = nx.DiGraph()

    for key, similarity, node_tree in query_results:
        # Extract the code element type and name from the key
        element_type, element_name, file_path = parse_key(key)
        node_id = f"{element_type}:{element_name}|{file_path}"
        G.add_node(node_id, similarity=similarity, type=element_type, name=element_name, file=file_path)

        if isinstance(node_tree, dict):
            imports = node_tree.get('imports', [])
        elif hasattr(node_tree, 'imports'):
            imports = node_tree.imports
        else:
            imports = []

        for import_stmt in imports:
            imported_elements = find_imported_elements(import_stmt, file_trees)
            for imported_element in imported_elements:
                G.add_edge(node_id, imported_element)

    return G if G.nodes else None

def print_graph(G):
    for node in G.nodes:
        node_data = G.nodes[node]
        print(f"Node: {node_data['type']}:{node_data['name']}")
        print(f"  File: {node_data['file']}")
        print(f"  Similarity: {node_data['similarity']:.4f}")
        print("  Edges:")
        for neighbor in G.neighbors(node):
            neighbor_data = G.nodes[neighbor]
            print(f"    -> {neighbor_data['type']}:{neighbor_data['name']} in {neighbor_data['file']}")
        print()

def parse_key(key):
    parts = key.split('|')
    element_info = parts[0].split(':')
    element_type = element_info[0]
    element_name = ':'.join(element_info[1:])
    file_path = parts[1].split('path:')[1]
    return element_type, element_name, file_path


def organize_results(file_trees, all_results, top_k):
    top_repos = {}
    overall_top_elements = []
    repo_specific_elements = {}
    file_specific_elements = {}

    for key, similarity, node_tree, repo_name in all_results:
        element_type, element_name, file_path = parse_key(key)

        # Create element info dictionaryclass_names
        element_info = {
            "type": element_type,
            "name": element_name,
            "similarity": similarity,
            "file_path": key.split('|path:')[-1],
            "snippet": get_snippet(file_trees.get(file_path), key.split('|')[0]),
            "repo_name": repo_name
        }

        # Add to top repos
        if repo_name not in top_repos:
            top_repos[repo_name] = {"similarity": similarity, "top_files": {}}

        # Add to top files within repo
        if file_path not in top_repos[repo_name]["top_files"]:
            top_repos[repo_name]["top_files"][file_path] = {"similarity": similarity, "top_elements": []}

        # Add to top elements within file
        if len(top_repos[repo_name]["top_files"][file_path]["top_elements"]) < top_k:
            top_repos[repo_name]["top_files"][file_path]["top_elements"].append(element_info)

        # Add to overall top elements
        if len(overall_top_elements) < top_k:
            overall_top_elements.append(element_info)

        # Add to repo-specific elements
        if repo_name not in repo_specific_elements:
            repo_specific_elements[repo_name] = []
        if len(repo_specific_elements[repo_name]) < top_k:
            repo_specific_elements[repo_name].append(element_info)

        # Add to file-specific elements
        if file_path not in file_specific_elements:
            file_specific_elements[file_path] = []
        if len(file_specific_elements[file_path]) < top_k:
            file_specific_elements[file_path].append(element_info)

    return {
        "top_repos": format_top_repos(top_repos, top_k),
        "overall_top_elements": overall_top_elements,
        "repo_specific_elements": repo_specific_elements,
        "file_specific_elements": file_specific_elements
    }
def format_top_repos(top_repos, top_k):
    formatted_repos = [
        {
            "repo_name": repo,
            "similarity": data["similarity"],
            "top_files": [
                {
                    "file_path": file,
                    "similarity": file_data["similarity"],
                    "top_elements": file_data["top_elements"]
                }
                for file, file_data in data["top_files"].items()
            ]
        }
        for repo, data in top_repos.items()
    ]
    return sorted(formatted_repos, key=lambda x: x["similarity"], reverse=True)[:top_k]

embeddings_db = {}

def process_full_graph(full_graph_path, file_paths=None):
    with open(full_graph_path, 'r') as file:
        parsed_data = json.load(file)

    if file_paths:
        parsed_data = {k: v for k, v in parsed_data.items() if k in file_paths}
        logging.info(f"Filtered parsed_data: {parsed_data}")

    links = set()
    dependencies = {}

    for file_path, node_tree in parsed_data.items():
        if not isinstance(node_tree, dict):
            continue

        node_imports = extract_imports(node_tree)
        property_dependencies = extract_property_dependencies(node_tree)
        file_dependencies = []

        current_file_base = os.path.splitext(os.path.basename(file_path))[0]
        logging.info(f"Processing file: {file_path}")

        for other_file_path, other_node_tree in parsed_data.items():
            if file_path == other_file_path or not isinstance(other_node_tree, dict):
                continue

            other_file_base = os.path.splitext(os.path.basename(other_file_path))[0]

            if any(imp.endswith(other_file_base) for imp in node_imports) or \
               any(prop == other_file_base for prop in property_dependencies) or \
               any(other_file_base in func.get('name', '') for func in node_tree.get('functions', [])) or \
               any(other_file_base in class_name for class_name in node_tree.get('class_names', [])):
                file_dependencies.append(other_file_path)
                links.add((file_path, other_file_path))

        dependencies[file_path] = list(set(file_dependencies))
        logging.info(f"Dependencies for {file_path}: {file_dependencies}")

    nodes = []
    for file_path in parsed_data.keys():
        node = {
            "id": file_path,
            "user": extract_component_name(file_path),
            "description": "",
            "fileSize": os.path.getsize(file_path),
        }
        nodes.append(node)
        logging.info(f"Added node: {node}")

    unique_links = [{"source": source, "target": target} for source, target in links]
    logging.info(f"Unique links: {unique_links}")
    return {"nodes": nodes, "links": unique_links}

def extract_imports(node_tree):
    imports = []
    for imp in node_tree.get("imports", []):
        if imp.startswith("import "):
            module = imp.replace("import ", "").strip().split()[0]
            imports.append(module)
        else:
            imports.append(imp.strip())
    return imports

def extract_property_dependencies(node_tree):
    properties = []
    for prop in node_tree.get("property_declarations", []):
        if "@ObservedObject" in prop or "@State" in prop or "@EnvironmentObject" in prop or "@Binding" in prop:
            property_name = re.findall(r'\b\w+\b', prop)[-1]
            properties.append(property_name)
    return properties


def extended_retrieval(parsed_data, initial_files, top_k):
    # Compute dependency graph for initial_files
    dependency_graph = process_full_graph('./frontend/public/api/tree-node-data/file_trees.json', initial_files)
    dependencies = {node['id'] for node in dependency_graph['nodes']}

    # Add dependencies to initial_files
    extended_files = set(initial_files).union(dependencies)

    # Perform retrieval to get twice the top_k from extended files
    sorted_extended_files = sorted(extended_files)
    return sorted_extended_files[:top_k * 2]

def generate_individual_user_jsons(json_data):
    nodes = json_data['nodes']
    links = json_data['links']

    link_counts = calculate_link_counts(nodes, links)
    for node in nodes:
        node['linkCount'] = link_counts[node['id']]

    user_nodes_dict = {}
    for node in nodes:
        user = node['user']
        if user not in user_nodes_dict:
            user_nodes_dict[user] = []
        user_nodes_dict[user].append(node)

    script_location = pathlib.Path(__file__).parent.absolute()
    assets_dir = script_location / 'frontend/public/api/graph-data/files'
    assets_dir.mkdir(parents=True, exist_ok=True)

    file_json = {}
    for user, user_nodes in user_nodes_dict.items():
        user_links = [
            link for link in links
            if link['source'] in [node['id'] for node in user_nodes]
            or link['target'] in [node['id'] for node in user_nodes]
        ]
        file_json = {
            'nodes': user_nodes,
            'links': user_links
        }
        file_path = assets_dir / f'{user}.json'
        with open(file_path, 'w') as outfile:
            json.dump(file_json, outfile, indent=4, sort_keys=True)

    return file_json

def generate_root_level_json(json_data):
    users = {node['user'] for node in json_data['nodes']}
    new_nodes = [
        {
            'id': user,
            'description': user,
            'fileSize': sum(node['fileSize'] for node in json_data['nodes'] if node['user'] == user),
            'fileCount': sum(1 for node in json_data['nodes'] if node['user'] == user)
        }
        for user in users
    ]

    links = set()
    for link in json_data['links']:
        source_user = next(node['user'] for node in json_data['nodes'] if node['id'] == link['source'])
        target_user = next(node['user'] for node in json_data['nodes'] if node['id'] == link['target'])
        if source_user != target_user:
            links.add((source_user, target_user))

    new_links = [{'source': link[0], 'target': link[1]} for link in links]
    repo_json = {
        'nodes': new_nodes,
        'links': new_links
    }

    script_location = pathlib.Path(__file__).parent.absolute()
    assets_dir = script_location / 'frontend/public/api/graph-data'
    assets_dir.mkdir(parents=True, exist_ok=True)

    file_path = assets_dir / 'repos_graph.json'
    with open(file_path, 'w') as outfile:
        json.dump(repo_json, outfile, indent=4, sort_keys=True)

    return repo_json

def calculate_link_counts(nodes, links):
    link_counts = {node['id']: 0 for node in nodes}
    for link in links:
        if link['source'] in link_counts:
            link_counts[link['source']] += 1
        if link['target'] in link_counts:
            link_counts[link['target']] += 1
    return link_counts



def interactive_query_mode(file_trees_path):
    file_trees = load_file_trees()
    embeddings_db = load_embeddings_db()
    full_graph = loaded_graph("./frontend/public/api/graph-data/full_graph.json")
    repos_graph = loaded_graph("./frontend/public/api/graph-data/repos_graph.json")
    rag_system = RaggedyRag(embeddings_db, file_trees, full_graph, repos_graph)

    print("Improved RAG system initialized. Ready for queries.")
    print("Enter your queries (type 'exit' to quit):")

    while True:
        query = input("Query: ").strip()
        if query.lower() == 'exit':
            break

        response, relevant_snippets = rag_system.query(query)

        print("\nRAG System Response:")
        print(response)

        print("\nRelevant code snippets:")
        for i, (file_path, score) in enumerate(relevant_snippets, 1):
            print(f"{i}. Score: {score:.4f} - {file_path}")
            snippet = rag_system._get_snippet(file_path)
            print(f"Snippet: {snippet[:100]}...")  # Display first 100 characters of the snippet
            print()

        # Optionally, you can add a feature to dive deeper into specific snippets
        while True:
            choice = input("Enter a snippet number to see more details (or 'c' to continue): ")
            if choice.lower() == 'c':
                break
            try:
                index = int(choice) - 1
                if 0 <= index < len(relevant_snippets):
                    file_path, score = relevant_snippets[index]
                    print(f"\nDetailed view of snippet {index + 1}:")
                    print(f"Score: {score:.4f} - {file_path}")
                    print(f"Full snippet:\n{rag_system._get_snippet(file_path)}")
                else:
                    print("Invalid snippet number.")
            except ValueError:
                print("Invalid input. Please enter a number or 'c'.")

def process_requirements(csv_file_path):
    requirements_db = {}
    try:
        with open(csv_file_path, mode='r', encoding='utf-8') as csvfile:
            csvreader = csv.DictReader(csvfile)
            for row in csvreader:
                requirement_id = row["Project ID"]
                description = row["Description"]
                embedding = generate_embeddings(description, model=REQUIREMENT_EMBEDDING_MODEL)
                if embedding is not None:
                    requirements_db[requirement_id] = {
                        "embedding": embedding.tolist(),
                        "data": row
                    }
    except Exception as e:
        logging.error(f"Error processing requirements: {str(e)}")

    # Save the requirements embeddings
    save_requirements_db(requirements_db)
    return requirements_db

# Function to save requirements embeddings to disk
def save_requirements_db(requirements_db):
    with open(REQUIREMENTS_DB_PATH, "w") as file:
        json.dump(requirements_db, file)

# Function to load requirements embeddings from disk
def load_requirements_db():
    if os.path.exists(REQUIREMENTS_DB_PATH):
        with open(REQUIREMENTS_DB_PATH, "r") as file:
            return json.load(file)
    return {}



# Main function to process codebase and requirements
def main():
    parser = argparse.ArgumentParser(description="Code Embedding Processor and Query System")
    parser.add_argument("mode", choices=["process", "query", "process_requirements"],
                        help="Mode of operation: 'process' to analyze codebase, 'query' for interactive querying, 'process_requirements' to process only requirements")
    parser.add_argument("--root_dir", help="Root directory of the codebase (required for 'process' mode)")
    parser.add_argument("--requirements_csv", help="Path to requirements CSV file (required for 'process_requirements' mode, optional for 'process' mode)")

    args = parser.parse_args()

    if args.mode == "process":
        if not args.root_dir:
            print("Error: --root_dir is required for 'process' mode")
            sys.exit(1)
        process_codebase(args.root_dir)
        if args.requirements_csv:
            process_requirements(args.requirements_csv)
    elif args.mode == "process_requirements":
        if not args.requirements_csv:
            print("Error: --requirements_csv is required for 'process_requirements' mode")
            sys.exit(1)
        process_requirements(args.requirements_csv)
    elif args.mode == "query":
        file_trees_path = "./frontend/public/api/tree-node-data/file_trees.json"
        if not os.path.exists(file_trees_path):
            print("Error: No file trees found. Please run in 'process' mode first.")
            sys.exit(1)
        interactive_query_mode(file_trees_path)

if __name__ == "__main__":
    main()
