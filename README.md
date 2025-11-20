# Enterprise Multimodal RAG Agent (FastAPI + ColPali)

## Project Overview

This project is a production-ready **Multimodal Retrieval-Augmented Generation (RAG)** system designed to handle complex financial documents (PDFs with tables, charts, and graphs).

Unlike traditional text-based RAG, this system uses **ColPali (Vision-Language Model)** to index document pages as visual embeddings. This allows it to retrieve information based on visual layout (e.g., "the chart on the bottom left") rather than just text keywords.

The architecture is modular, using **FastAPI** for the backend and vanilla **HTML/JS** for a lightweight, decoupled frontend.

## Tech Stack

* **Backend:** FastAPI, Uvicorn
* **Retrieval:** ColPali (via `byaldi`), PyTorch
* **Frontend:** HTML5, CSS3, JavaScript (Fetch API)
* **Indexing:** Visual Vector Embeddings (ColBERT-style late interaction)

## Quick Start

### 1. Setup Environment

```
# Create virtual environment
python -m venv venv
source venv/bin/activate  
pip install -r requirements.txt

```

### 2. Add Data

Place your PDF file (e.g., `nvidia_10q.pdf`) inside the `data/` folder.

### 3. Run the Server

This command starts the API and serves the frontend.

```
python -m app.main

```

*Note: On the first run, it will download the ColPali model (~2GB) and create the index. This may take a few minutes.*

### 4. Use the App

Open your browser to: `http://localhost:8000`

## Resume Content

Headline:

Machine Learning Engineer | Specialized in Multimodal AI & Production Systems
