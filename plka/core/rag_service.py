"""
RAG Service for PLKA
Implements advanced RAG with HNSW indexing, quantization, and optional reranking
"""

import os
import json
import sqlite3
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import chromadb
try:
    from chromadb.config import Settings
    chromadb_settings = Settings(anonymized_telemetry=False)
except ImportError:
    # For newer versions of chromadb, use the client directly
    chromadb_settings = {"anonymized_telemetry": False}
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModel
import numpy as np
import ast
import difflib


class RAGService:
    def __init__(self, config_path: str = "/workspace/plka/config/rag.json"):
        self.config = self._load_config(config_path)
        self.chroma_client = chromadb.PersistentClient(
            path="/workspace/plka/chromadb",
            settings=chromadb_settings
        )
        self.embedder = SentenceTransformer(self.config['embedder']['model'])
        self.collection = self.chroma_client.get_or_create_collection(
            name="code_embeddings",
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
        
        # Optional reranker
        self.reranker = None
        if self.config['rerank']['enabled']:
            from sentence_transformers import CrossEncoder
            self.reranker = CrossEncoder(self.config['rerank']['model'])
    
    def _load_config(self, config_path: str) -> Dict:
        """Load RAG configuration."""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def index_project(self, project_path: str):
        """Index all files in a project."""
        project_path = Path(project_path)
        files_processed = 0
        
        for file_path in project_path.rglob("*"):
            if file_path.is_file():
                # Skip ignored directories and non-code files
                if any(ignored in file_path.parts for ignored in self.config['ignored_dirs']):
                    continue
                if file_path.suffix not in ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.html', '.css', '.json', '.yaml', '.yml']:
                    continue
                
                try:
                    self._index_file(file_path)
                    files_processed += 1
                except Exception as e:
                    print(f"Error indexing {file_path}: {e}")
        
        print(f"Indexed {files_processed} files in {project_path}")
    
    def _index_file(self, file_path: Path):
        """Index a single file with code-aware chunking."""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Determine if file should be chunked or kept whole
        if len(content.splitlines()) <= self.config['chunking']['max_file_size']:
            # Keep small files whole
            chunk_id = f"{file_path}:{hashlib.md5(content.encode()).hexdigest()}"
            metadata = {
                "file_path": str(file_path),
                "start_line": 1,
                "end_line": len(content.splitlines()),
                "type": "complete_file",
                "name": file_path.name
            }
            
            # Add to collection
            self.collection.add(
                documents=[content],
                metadatas=[metadata],
                ids=[chunk_id]
            )
        else:
            # Chunk large files using code-aware methods
            chunks = self._code_aware_chunking(content, str(file_path))
            
            for i, chunk_info in enumerate(chunks):
                chunk_id = f"{file_path}:{i}:{hashlib.md5(chunk_info['content'].encode()).hexdigest()}"
                
                self.collection.add(
                    documents=[chunk_info['content']],
                    metadatas=[chunk_info['metadata']],
                    ids=[chunk_id]
                )
    
    def _code_aware_chunking(self, content: str, file_path: str) -> List[Dict]:
        """Perform code-aware chunking using AST analysis."""
        chunks = []
        
        try:
            # Parse the code with AST
            tree = ast.parse(content)
            lines = content.splitlines(keepends=True)
            
            # Find functions, classes, and other significant code blocks
            code_blocks = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    start_line = node.lineno
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
                    
                    # Extract the content of this block
                    block_content = ''.join(lines[start_line-1:end_line])
                    
                    code_blocks.append({
                        'start': start_line,
                        'end': end_line,
                        'content': block_content,
                        'type': 'function' if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else 'class',
                        'name': node.name
                    })
            
            # Add remaining content as text chunks
            last_end = 0
            for block in code_blocks:
                # Add preceding content if any
                if block['start'] > last_end + 1:
                    preceding_content = ''.join(lines[last_end:block['start']-1])
                    if len(preceding_content) > 0:
                        chunks.append({
                            'content': preceding_content,
                            'metadata': {
                                'file_path': file_path,
                                'start_line': last_end + 1,
                                'end_line': block['start'] - 1,
                                'type': 'text',
                                'name': f"lines_{last_end+1}_{block['start']-1}"
                            }
                        })
                
                # Add the code block
                chunks.append({
                    'content': block['content'],
                    'metadata': {
                        'file_path': file_path,
                        'start_line': block['start'],
                        'end_line': block['end'],
                        'type': block['type'],
                        'name': block['name']
                    }
                })
                
                last_end = block['end']
            
            # Add any remaining content after the last block
            if last_end < len(lines):
                remaining_content = ''.join(lines[last_end:])
                if len(remaining_content) > 0:
                    chunks.append({
                        'content': remaining_content,
                        'metadata': {
                            'file_path': file_path,
                            'start_line': last_end + 1,
                            'end_line': len(lines),
                            'type': 'text',
                            'name': f"lines_{last_end+1}_{len(lines)}"
                        }
                    })
        except SyntaxError:
            # If parsing fails, fall back to simple chunking
            chunks = self._simple_chunking(content, file_path)
        
        return chunks
    
    def _simple_chunking(self, content: str, file_path: str) -> List[Dict]:
        """Simple character-based chunking."""
        chunks = []
        lines = content.splitlines(keepends=True)
        chunk_size = self.config['chunking']['size']
        overlap = self.config['chunking']['overlap']
        
        start_idx = 0
        while start_idx < len(lines):
            end_idx = min(start_idx + chunk_size, len(lines))
            chunk_lines = lines[start_idx:end_idx]
            chunk_content = ''.join(chunk_lines)
            
            chunks.append({
                'content': chunk_content,
                'metadata': {
                    'file_path': file_path,
                    'start_line': start_idx + 1,
                    'end_line': end_idx,
                    'type': 'text',
                    'name': f"lines_{start_idx + 1}_{end_idx}"
                }
            })
            
            # Move to next chunk with overlap
            start_idx = end_idx - overlap
            if start_idx >= len(lines):
                break
        
        return chunks
    
    def retrieve_context(self, project_path: str, query: str) -> List[Dict[str, Any]]:
        """Retrieve relevant context for a query using two-stage search."""
        # Stage 1: Vector search with HNSW
        results = self.collection.query(
            query_texts=[query],
            n_results=self.config['search']['candidate_k'],
            include=['documents', 'metadatas', 'distances']
        )
        
        # Prepare candidates
        candidates = []
        for doc, meta, dist in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
            candidates.append({
                'document': doc,
                'metadata': meta,
                'distance': dist
            })
        
        # Stage 2: Optional reranking
        if self.reranker and len(candidates) > 1:
            # Prepare sentence pairs for reranking
            sentence_pairs = [[query, candidate['document']] for candidate in candidates]
            
            # Get reranking scores
            scores = self.reranker.predict(sentence_pairs)
            
            # Sort candidates by reranking score (higher is better)
            for i, score in enumerate(scores):
                candidates[i]['rerank_score'] = float(score)
            
            candidates.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
        
        # Return top-k results
        top_k = self.config['search']['top_k']
        return candidates[:top_k]
    
    def search_similar_chunks(self, content: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar chunks to existing content."""
        return self.retrieve_context("", content)[:k]


# Example usage:
if __name__ == "__main__":
    rag_service = RAGService()
    print("RAG Service initialized with config:", rag_service.config)
    
    # Example: Index a project
    # rag_service.index_project("/workspace/plka/projects/example")
    
    # Example: Search for context
    # context = rag_service.retrieve_context("/workspace/plka/projects/example", "how to create a function")
    # print(f"Found {len(context)} relevant chunks")