1. Project Overview

This project is a Retrieval-Augmented Generation (RAG) based enterprise knowledge assistant.

The system allows users to ask questions in natural language and retrieves relevant information from company documents using semantic search. The retrieved information is then provided as context to a locally hosted Qwen3 8B language model to generate a grounded response.

The system is designed to make existing organizational knowledge easier to access and reuse.

---

2. System Architecture

Documents
    ↓
Python Ingestion
    ↓
Text Extraction & Chunking
    ↓
nomic-embed-text
    ↓
Qdrant Vector Database
    ↓
User Query
    ↓
Query Embedding
    ↓
Semantic Similarity Search
    ↓
Relevant Document Chunks
    ↓
Context Construction
    ↓
Qwen3:8b via Ollama
    ↓
Generated Response
    ↓
FastAPI / Open WebUI / n8n

---

3. Technologies Used

- Python
- docx2txt
- Qdrant
- Ollama
- nomic-embed-text
- Qwen3:8b
- n8n
- FastAPI
- Open WebUI
- Docker

---

4. Project Structure

```text
AI_Knowledge_Base_Project/
│
├── knowledge_base/
│   ├── Coupons.docx
│   ├── MQ SURE! Promotions.docx
│   ├── MQ SURE! Simplified Collections.docx
│   ├── Payment Gateway TroubleShooting Document.docx
│   └── Referral_Program.docx
│
├── rag-api/
│   └── app.py
│
├── ingest.py
├── create_manifest.py
├── cleanup_duplicates.py
├── initialize_hashes.py
├── requirements.txt
├── n8n_workflow.json
└── README.md


FastAPI acts as an API bridge between the user interface and the n8n-based RAG workflow. It exposes an OpenAI-compatible /v1/chat/completions endpoint, forwards the user's question to the n8n webhook, and returns the generated answer and document sources.