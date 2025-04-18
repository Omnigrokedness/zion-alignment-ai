import os
import numpy as np
import logging
# import faiss  # Commented out until we can install faiss
import json
from flask import Blueprint, jsonify, request
from app import db
from models import Truth
# from llm_handler import initialize_model, model, tokenizer  # Commented out until we can install torch/transformers

# Configure logging
logger = logging.getLogger(__name__)

# Global variables
index = None
truth_ids = []
dimension = 768  # Default dimension for embeddings

def get_embedding(text):
    """Get embedding vector for text using the loaded model"""
    try:
        # Temporarily return a random vector until we can install transformers and torch
        # This is just a placeholder function
        logger.warning("Using placeholder embedding function - no semantic search capability")
        return np.random.rand(dimension)
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None

def initialize_index():
    """Initialize or load the FAISS index for truth retrieval"""
    global index, truth_ids, dimension
    
    try:
        # Temporarily disabled FAISS integration
        logger.info("FAISS integration is currently disabled")
        
        # Load all truths from database
        truths = Truth.query.all()
        if not truths:
            logger.info("No truths found in database to index")
            return
        
        # Just store truth IDs for now
        truth_ids = [truth.id for truth in truths]
        logger.info(f"Loaded {len(truth_ids)} truth IDs (no vector index)")
        
    except Exception as e:
        logger.error(f"Error initializing index: {e}")

def search_similar_truths(query_text, top_k=5):
    """Search for similar truths based on semantic similarity"""
    global index, truth_ids
    
    if len(truth_ids) == 0:
        initialize_index()
        if len(truth_ids) == 0:
            logger.warning("No truths found in database")
            return []
    
    # Since we don't have FAISS, return a random selection of truths instead
    logger.warning("Using basic search without semantic capabilities")
    
    # Get a random selection of truth IDs
    import random
    selected_ids = random.sample(truth_ids, min(top_k, len(truth_ids)))
    
    # Retrieve truths from database
    truths = Truth.query.filter(Truth.id.in_(selected_ids)).all()
    
    return truths

def add_to_index(truth):
    """Add a truth to the index (simplified version without FAISS)"""
    global truth_ids
    
    if truth.id not in truth_ids:
        # Generate a placeholder embedding
        vector = get_embedding(truth.content)
        
        # Save embedding to database (will be useful when we enable FAISS)
        if vector is not None:
            truth.set_vector(vector.tolist())
            db.session.commit()
        
        # Add to our simple index
        truth_ids.append(truth.id)
        logger.info(f"Added truth ID {truth.id} to simplified index")
    
    return True

def remove_from_index(truth_id):
    """Remove a truth from the index"""
    global truth_ids
    
    try:
        if truth_id in truth_ids:
            # Remove from ids list
            truth_ids.remove(truth_id)
            logger.info(f"Removed truth ID {truth_id} from simplified index")
        else:
            logger.warning(f"Truth ID {truth_id} not found in index")
    except Exception as e:
        logger.error(f"Error removing truth from index: {e}")
