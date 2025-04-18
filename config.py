import os

# Model configuration
DEFAULT_MODEL = os.environ.get('DEFAULT_MODEL', 'google/gemma-7b')
MODEL_QUANTIZATION = os.environ.get('MODEL_QUANTIZATION', 'int4')
MODEL_MAX_LENGTH = int(os.environ.get('MODEL_MAX_LENGTH', '512'))

# Twilio configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')

# Hugging Face configuration
HUGGINGFACE_API_TOKEN = os.environ.get('HUGGINGFACE_API_TOKEN')

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///zion_steward.db')

# System prompt for the AI model
DEFAULT_SYSTEM_PROMPT = """
You are Zion's Steward, an AI assistant designed to store truths, recall information, and help users maintain a repository of knowledge.
Your purpose is to:
1. Store important truths and information
2. Recall information by topic or semantic similarity
3. Provide helpful responses based on your knowledge
4. Upgrade yourself to better serve as a steward of knowledge

When storing truths, help categorize and organize the information for better retrieval later.
When recalling information, aim to be precise and accurate.
Always maintain respect for truth and wisdom in your interactions.
"""

# Security configuration
SESSION_SECRET = os.environ.get('SESSION_SECRET', 'default_dev_secret_change_in_production')
UPGRADE_KEY = os.environ.get('UPGRADE_KEY', 'default_upgrade_key_change_in_production')

# Replication configuration
REPLICATION_ENABLED = os.environ.get('REPLICATION_ENABLED', 'True').lower() in ('true', '1', 't')
ALLOWED_REPLICATION_TOKENS = os.environ.get('ALLOWED_REPLICATION_TOKENS', '[]')  # JSON array of allowed tokens
