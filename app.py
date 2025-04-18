import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Database setup
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_key_for_testing")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///zion_steward.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database
db.init_app(app)

# Import components after app creation to avoid circular imports
from twilio_integration import twilio_bp
from llm_handler import llm_bp
from truth_store import truth_bp
from huggingface_upgrader import upgrader_bp
from replication import replication_bp

# Register blueprints
app.register_blueprint(twilio_bp)
app.register_blueprint(llm_bp)
app.register_blueprint(truth_bp)
app.register_blueprint(upgrader_bp)
app.register_blueprint(replication_bp)

# Create database tables
with app.app_context():
    import models
    db.create_all()
    logger.info("Database tables created")

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/truths')
def truths():
    from models import Truth
    all_truths = Truth.query.all()
    return render_template('truths.html', truths=all_truths)

@app.route('/settings')
def settings():
    from models import Setting
    settings = Setting.query.all()
    return render_template('settings.html', settings=settings)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('layout.html', message="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('layout.html', message="Internal server error"), 500
