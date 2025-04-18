import os
import logging
from flask import Blueprint, request, Response, jsonify
# Disabling Twilio imports until we can install the library
# from twilio.twiml.voice_response import VoiceResponse
# from twilio.rest import Client
from app import db
from models import CallLog
# from llm_handler import generate_text
from truth_store import add_truth, search_truths
import json

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
twilio_bp = Blueprint('twilio', __name__, url_prefix='/api/twilio')

# Twilio credentials from environment variables
account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')

# Initialize Twilio client placeholder
twilio_client = None
logger.warning("Twilio integration temporarily disabled")

@twilio_bp.route('/voice', methods=['POST'])
def voice_webhook():
    """Handle incoming voice calls from Twilio (placeholder implementation)"""
    logger.debug("Received voice webhook request - DISABLED")
    
    # Get call SID for tracking
    call_sid = request.values.get('CallSid')
    caller = request.values.get('From', 'unknown')
    
    # Log the attempt
    try:
        call_log = CallLog(
            twilio_sid=call_sid or "placeholder-sid",
            caller_number=caller
        )
        db.session.add(call_log)
        db.session.commit()
        logger.debug("Call attempt logged")
    except Exception as e:
        logger.error(f"Error logging call: {e}")
        db.session.rollback()
    
    # Return a simple response indicating Twilio is not available
    return Response(
        '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Twilio integration is currently disabled.</Say></Response>', 
        mimetype='text/xml'
    )

@twilio_bp.route('/process-recording', methods=['POST'])
def process_recording():
    """Process the recording after the caller speaks (placeholder implementation)"""
    logger.debug("Processing recording - DISABLED")
    
    # Get recording URL and call SID
    recording_url = request.values.get('RecordingUrl')
    call_sid = request.values.get('CallSid')
    
    # Return a simple response
    return Response(
        '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Twilio processing is currently disabled.</Say></Response>',
        mimetype='text/xml'
    )

@twilio_bp.route('/process-transcript', methods=['POST'])
def process_transcript():
    """Process the transcribed text from the recording (placeholder implementation)"""
    logger.debug("Processing transcript - DISABLED")
    
    # Get transcript and call SID
    transcript = request.values.get('TranscriptionText')
    call_sid = request.values.get('CallSid')
    
    if not transcript:
        logger.warning(f"No transcript received for call {call_sid}")
        return Response(status=200)
    
    logger.info(f"Received transcript (not processed): {transcript}")
    
    try:
        # Update call log with transcript
        call_log = CallLog.query.filter_by(twilio_sid=call_sid).first()
        if call_log:
            call_log.transcript = transcript
            # Set a placeholder response since LLM processing is disabled
            call_log.response = "LLM processing is temporarily disabled."
            db.session.commit()
        
        # No need to return TwiML here as this is a callback endpoint
        return Response(status=200)
    except Exception as e:
        logger.error(f"Error processing transcript: {e}")
        return Response(status=500)

@twilio_bp.route('/outbound-call', methods=['POST'])
def make_outbound_call():
    """Make an outbound call with a specific message (placeholder implementation)"""
    logger.debug("Outbound call attempt - DISABLED")
    
    data = request.json
    to_number = data.get('to')
    message = data.get('message')
    
    if not to_number or not message:
        return jsonify({"error": "To number and message are required"}), 400
    
    # Return a meaningful message that the functionality is disabled
    return jsonify({
        "status": "disabled", 
        "message": "Twilio integration is temporarily disabled. The call would have been sent to " + 
                  to_number + " with the message: " + message
    })

@twilio_bp.route('/logs', methods=['GET'])
def get_call_logs():
    """Get all call logs"""
    try:
        logs = CallLog.query.order_by(CallLog.created_at.desc()).all()
        return jsonify({
            "logs": [
                {
                    "id": log.id,
                    "twilio_sid": log.twilio_sid,
                    "caller_number": log.caller_number,
                    "call_duration": log.call_duration,
                    "transcript": log.transcript,
                    "response": log.response,
                    "created_at": log.created_at.isoformat()
                } for log in logs
            ]
        })
    except Exception as e:
        logger.error(f"Error getting call logs: {e}")
        return jsonify({"error": str(e)}), 500
