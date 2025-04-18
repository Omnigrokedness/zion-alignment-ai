import os
import json
import logging
from flask import Blueprint, request, jsonify, render_template
from app import db
from models import Truth
from memory_manager import add_to_index, remove_from_index, search_similar_truths, get_embedding

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
truth_bp = Blueprint('truth', __name__, url_prefix='/api/truth')

@truth_bp.route('/add', methods=['POST'])
def add_truth(data=None):
    """Add a new truth to the database"""
    # Allow direct function call with data parameter or get from request
    if data is None:
        data = request.json
    
    content = data.get('content')
    source = data.get('source', '')
    
    if not content:
        if request:
            return jsonify({"error": "Content is required"}), 400
        else:
            logger.error("Content is required for adding truth")
            return None
    
    try:
        # Create new truth
        truth = Truth(content=content, source=source)
        
        # Generate embedding - skipped if ML is disabled
        try:
            embedding = get_embedding(content)
            if embedding is not None:
                truth.set_vector(embedding.tolist())
        except Exception as embed_error:
            logger.warning(f"Could not generate embedding for truth: {embed_error}")
        
        # Extract topics (simplified implementation)
        topics = extract_topics(content)
        truth.set_topics(topics)
        
        # Save to database
        db.session.add(truth)
        db.session.commit()
        
        # Add to search index - skipped if ML is disabled
        try:
            add_to_index(truth)
        except Exception as index_error:
            logger.warning(f"Could not add truth to search index: {index_error}")
        
        result = {
            "id": truth.id,
            "message": "Truth added successfully",
            "topics": topics
        }
        
        if request:
            return jsonify(result)
        else:
            return result
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding truth: {e}")
        if request:
            return jsonify({"error": str(e)}), 500
        else:
            return None

@truth_bp.route('/delete/<int:truth_id>', methods=['DELETE'])
def delete_truth(truth_id):
    """Delete a truth from the database"""
    truth = Truth.query.get(truth_id)
    if not truth:
        return jsonify({"error": "Truth not found"}), 404
    
    try:
        # Remove from search index
        remove_from_index(truth_id)
        
        # Delete from database
        db.session.delete(truth)
        db.session.commit()
        
        return jsonify({"message": "Truth deleted successfully"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting truth: {e}")
        return jsonify({"error": str(e)}), 500

@truth_bp.route('/update/<int:truth_id>', methods=['PUT'])
def update_truth(truth_id):
    """Update an existing truth"""
    truth = Truth.query.get(truth_id)
    if not truth:
        return jsonify({"error": "Truth not found"}), 404
    
    data = request.json
    content = data.get('content')
    source = data.get('source')
    
    if not content:
        return jsonify({"error": "Content is required"}), 400
    
    try:
        # Update truth
        truth.content = content
        if source is not None:
            truth.source = source
        
        # Update embedding
        embedding = get_embedding(content)
        if embedding is not None:
            truth.set_vector(embedding.tolist())
        
        # Update topics
        topics = extract_topics(content)
        truth.set_topics(topics)
        
        # Save changes
        db.session.commit()
        
        # Update in search index (remove and re-add)
        remove_from_index(truth_id)
        add_to_index(truth)
        
        return jsonify({
            "message": "Truth updated successfully",
            "topics": topics
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating truth: {e}")
        return jsonify({"error": str(e)}), 500

@truth_bp.route('/search', methods=['GET'])
def search_truths():
    """Search for truths by content or semantic similarity"""
    query = request.args.get('query', '')
    search_type = request.args.get('type', 'semantic')  # 'semantic' or 'text'
    limit = int(request.args.get('limit', 5))
    
    if not query:
        return jsonify({"error": "Query is required"}), 400
    
    try:
        if search_type == 'semantic':
            # Semantic search using vector embeddings
            results = search_similar_truths(query, limit)
            return jsonify({
                "results": [
                    {
                        "id": t.id,
                        "content": t.content,
                        "source": t.source,
                        "topics": t.get_topics(),
                        "created_at": t.created_at.isoformat()
                    } for t in results
                ]
            })
        else:
            # Text-based search
            results = Truth.query.filter(Truth.content.ilike(f'%{query}%')).limit(limit).all()
            return jsonify({
                "results": [
                    {
                        "id": t.id,
                        "content": t.content,
                        "source": t.source,
                        "topics": t.get_topics(),
                        "created_at": t.created_at.isoformat()
                    } for t in results
                ]
            })
    except Exception as e:
        logger.error(f"Error searching truths: {e}")
        return jsonify({"error": str(e)}), 500

@truth_bp.route('/by-topic/<topic>', methods=['GET'])
def get_truths_by_topic(topic):
    """Get truths by topic"""
    limit = int(request.args.get('limit', 10))
    
    try:
        # Get all truths
        all_truths = Truth.query.all()
        
        # Filter by topic
        results = []
        for truth in all_truths:
            topics = truth.get_topics()
            if topic.lower() in [t.lower() for t in topics]:
                results.append(truth)
                if len(results) >= limit:
                    break
        
        return jsonify({
            "results": [
                {
                    "id": t.id,
                    "content": t.content,
                    "source": t.source,
                    "topics": t.get_topics(),
                    "created_at": t.created_at.isoformat()
                } for t in results
            ]
        })
    except Exception as e:
        logger.error(f"Error getting truths by topic: {e}")
        return jsonify({"error": str(e)}), 500

@truth_bp.route('/all', methods=['GET'])
def get_all_truths():
    """Get all truths"""
    try:
        truths = Truth.query.all()
        return jsonify({
            "truths": [
                {
                    "id": t.id,
                    "content": t.content,
                    "source": t.source,
                    "topics": t.get_topics(),
                    "created_at": t.created_at.isoformat()
                } for t in truths
            ]
        })
    except Exception as e:
        logger.error(f"Error getting all truths: {e}")
        return jsonify({"error": str(e)}), 500

@truth_bp.route('/topics', methods=['GET'])
def get_all_topics():
    """Get all unique topics from truths"""
    try:
        truths = Truth.query.all()
        all_topics = set()
        
        for truth in truths:
            topics = truth.get_topics()
            all_topics.update(topics)
        
        return jsonify({
            "topics": sorted(list(all_topics))
        })
    except Exception as e:
        logger.error(f"Error getting all topics: {e}")
        return jsonify({"error": str(e)}), 500

def extract_topics(content):
    """
    Extract topics from content
    Simple implementation - in a real system, this would use more sophisticated NLP
    """
    # Simple keyword extraction - this is a placeholder
    # In a production system, you'd use NER, keyword extraction, or topic modeling
    common_topics = [
        "faith", "revelation", "scripture", "prophecy", "truth",
        "wisdom", "knowledge", "salvation", "redemption", "covenant"
    ]
    
    found_topics = []
    for topic in common_topics:
        if topic.lower() in content.lower():
            found_topics.append(topic)
    
    # Default topic if none found
    if not found_topics:
        found_topics = ["general"]
    
    return found_topics
