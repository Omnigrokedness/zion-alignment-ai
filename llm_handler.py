import os
import logging
import threading
from flask import Blueprint, jsonify, request
# import torch
# from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from app import db
from models import ModelState, Setting

# Configure logging
logger = logging.getLogger(__name__)

# Setup blueprint
llm_bp = Blueprint('llm', __name__, url_prefix='/api/llm')

# Global variables
model = None
tokenizer = None
generation_pipeline = None
model_lock = threading.Lock()

def initialize_model():
    """Initialize the language model and tokenizer"""
    global model, tokenizer, generation_pipeline
    
    try:
        with model_lock:
            # Check if model is already loaded
            if model is not None and tokenizer is not None:
                return True
            
            # Get current model info from database
            with db.session() as session:
                model_state = ModelState.query.filter_by(loaded=True).first()
                
                if not model_state:
                    # Default to Gemma 7B if no model is set
                    default_model = "google/gemma-7b"
                    model_state = ModelState(
                        model_name="gemma-7b",
                        model_version="1.0",
                        model_path=default_model,
                        quantization="int4",
                        loaded=True
                    )
                    session.add(model_state)
                    session.commit()
                    logger.info(f"No model found in DB, defaulting to {default_model}")
                
                logger.info(f"Loading model: {model_state.model_path} with {model_state.quantization} quantization")
                
                # Load the model with quantization
                if model_state.quantization == "int4":
                    try:
                        # Load int4 quantized model
                        model = AutoModelForCausalLM.from_pretrained(
                            model_state.model_path,
                            torch_dtype=torch.float16,
                            device_map="auto",
                            load_in_4bit=True
                        )
                    except Exception as e:
                        logger.error(f"Error loading int4 model: {e}")
                        # Fallback to int8
                        model = AutoModelForCausalLM.from_pretrained(
                            model_state.model_path,
                            torch_dtype=torch.float16,
                            device_map="auto",
                            load_in_8bit=True
                        )
                else:
                    # Load int8 quantized model
                    model = AutoModelForCausalLM.from_pretrained(
                        model_state.model_path,
                        torch_dtype=torch.float16,
                        device_map="auto",
                        load_in_8bit=True
                    )
                
                # Load tokenizer
                tokenizer = AutoTokenizer.from_pretrained(model_state.model_path)
                
                # Create generation pipeline
                generation_pipeline = pipeline(
                    "text-generation",
                    model=model,
                    tokenizer=tokenizer
                )
                
                logger.info("Model loaded successfully")
                return True
    except Exception as e:
        logger.error(f"Failed to initialize model: {e}")
        return False

@llm_bp.route('/generate', methods=['POST'])
def generate_text():
    """Generate text from the language model"""
    if not initialize_model():
        return jsonify({"error": "Failed to initialize model"}), 500
    
    data = request.json
    prompt = data.get('prompt', '')
    max_length = data.get('max_length', 512)
    
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400
    
    try:
        # Get system prompt from settings
        system_prompt = Setting.query.filter_by(key="system_prompt").first()
        if system_prompt:
            full_prompt = f"{system_prompt.value}\n\nUser: {prompt}\n\nAssistant:"
        else:
            full_prompt = f"User: {prompt}\n\nAssistant:"
        
        # Generate response
        response = generation_pipeline(
            full_prompt,
            max_length=max_length,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            num_return_sequences=1
        )[0]['generated_text']
        
        # Extract just the assistant's response
        try:
            assistant_response = response.split("Assistant:")[1].strip()
        except IndexError:
            assistant_response = response.replace(full_prompt, "").strip()
        
        return jsonify({"response": assistant_response})
    except Exception as e:
        logger.error(f"Error generating text: {e}")
        return jsonify({"error": str(e)}), 500

@llm_bp.route('/model-info', methods=['GET'])
def model_info():
    """Get information about the currently loaded model"""
    model_state = ModelState.query.filter_by(loaded=True).first()
    if model_state:
        return jsonify({
            "model_name": model_state.model_name,
            "model_version": model_state.model_version,
            "model_path": model_state.model_path,
            "quantization": model_state.quantization,
            "last_used": model_state.last_used.isoformat() if model_state.last_used else None
        })
    return jsonify({"error": "No model currently loaded"}), 404

@llm_bp.route('/load-model', methods=['POST'])
def load_model():
    """Load a specific model"""
    data = request.json
    model_path = data.get('model_path')
    quantization = data.get('quantization', 'int4')
    
    if not model_path:
        return jsonify({"error": "Model path is required"}), 400
    
    try:
        # Update database
        with db.session() as session:
            # Set all models to not loaded
            ModelState.query.update({ModelState.loaded: False})
            
            # Check if model already exists
            existing_model = ModelState.query.filter_by(model_path=model_path).first()
            if existing_model:
                existing_model.loaded = True
                existing_model.quantization = quantization
            else:
                # Extract model name from path
                model_name = model_path.split('/')[-1]
                new_model = ModelState(
                    model_name=model_name,
                    model_version="1.0",  # Default version
                    model_path=model_path,
                    quantization=quantization,
                    loaded=True
                )
                session.add(new_model)
            
            session.commit()
        
        # Reset global model variables to trigger reload
        global model, tokenizer, generation_pipeline
        with model_lock:
            model = None
            tokenizer = None
            generation_pipeline = None
        
        # Initialize the new model
        success = initialize_model()
        if success:
            return jsonify({"message": f"Model {model_path} loaded successfully"})
        else:
            return jsonify({"error": "Failed to load model"}), 500
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return jsonify({"error": str(e)}), 500
