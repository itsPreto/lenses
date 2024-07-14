<div align="center">

# Setup Guide for LENSES: Layered Embedding Network for Search and Exploration System

This document provides a comprehensive guide for setting up and using the LENSES project. It covers environment setup, backend and frontend configuration, system usage, future vision, and details about the Flask server and its features.

---

![LENSES Project](https://github.com/itsPreto/lenses/blob/main/frontend/public/animated.gif)

## Note: the project comes with an example codebase already processed: [Spring-AI](https://github.com/spring-projects/spring-ai)
## To quickly launch the frontend `cd frontend` then `npm install` & `npm start` and you should see the UI be brought up.
</div>

---

## 1. Environment Setup

### 1.1 Python Environment
1. Ensure Python 3.8+ is installed.
2. Create a virtual environment:
   ```sh
   python -m venv lenses_env
   ```
3. Activate the virtual environment:
   - Windows: `lenses\Scripts\activate`
   - Mac/Linux: `source lenses-env/bin/activate`

### 1.2 Install Python Dependencies
Use the requirements.txt file:
```sh
pip install -r requirements.txt
```

### 1.3 Node.js and npm
Ensure Node.js and npm are installed for the frontend.

### 1.4 Local Embedding Server Setup (Ollama)

Ollama allows running AI models locally. To set it up:

1. Install Ollama from [ollama.ai/download](https://ollama.ai/download).
2. Start the Ollama server:
   ```sh
   ollama serve
   ```
3. Pull the required models:
   ```sh
   ollama pull unclemusclez/jina-embeddings-v2-base-code:q4
   ollama pull qwen2:7b
   ```

To use different models:
1. Browse the [Ollama Model Library](https://ollama.com/library)
2. Pull a model:
   ```sh
   ollama pull model_name:variant
   ```
   Example: `ollama pull llama2:13b-chat-q5_1`

3. List installed models:
   ```sh
   ollama list
   ```

To use a different model, update `app.py` or `rag.py`:

```python
CODE_EMBEDDING_MODEL = "new_embedding_model"
LLM_MODEL = "new_llm_model"
```

## 2. Backend Setup

### 2.1 Directory Structure
Ensure the project structure is as follows:
```
LENSES/
├── app.py
├── rag.py
├── requirements.txt
├── flask_server.py     // this is WIP
├── utils/
│   └── grammar/
│       ├── ast_traversers.py
│       └── language_grammars.so
├── frontend/
│   └── public/
│       └── api/
│           ├── graph-data/
│           └── tree-node-data/
└── assets/
```

### 2.2 Processing Repositories
1. Place repositories to analyze in a directory.
2. Run the processing script:
   ```sh
   python app.py process --root_dir /path/to/repos
   ```
   This generates JSON files in `frontend/public/api/`.

## 3. Frontend Setup

### 3.1 Install Frontend Dependencies
In the frontend directory:
```sh
cd frontend
npm install
```

### 3.2 Configure API Endpoints
Ensure correct API endpoints in React components.

### 3.3 Start the Development Server
```sh
npm start
```

## 4. Running the System

1. Start Ollama in a separate terminal:
   ```sh
   ollama serve
   ```

2. Run the backend query mode:
   ```sh
   python app.py query
   ```

3. Start the frontend server:
   ```sh
   cd frontend
   npm start
   ```

4. Open `http://localhost:3000` in a browser.

## 5. Using the System

### 5.1 Visualization Interface
- Switch between Repos and Full Graph views
- Search for nodes
- Click nodes for details
- Use Selection Mode for impact statistics

### 5.2 Backend Querying
Use the command-line interface to:
1. Enter queries
2. View results and snippets
3. Explore specific snippets

## 6. Extending the System

To integrate backend functionality with the frontend:

1. Implement API endpoints in the backend
2. Update frontend to use new endpoints
3. Add UI components for query results and summaries

## 7. Future Vision

Long-term goals for the project include:

### 8.1 Local AI Assistant Capabilities

- Complex codebase understanding
- Independent research and task completion
- Adaptation to user interactions
- Local operation for privacy

### 8.2 Natural Language Interaction

- Voice-to-text using whisper.cpp
- Text-to-speech for audio responses
- Voice-controlled interface

### 8.3 Expanded Knowledge Integration

- Incorporation of external documentation
- Integration with project management tools
- Analysis of version control history
- Inclusion of community discussions

### 8.4 Advanced Code Analysis

- Automated refactoring suggestions
- Bug detection and fixing
- Code generation from descriptions
- Performance optimization recommendations

### 8.5 Collaborative Development Features

- Assistance in code reviews
- Task allocation suggestions
- Conflict and integration issue prediction
- Knowledge transfer facilitation

The project aims to become a comprehensive tool for developers, leveraging AI for code understanding while maintaining local execution for privacy.

## 9. Flask Server Setup and Features

The project includes a Flask server that provides additional functionality and APIs for the frontend. This server is not yet fully integrated with the frontend but offers several powerful features.

### 9.1 Setting Up the Flask Server

1. Ensure Flask and required dependencies are installed:
   ```sh
   pip install -r requirements.txt
   ```

2. Run the Flask server:
   ```sh
   python flask_server.py
   ```

   The server will start on `http://localhost:5000` by default.

### 9.2 Key Features of the Flask Server

#### 9.2.1 Similarity Matrix Generation

- Endpoint: `/similarity-matrix`
- Method: GET
- Description: Generates a similarity matrix between JAMA requirements descriptions and relevant code snippets.
- Use Case: Allows QA to "audit" specific requirements and check their implementation status.

#### 9.2.2 Codebase Processing

- Endpoint: `/process`
- Method: POST
- Description: Processes the codebase, generating embeddings and necessary data structures.

#### 9.2.3 Query Processing

- Endpoint: `/query`
- Method: POST
- Description: Processes queries against the codebase, returning relevant code snippets and requirements.
- Features:
  - Extends retrieval results by including transitive closures of file references.
  - Provides a broader scope of implementation context.

#### 9.2.4 Dependency Graph Generation

- Endpoint: `/generate_dependency_graph`
- Method: POST
- Description: Generates a dependency graph based on query results or specified file paths.

### 9.3 Future Enhancements

- LLM Integration: Plans to process retrieved snippets through an LLM for more coherent decision-making about requirement implementation.
- Frontend Integration: The server will be integrated with the frontend to provide a seamless user experience.
- Context Optimization: Working on optimizing the amount of context provided to the LLM to improve response quality while managing information overload.

### 9.4 Using the Flask Server

To interact with the Flask server:

1. Use API testing tools like Postman or curl to send requests to the endpoints.
2. Integrate the endpoints into the frontend application for a unified user interface.
3. Customize the server endpoints as needed for specific project requirements.

Note: Ensure proper error handling and security measures are implemented before deploying the server in a production environment.

### 9.5 Real-time updates to the graph:

1. Sync source-code to the json structures to auto-parse and increment the
json structures with the live changes so that the graph can update as a developer edits the code.

2. TODO--

## 10. Backend's Additional Capabilities and Current Issues

### 10.1 Generating Individual Repo Level JSONs
The backend is capable of generating a third dilution of the full dependency graph, which results in individual repo level JSONs containing all the file-to-file relationships within that repo. This feature can be useful for focused analysis and visualization of specific repositories.

### 10.2 Current Issue with Individual JSONs
There is an issue with the algorithm in the `generate_individual_user_jsons` function where it creates links to files (nodes) that belong to different repositories (known as "users" in the code).

### 10.3 Temporary Solution
Due to this issue, the ability to view individual graphs on the UI has been temporarily removed. The goal is to ensure that individual JSONs contain only files specific to their respective "user" before re-enabling this feature in the UI.

---
