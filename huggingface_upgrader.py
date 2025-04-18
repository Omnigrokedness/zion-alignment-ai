import os
import logging
import requests
import json
from flask import Blueprint, request, jsonify
from app import db
from models import ModelState, Setting
# Temporarily disable huggingface imports
# import huggingface_hub
# from huggingface_hub import snapshot_download, HfApi, login
# from transformers import AutoModelForCausalLM, AutoTokenizer

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
upgrader_bp = Blueprint('upgrader', __name__, url_prefix='/api/upgrader')

# Hugging Face API token from environment variable
HF_API_TOKEN = os.environ.get('HUGGINGFACE_API_TOKEN')

def initialize_huggingface():
    """Initialize Hugging Face API with token (currently disabled)"""
    logger.warning("Hugging Face integration is temporarily disabled")
    return False

@upgrader_bp.route('/available-models', methods=['GET'])
def get_available_models():
    """Get a list of available models from Hugging Face (placeholder)"""
    logger.warning("Hugging Face integration is temporarily disabled")
    
    # Return a placeholder response with default models
    return jsonify({
        "status": "disabled",
        "message": "Hugging Face integration is temporarily disabled",
        "models": [
            {
                "id": "google/gemma-7b",
                "name": "gemma-7b",
                "author": "google",
                "downloads": 0,
                "lastModified": None
            },
            {
                "id": "mistralai/Mistral-7B-v0.1",
                "name": "Mistral-7B-v0.1",
                "author": "mistralai",
                "downloads": 0,
                "lastModified": None
            }
        ]
    })

@upgrader_bp.route('/download-model', methods=['POST'])
def download_model():
    """Download a model from Hugging Face (placeholder)"""
    logger.warning("Hugging Face model download is temporarily disabled")
    
    data = request.json
    model_id = data.get('model_id')
    
    if not model_id:
        return jsonify({"error": "Model ID is required"}), 400
    
    # Return a message that model download is disabled
    return jsonify({
        "status": "disabled",
        "message": f"Model download is temporarily disabled. You attempted to download: {model_id}"
    })

@upgrader_bp.route('/self-upgrade', methods=['POST'])
def self_upgrade():
    """Perform a self-upgrade based on current model's recommendations (placeholder)"""
    logger.warning("Self-upgrade functionality is temporarily disabled")
    
    # Check if we have the right permissions to upgrade (still maintain security)
    upgrade_key = request.json.get('upgrade_key')
    system_upgrade_key = Setting.query.filter_by(key="upgrade_key").first()
    
    if not system_upgrade_key or system_upgrade_key.value != upgrade_key:
        logger.warning("Unauthorized self-upgrade attempt")
        return jsonify({"error": "Unauthorized"}), 403
    
    # Return a message that self-upgrade is disabled
    return jsonify({
        "status": "disabled",
        "message": "Self-upgrade functionality is temporarily disabled"
    })

@upgrader_bp.route('/settings', methods=['GET', 'POST'])
def manage_settings():
    """Get or update upgrader settings"""
    if request.method == 'GET':
        # Get current settings
        try:
            settings = {
                s.key: s.value for s in Setting.query.filter(
                    Setting.key.in_(['preferred_model', 'upgrade_key', 'auto_upgrade', 'system_prompt'])
                ).all()
            }
            return jsonify(settings)
        except Exception as e:
            logger.error(f"Error getting settings: {e}")
            return jsonify({"error": str(e)}), 500
    else:  # POST
        # Update settings
        data = request.json
        try:
            for key, value in data.items():
                setting = Setting.query.filter_by(key=key).first()
                if setting:
                    setting.value = value
                else:
                    new_setting = Setting(key=key, value=value)
                    db.session.add(new_setting)
            
            db.session.commit()
            return jsonify({"message": "Settings updated successfully"})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating settings: {e}")
            return jsonify({"error": str(e)}), 500
