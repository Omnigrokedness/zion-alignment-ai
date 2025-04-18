from app import db
from datetime import datetime
from flask_login import UserMixin
import json

# Add User model from development guidelines
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # ensure password hash field has length of at least 256
    password_hash = db.Column(db.String(256))

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Setting {self.key}>'

class Truth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(256))
    vector_embedding = db.Column(db.Text)  # JSON string of vector embedding
    topics = db.Column(db.Text)  # JSON string of topics
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Truth {self.id}>'
    
    def get_vector(self):
        """Return the vector embedding as a list of floats"""
        if self.vector_embedding:
            return json.loads(self.vector_embedding)
        return None
    
    def set_vector(self, vector):
        """Store vector embedding as JSON string"""
        if vector is not None:
            self.vector_embedding = json.dumps(vector)
    
    def get_topics(self):
        """Return topics as a list"""
        if self.topics:
            return json.loads(self.topics)
        return []
    
    def set_topics(self, topics):
        """Store topics as JSON string"""
        if topics is not None:
            self.topics = json.dumps(topics)

class ModelState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(128), nullable=False)
    model_version = db.Column(db.String(64), nullable=False)
    model_path = db.Column(db.String(256), nullable=False)
    quantization = db.Column(db.String(32), default="int4")
    loaded = db.Column(db.Boolean, default=False)
    last_used = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ModelState {self.model_name} v{self.model_version}>'

class CallLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    twilio_sid = db.Column(db.String(64), unique=True)
    call_duration = db.Column(db.Integer)
    caller_number = db.Column(db.String(32))
    transcript = db.Column(db.Text)
    response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CallLog {self.id}>'

class ReplicationNode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    endpoint = db.Column(db.String(256), nullable=False)
    api_key = db.Column(db.String(256))
    status = db.Column(db.String(32), default="inactive")
    last_sync = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ReplicationNode {self.name}>'
