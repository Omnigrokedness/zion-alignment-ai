import os
import logging
from flask import Blueprint, request, Response, jsonify
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from app import db
from models import CallLog
# LLM is still disabled as we don't have the ML packages
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
phone_number = os.environ.get('TWILIO_PHONE_NUMBER')

# Initialize Twilio client
twilio_client = None
if account_sid and auth_token:
    try:
        twilio_client = Client(account_sid, auth_token)
        logger.info(f"Twilio client initialized with phone number: {phone_number}")
    except Exception as e:
        logger.error(f"Error initializing Twilio client: {e}")
else:
    logger.warning("Twilio credentials not found in environment variables")

@twilio_bp.route('/voice', methods=['POST'])
def voice_webhook():
    """Handle incoming voice calls from Twilio"""
    logger.debug("Received voice webhook request")
    
    # Create TwiML response
    resp = VoiceResponse()
    
    # Get call SID for tracking
    call_sid = request.values.get('CallSid')
    caller = request.values.get('From', 'unknown')
    
    # Greeting message
    resp.say("Welcome to Zion's Steward. I am here to help you store and retrieve truths. Please speak after the tone.", voice="Polly.Matthew")
    resp.pause(length=1)
    resp.say("You may ask me to store a truth, retrieve information on a topic, or ask general questions.", voice="Polly.Matthew")
    
    # Record the caller's speech
    resp.record(
        action='/api/twilio/process-recording',
        maxLength=60,
        playBeep=True,
        timeout=5,
        transcribe=True,
        transcribeCallback='/api/twilio/process-transcript'
    )
    
    # Log the call
    try:
        call_log = CallLog(
            twilio_sid=call_sid,
            caller_number=caller
        )
        db.session.add(call_log)
        db.session.commit()
        logger.debug(f"Call logged with SID: {call_sid}")
    except Exception as e:
        logger.error(f"Error logging call: {e}")
        db.session.rollback()
    
    return Response(str(resp), mimetype='text/xml')

@twilio_bp.route('/process-recording', methods=['POST'])
def process_recording():
    """Process the recording after the caller speaks"""
    logger.debug("Processing recording")
    
    # Create TwiML response
    resp = VoiceResponse()
    
    # Get recording URL and call SID
    recording_url = request.values.get('RecordingUrl')
    call_sid = request.values.get('CallSid')
    
    if recording_url:
        # We'll process the transcript in the transcribe callback
        resp.say("I've received your message. Please wait while I process it.", voice="Polly.Matthew")
        resp.pause(length=2)
        resp.say("Thank you for your contribution to Zion's knowledge base.", voice="Polly.Matthew")
    else:
        resp.say("I didn't receive any recording. Please call back and try again.", voice="Polly.Matthew")
    
    return Response(str(resp), mimetype='text/xml')

@twilio_bp.route('/process-transcript', methods=['POST'])
def process_transcript():
    """Process the transcribed text from the recording"""
    logger.debug("Processing transcript")
    
    # Get transcript and call SID
    transcript = request.values.get('TranscriptionText')
    call_sid = request.values.get('CallSid')
    
    if not transcript:
        logger.warning(f"No transcript received for call {call_sid}")
        return Response(status=200)
    
    logger.info(f"Received transcript: {transcript}")
    
    try:
        # Update call log with transcript
        call_log = CallLog.query.filter_by(twilio_sid=call_sid).first()
        if call_log:
            call_log.transcript = transcript
            
            # Simple response generation until we can install ML libraries
            response = "Thank you for your contribution to Zion's knowledge."
            
            # Check if this is a truth to store
            if "store this truth" in transcript.lower() or "remember this" in transcript.lower():
                # Extract the truth content
                if "store this truth" in transcript.lower():
                    truth_content = transcript.lower().split("store this truth", 1)[1].strip()
                else:
                    truth_content = transcript.lower().split("remember this", 1)[1].strip()
                
                # Store the truth in our database
                try:
                    add_truth_data = {
                        'content': truth_content,
                        'source': f"Voice call from {call_log.caller_number}"
                    }
                    
                    # Add truth to database
                    from truth_store import add_truth
                    add_truth(add_truth_data)
                    
                    response = f"I've stored the truth: '{truth_content}'. Thank you for contributing to Zion's knowledge."
                    logger.info(f"Added truth from transcript: {truth_content}")
                except Exception as truth_error:
                    logger.error(f"Error adding truth: {truth_error}")
                    response = "I encountered an error storing your truth. Please try again later."
            
            # Update call log with response
            call_log.response = response
            db.session.commit()
            
            # Optionally call back to confirm (would need LLM for more complex interactions)
            if twilio_client and call_log and "store this truth" in transcript.lower():
                try:
                    twilio_client.calls.create(
                        to=call_log.caller_number,
                        from_=phone_number,
                        twiml=f'<Response><Say voice="Polly.Matthew">{response}</Say></Response>'
                    )
                    logger.info(f"Callback sent to {call_log.caller_number}")
                except Exception as callback_error:
                    logger.error(f"Error making callback: {callback_error}")
        
        # No need to return TwiML here as this is a callback endpoint
        return Response(status=200)
    except Exception as e:
        logger.error(f"Error processing transcript: {e}")
        return Response(status=500)

@twilio_bp.route('/outbound-call', methods=['POST'])
def make_outbound_call():
    """Make an outbound call with a specific message"""
    logger.debug("Outbound call attempt")
    
    if not twilio_client:
        return jsonify({"error": "Twilio client not initialized"}), 500
    
    data = request.json
    to_number = data.get('to')
    message = data.get('message')
    
    if not to_number or not message:
        return jsonify({"error": "To number and message are required"}), 400
    
    try:
        # Make the call
        call = twilio_client.calls.create(
            to=to_number,
            from_=phone_number,
            twiml=f'<Response><Say voice="Polly.Matthew">{message}</Say></Response>'
        )
        
        logger.info(f"Outbound call initiated to {to_number}, SID: {call.sid}")
        
        return jsonify({
            "message": "Call initiated successfully",
            "call_sid": call.sid
        })
    except Exception as e:
        logger.error(f"Error making outbound call: {e}")
        return jsonify({"error": str(e)}), 500

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
