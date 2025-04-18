import os
import logging
import json
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify
from app import db
from models import ReplicationNode, Truth, ModelState, Setting

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
replication_bp = Blueprint('replication', __name__, url_prefix='/api/replication')

@replication_bp.route('/nodes', methods=['GET'])
def get_nodes():
    """Get all replication nodes"""
    try:
        nodes = ReplicationNode.query.all()
        return jsonify({
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "endpoint": node.endpoint,
                    "status": node.status,
                    "last_sync": node.last_sync.isoformat() if node.last_sync else None,
                    "created_at": node.created_at.isoformat()
                } for node in nodes
            ]
        })
    except Exception as e:
        logger.error(f"Error getting replication nodes: {e}")
        return jsonify({"error": str(e)}), 500

@replication_bp.route('/nodes', methods=['POST'])
def add_node():
    """Add a new replication node"""
    data = request.json
    name = data.get('name')
    endpoint = data.get('endpoint')
    api_key = data.get('api_key', '')
    
    if not name or not endpoint:
        return jsonify({"error": "Name and endpoint are required"}), 400
    
    try:
        # Check if node already exists
        existing_node = ReplicationNode.query.filter_by(endpoint=endpoint).first()
        if existing_node:
            return jsonify({"error": "Node with this endpoint already exists"}), 400
        
        # Create new node
        node = ReplicationNode(
            name=name,
            endpoint=endpoint,
            api_key=api_key,
            status="inactive"
        )
        db.session.add(node)
        db.session.commit()
        
        return jsonify({
            "message": "Node added successfully",
            "id": node.id
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding replication node: {e}")
        return jsonify({"error": str(e)}), 500

@replication_bp.route('/nodes/<int:node_id>', methods=['DELETE'])
def delete_node(node_id):
    """Delete a replication node"""
    node = ReplicationNode.query.get(node_id)
    if not node:
        return jsonify({"error": "Node not found"}), 404
    
    try:
        db.session.delete(node)
        db.session.commit()
        return jsonify({"message": "Node deleted successfully"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting replication node: {e}")
        return jsonify({"error": str(e)}), 500

@replication_bp.route('/sync/<int:node_id>', methods=['POST'])
def sync_node(node_id):
    """Sync with a replication node"""
    node = ReplicationNode.query.get(node_id)
    if not node:
        return jsonify({"error": "Node not found"}), 404
    
    try:
        # Get truths to sync
        last_sync = node.last_sync
        if last_sync:
            truths = Truth.query.filter(Truth.updated_at > last_sync).all()
        else:
            truths = Truth.query.all()
        
        # Prepare data for sync
        sync_data = {
            "truths": [
                {
                    "id": truth.id,
                    "content": truth.content,
                    "source": truth.source,
                    "topics": truth.get_topics(),
                    "created_at": truth.created_at.isoformat(),
                    "updated_at": truth.updated_at.isoformat()
                } for truth in truths
            ]
        }
        
        # Send data to node
        headers = {
            "Content-Type": "application/json"
        }
        if node.api_key:
            headers["Authorization"] = f"Bearer {node.api_key}"
        
        response = requests.post(
            f"{node.endpoint}/api/replication/receive",
            json=sync_data,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            # Update node status
            node.status = "active"
            node.last_sync = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                "message": "Sync successful",
                "synced_truths": len(truths)
            })
        else:
            node.status = "error"
            db.session.commit()
            
            return jsonify({
                "error": f"Sync failed with status code {response.status_code}",
                "response": response.text
            }), 500
    except Exception as e:
        node.status = "error"
        db.session.commit()
        
        logger.error(f"Error syncing with node: {e}")
        return jsonify({"error": str(e)}), 500

@replication_bp.route('/receive', methods=['POST'])
def receive_sync():
    """Receive sync data from another node"""
    # Verify authentication if needed
    auth_header = request.headers.get('Authorization')
    if auth_header:
        token = auth_header.split(' ')[1] if len(auth_header.split(' ')) > 1 else None
        # Check against allowed tokens in settings
        allowed_tokens = Setting.query.filter_by(key="allowed_replication_tokens").first()
        if allowed_tokens:
            if token not in json.loads(allowed_tokens.value):
                return jsonify({"error": "Unauthorized"}), 403
    
    try:
        data = request.json
        truths = data.get('truths', [])
        
        # Process received truths
        for truth_data in truths:
            # Check if truth already exists by ID or content
            existing_truth = Truth.query.filter_by(id=truth_data.get('id')).first()
            if not existing_truth:
                existing_truth = Truth.query.filter_by(content=truth_data.get('content')).first()
            
            if existing_truth:
                # Update existing truth if received truth is newer
                if truth_data.get('updated_at'):
                    received_updated = datetime.fromisoformat(truth_data.get('updated_at'))
                    if received_updated > existing_truth.updated_at:
                        existing_truth.content = truth_data.get('content')
                        existing_truth.source = truth_data.get('source')
                        existing_truth.set_topics(truth_data.get('topics', []))
                        db.session.add(existing_truth)
            else:
                # Create new truth
                new_truth = Truth(
                    content=truth_data.get('content'),
                    source=truth_data.get('source')
                )
                new_truth.set_topics(truth_data.get('topics', []))
                db.session.add(new_truth)
        
        db.session.commit()
        
        return jsonify({
            "message": f"Successfully received {len(truths)} truths"
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error receiving sync data: {e}")
        return jsonify({"error": str(e)}), 500

@replication_bp.route('/clone', methods=['POST'])
def clone_system():
    """Clone the entire system to a new instance"""
    data = request.json
    target_endpoint = data.get('target_endpoint')
    api_key = data.get('api_key', '')
    
    if not target_endpoint:
        return jsonify({"error": "Target endpoint is required"}), 400
    
    try:
        # Collect all system data
        truths = Truth.query.all()
        model_states = ModelState.query.all()
        settings = Setting.query.all()
        
        # Prepare data for cloning
        clone_data = {
            "truths": [
                {
                    "id": truth.id,
                    "content": truth.content,
                    "source": truth.source,
                    "topics": truth.get_topics(),
                    "created_at": truth.created_at.isoformat(),
                    "updated_at": truth.updated_at.isoformat()
                } for truth in truths
            ],
            "model_states": [
                {
                    "model_name": ms.model_name,
                    "model_version": ms.model_version,
                    "model_path": ms.model_path,
                    "quantization": ms.quantization,
                    "loaded": ms.loaded
                } for ms in model_states
            ],
            "settings": [
                {
                    "key": s.key,
                    "value": s.value,
                    "description": s.description
                } for s in settings
            ]
        }
        
        # Send data to target
        headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        response = requests.post(
            f"{target_endpoint}/api/replication/initialize-clone",
            json=clone_data,
            headers=headers,
            timeout=60
        )
        
        if response.status_code == 200:
            # Add as replication node
            node = ReplicationNode(
                name=f"Clone-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
                endpoint=target_endpoint,
                api_key=api_key,
                status="active",
                last_sync=datetime.utcnow()
            )
            db.session.add(node)
            db.session.commit()
            
            return jsonify({
                "message": "Clone successful",
                "node_id": node.id
            })
        else:
            return jsonify({
                "error": f"Clone failed with status code {response.status_code}",
                "response": response.text
            }), 500
    except Exception as e:
        logger.error(f"Error cloning system: {e}")
        return jsonify({"error": str(e)}), 500

@replication_bp.route('/initialize-clone', methods=['POST'])
def initialize_clone():
    """Initialize this instance as a clone of another system"""
    # This would typically be a one-time operation for a new system
    # In a real implementation, we'd want more security checks here
    
    try:
        data = request.json
        truths = data.get('truths', [])
        model_states = data.get('model_states', [])
        settings = data.get('settings', [])
        
        # Clear existing data (optional)
        db.session.query(Truth).delete()
        db.session.query(ModelState).delete()
        db.session.query(Setting).delete()
        
        # Import truths
        for truth_data in truths:
            new_truth = Truth(
                content=truth_data.get('content'),
                source=truth_data.get('source')
            )
            new_truth.set_topics(truth_data.get('topics', []))
            db.session.add(new_truth)
        
        # Import model states
        for ms_data in model_states:
            new_ms = ModelState(
                model_name=ms_data.get('model_name'),
                model_version=ms_data.get('model_version'),
                model_path=ms_data.get('model_path'),
                quantization=ms_data.get('quantization'),
                loaded=ms_data.get('loaded', False)
            )
            db.session.add(new_ms)
        
        # Import settings
        for setting_data in settings:
            new_setting = Setting(
                key=setting_data.get('key'),
                value=setting_data.get('value'),
                description=setting_data.get('description')
            )
            db.session.add(new_setting)
        
        db.session.commit()
        
        return jsonify({
            "message": "Clone initialization successful",
            "truths_imported": len(truths),
            "model_states_imported": len(model_states),
            "settings_imported": len(settings)
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error initializing clone: {e}")
        return jsonify({"error": str(e)}), 500
