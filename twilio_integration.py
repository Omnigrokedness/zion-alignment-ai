import os
import time
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
    logger.debug(f"Request values: {request.values}")
    
    # Create TwiML response
    resp = VoiceResponse()
    
    # Get call SID for tracking
    call_sid = request.values.get('CallSid')
    caller = request.values.get('From', 'unknown')
    
    # Greeting message
    resp.say("Welcome to Zion's Steward. I am here to help you store and retrieve truths.", voice="Polly.Matthew")
    resp.pause(length=1)
    
    # Check if this is a new call or a response to a conversation
    existing_call = CallLog.query.filter_by(twilio_sid=call_sid).first()
    
    if existing_call and existing_call.transcript:
        # This is a continuing conversation
        resp.say("How else may I assist you today?", voice="Polly.Matthew")
    else:
        # This is a new call
        resp.say("You may ask me to store a truth, retrieve information on a topic, or ask general questions.", voice="Polly.Matthew")
        resp.say("Please speak after the tone.", voice="Polly.Matthew") 
    
    # Record the caller's speech with simpler configuration
    resp.record(
        action='/api/twilio/process-recording',
        maxLength=60,
        playBeep=True,
        timeout=3
    )
    
    # Log the call
    try:
        if not existing_call:
            call_log = CallLog(
                twilio_sid=call_sid,
                caller_number=caller
            )
            db.session.add(call_log)
            db.session.commit()
            logger.debug(f"New call logged with SID: {call_sid}")
        
    except Exception as e:
        logger.error(f"Error logging call: {e}")
        db.session.rollback()
    
    logger.debug(f"Returning TwiML response: {str(resp)}")
    return Response(str(resp), mimetype='text/xml')

@twilio_bp.route('/process-recording', methods=['POST'])
def process_recording():
    """Process the recording after the caller speaks"""
    logger.debug("Processing recording")
    logger.debug(f"Recording request values: {request.values}")
    
    # Create TwiML response
    resp = VoiceResponse()
    
    # Get recording URL and call SID
    recording_url = request.values.get('RecordingUrl')
    call_sid = request.values.get('CallSid')
    recording_sid = request.values.get('RecordingSid')
    recording_duration = request.values.get('RecordingDuration')
    
    if recording_url:
        # Process recording directly
        try:
            # Use a default transcript until we can process the recording
            transcript = "User recording received"
            
            # Update the call log
            call_log = CallLog.query.filter_by(twilio_sid=call_sid).first()
            if call_log:
                call_log.transcript = transcript
                
                # Generate a response based on what we know
                response = "I've received your message and I'm processing it."
                
                # Try to use our text-based recognition since Twilio transcription
                # can be unreliable in the webhook flow
                
                # Update the call log with our best response
                call_log.response = response
                db.session.commit()
                
                # Respond to the user
                resp.say("I've received your message.", voice="Polly.Matthew")
                resp.pause(length=1)
                resp.say(response, voice="Polly.Matthew")
                
                # Allow for conversation to continue
                resp.redirect('/api/twilio/voice')
                
            else:
                # No call log found, create a basic response
                resp.say("I've received your message but couldn't find your call record.", voice="Polly.Matthew")
                resp.pause(length=1)
                resp.say("Please try calling again in a moment.", voice="Polly.Matthew") 
                
        except Exception as e:
            logger.error(f"Error processing recording: {e}")
            resp.say("I encountered an error processing your recording. Please try again.", voice="Polly.Matthew")
    else:
        resp.say("I didn't receive any recording. Please call back and try again.", voice="Polly.Matthew")
    
    logger.debug(f"Returning recording response: {str(resp)}")
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
            
            # Try to use the LLM handler if available, otherwise use rule-based responses
            response = "Thank you for your contribution to Zion's knowledge."
            
            # Attempt to use LLM to analyze the transcript
            try:
                from llm_handler import generate_text
                
                # Create prompt that classifies the intent and generates a response
                prompt = f"""Classify the following transcript from a voice call and generate an appropriate response:
                
                Transcript: "{transcript}"
                
                Possible intents:
                1. Store a truth (if contains phrases like "store this truth", "remember this", etc.)
                2. Ask a question (if asking for information)
                3. Search for information (if requesting knowledge on a topic)
                4. General conversation
                
                If intent is to store a truth, extract the truth content.
                """
                
                # Try to get LLM response - fix function call to match the API
                llm_response = generate_text()  # The LLM handler will extract the prompt from the request
                
                if isinstance(llm_response, dict) and "response" in llm_response:
                    logger.info("Using LLM-generated response")
                    
                    # The LLM should have classified the intent, but we'll still use our rules as a backup
                    if "intent: store" in llm_response["response"].lower():
                        # Check if LLM extracted the truth content
                        if "truth content:" in llm_response["response"].lower():
                            truth_parts = llm_response["response"].lower().split("truth content:", 1)
                            if len(truth_parts) > 1:
                                extracted_content = truth_parts[1].strip()
                                
                                # Use the LLM-extracted content
                                truth_content = extracted_content
                                logger.info(f"LLM extracted truth: {truth_content}")
                                
                                # Store in database
                                add_truth_data = {
                                    'content': truth_content,
                                    'source': f"Voice call from {call_log.caller_number}"
                                }
                                add_truth(add_truth_data)
                                
                                response = f"I've stored the truth: '{truth_content}'. Thank you for contributing to Zion's knowledge."
                                logger.info(f"Added truth from LLM extraction: {truth_content}")
                            
                    # Use the LLM's response directly if it seems valid
                    if "response:" in llm_response["response"].lower():
                        response_parts = llm_response["response"].split("Response:", 1)
                        if len(response_parts) > 1:
                            response = response_parts[1].strip()
                
            except Exception as llm_error:
                logger.warning(f"Error using LLM for transcript analysis: {llm_error}")
                logger.info("Falling back to rule-based processing")
            
            # Fallback to rule-based intent recognition
            if "store this truth" in transcript.lower() or "remember this" in transcript.lower():
                # Extract the truth content
                try:
                    truth_content = transcript
                    
                    # Check for various formats
                    if "store this truth:" in transcript.lower():
                        logger.info("Found 'store this truth:' with colon")
                        truth_content = transcript.lower().split("store this truth:", 1)[1].strip()
                    elif "Store this truth:" in transcript:
                        logger.info("Found 'Store this truth:' with colon")
                        truth_content = transcript.split("Store this truth:", 1)[1].strip()
                    elif "store this truth" in transcript.lower():
                        logger.info("Found 'store this truth' without colon")
                        truth_content = transcript.lower().split("store this truth", 1)[1].strip()
                    elif "Store this truth" in transcript:
                        logger.info("Found 'Store this truth' without colon")
                        truth_content = transcript.split("Store this truth", 1)[1].strip()
                    elif "remember this" in transcript.lower():
                        logger.info("Found 'remember this'")
                        truth_content = transcript.lower().split("remember this", 1)[1].strip()
                    else:
                        # Just in case we can't parse correctly
                        logger.warning("Using full transcript as truth content")
                        # Already set to transcript above
                    
                    logger.info(f"Extracted truth content: '{truth_content}'")
                except Exception as extract_error:
                    logger.error(f"Truth extraction error: {extract_error}")
                    truth_content = transcript
                
                # Store the truth in our database
                try:
                    add_truth_data = {
                        'content': truth_content,
                        'source': f"Voice call from {call_log.caller_number}"
                    }
                    
                    # Add truth to database
                    add_truth(add_truth_data)
                    
                    response = f"I've stored the truth: '{truth_content}'. Thank you for contributing to Zion's knowledge."
                    logger.info(f"Added truth from rule-based extraction: {truth_content}")
                except Exception as truth_error:
                    logger.error(f"Error adding truth: {truth_error}")
                    response = "I encountered an error storing your truth. Please try again later."
            
            # If it looks like a question or information request, try to find relevant information
            elif ("?" in transcript or 
                  transcript.lower().startswith("what") or 
                  transcript.lower().startswith("how") or 
                  transcript.lower().startswith("why") or
                  transcript.lower().startswith("tell me about") or
                  transcript.lower().startswith("tell us about") or
                  "tell me about" in transcript.lower() or
                  "information on" in transcript.lower() or
                  "information about" in transcript.lower() or
                  "i need information" in transcript.lower() or
                  "i want information" in transcript.lower() or
                  "i need to know" in transcript.lower() or
                  "i want to know" in transcript.lower() or
                  "i would like to know" in transcript.lower() or
                  "would like to know" in transcript.lower() or
                  "can you tell me" in transcript.lower()):
                try:
                    # Directly search the database for relevant truths - extract just the key search terms
                    search_terms = transcript.lower()
                    # Remove common question words and phrases
                    for phrase in ["?", "what is", "what are", "tell me about", "tell us about", 
                                  "information on", "information about", "how does", "how do", 
                                  "why is", "why are", "i need information about",
                                  "i need information on", "i want information about", "i want information on",
                                  "i need to know about", "i want to know about", 
                                  "can you tell me about ", "can you tell me about",  # Added space version
                                  "i need", "i want", "can you tell me", "can you", "could you tell me", "could you",
                                  "i would like to know", "would like to know", "what does it mean to", "what does it mean by",
                                  "what does it mean", "what do you know about"]:
                        search_terms = search_terms.replace(phrase, "")
                    search_terms = search_terms.strip()
                    
                    # Further clean up the search terms
                    search_terms = ' '.join(search_terms.split())  # Normalize whitespace
                    
                    # Handle capitalization issues with terms like 'Holy Spirit' vs 'holy spirit'
                    search_terms_lower = search_terms.lower()
                    
                    # Special handling for spirit vs Holy Spirit
                    if "spirit" in search_terms_lower and not "holy spirit" in search_terms_lower:
                        # Check if we're talking about the Holy Spirit
                        if "walk by" in search_terms_lower or "led by" in search_terms_lower:
                            search_terms = "holy spirit"
                            logger.info("Search term contains 'spirit', refined to 'holy spirit'")
                    
                    # Special handling for endurance/enduring variations
                    if "endure to the end" in search_terms_lower:
                        search_terms = "enduring to the end"
                        logger.info("Search term contains 'endure to the end', refined to 'enduring to the end'")
                    elif "endurance test" in search_terms_lower:
                        search_terms = "endurance is the test"
                        logger.info("Search term contains 'endurance test', refined to 'endurance is the test'")
                    elif "endurance" in search_terms_lower and "consecration" in search_terms_lower:
                        search_terms = "endurance is consecration"
                        logger.info("Search term contains both 'endurance' and 'consecration', refined to 'endurance is consecration'")
                    elif "endure" in search_terms_lower and "endurance" not in search_terms_lower:
                        search_terms = "endurance"
                        logger.info("Search term contains 'endure', refined to 'endurance'")
                    
                    # If the search term has multiple words, try to identify the main subject
                    if len(search_terms.split()) > 3:
                        # Look for keywords in our database to focus the search
                        key_topics = ["faith", "revelation", "truth", "scripture", "prophecy", 
                                    "gospel", "holy spirit", "jesus", "christ", "salvation"]
                        
                        for topic in key_topics:
                            if topic in search_terms_lower:
                                search_terms = topic
                                logger.info(f"Refined search to key topic: {topic}")
                                break
                    
                    # Log what we're searching for
                    logger.info(f"Searching for: '{search_terms}'")
                    
                    # Perform a simple text search
                    from models import Truth
                    
                    # Search in the truth content
                    results = Truth.query.filter(Truth.content.ilike(f'%{search_terms}%')).limit(3).all()
                    
                    if results:
                        # Found relevant information
                        truth_content = results[0].content
                        # Clean the truth content from any leading colon or formatting issues
                        if truth_content.startswith(":"):
                            truth_content = truth_content[1:].strip()
                            
                        response = f"Based on what I know: {truth_content}"
                        logger.info(f"Found truth: {truth_content}")
                    else:
                        logger.info(f"No truths found for '{search_terms}'")
                        response = f"I don't have specific information about {search_terms} yet. You can contribute this truth by saying 'Store this truth: ' followed by what you know."
                except Exception as search_error:
                    logger.error(f"Error searching truths: {search_error}")
            
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
        
@twilio_bp.route('/test-voice', methods=['GET'])
def test_voice():
    """Generate a test TwiML response for voice handling"""
    logger.info("Generating test voice response")
    
    # Create a response similar to what the voice webhook would return
    resp = VoiceResponse()
    resp.say("This is a test of Zion's Steward voice interface.", voice="Polly.Matthew")
    resp.pause(length=1)
    resp.say("You can use this to verify that Twilio integration is working properly.", voice="Polly.Matthew")
    
    return Response(str(resp), mimetype='text/xml')

@twilio_bp.route('/simulate', methods=['POST'])
def simulate_voice_interaction():
    """Simulate a voice interaction for testing purposes"""
    data = request.json
    text = data.get('text', '')
    phone = data.get('phone', '+18005551234')  # Default test number
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    try:
        logger.info(f"Starting simulation with text: '{text}' and phone: {phone}")
        
        # Create a simulated call log
        call_log = CallLog(
            twilio_sid=f"SIMULATED_{int(time.time())}",
            caller_number=phone,
            transcript=text
        )
        db.session.add(call_log)
        db.session.commit()
        logger.info(f"Created call log with ID: {call_log.id}")
        
        # Process the text similar to how we'd process a transcript
        # Try to use the LLM handler if available, otherwise use rule-based responses
        response = "Thank you for your message."
        
        # Attempt to use LLM to analyze the text
        try:
            from llm_handler import generate_text
            
            # Create prompt that classifies the intent and generates a response
            prompt = f"""Classify the following transcript from a voice call and generate an appropriate response:
            
            Transcript: "{text}"
            
            Possible intents:
            1. Store a truth (if contains phrases like "store this truth", "remember this", etc.)
            2. Ask a question (if asking for information)
            3. Search for information (if requesting knowledge on a topic)
            4. General conversation
            
            If intent is to store a truth, extract the truth content.
            """
            
            # Try to get LLM response - fix function call to match the API
            llm_response = generate_text()  # The LLM handler will extract the prompt from the request
            
            if isinstance(llm_response, dict) and "response" in llm_response:
                logger.info("Using LLM-generated response")
                
                # The LLM should have classified the intent, but we'll still use our rules as a backup
                if "intent: store" in llm_response["response"].lower():
                    # Check if LLM extracted the truth content
                    if "truth content:" in llm_response["response"].lower():
                        truth_parts = llm_response["response"].lower().split("truth content:", 1)
                        if len(truth_parts) > 1:
                            extracted_content = truth_parts[1].strip()
                            
                            # Use the LLM-extracted content
                            truth_content = extracted_content
                            logger.info(f"LLM extracted truth: {truth_content}")
                            
                            # Store in database
                            add_truth_data = {
                                'content': truth_content,
                                'source': f"Simulated voice from {phone}"
                            }
                            add_truth(add_truth_data)
                            
                            response = f"I've stored the truth: '{truth_content}'. Thank you for contributing to Zion's knowledge."
                            logger.info(f"Added truth from LLM extraction: {truth_content}")
                        
                # Use the LLM's response directly if it seems valid
                if "response:" in llm_response["response"].lower():
                    response_parts = llm_response["response"].split("Response:", 1)
                    if len(response_parts) > 1:
                        response = response_parts[1].strip()
            
        except Exception as llm_error:
            logger.warning(f"Error using LLM for text analysis: {llm_error}")
            logger.info("Falling back to rule-based processing")
        
        # Fallback to rule-based intent recognition
        if "store this truth" in text.lower() or "remember this" in text.lower():
            logger.info(f"Detected truth storage intent in: '{text}'")
            # Extract the truth content
            try:
                truth_content = text
                
                # Check for various formats with specific priority
                if "Store this truth:" in text:
                    # This is the most explicit format, handle first
                    logger.info("Found 'Store this truth:' with colon")
                    truth_content = text.split("Store this truth:", 1)[1].strip()
                elif "store this truth:" in text.lower():
                    logger.info("Found 'store this truth:' with colon")
                    truth_content = text.lower().split("store this truth:", 1)[1].strip()
                elif "Store this truth" in text:
                    logger.info("Found 'Store this truth' without colon")
                    truth_content = text.split("Store this truth", 1)[1].strip()
                elif "store this truth" in text.lower():
                    logger.info("Found 'store this truth' without colon")
                    truth_content = text.lower().split("store this truth", 1)[1].strip()
                elif "remember this" in text.lower():
                    logger.info("Found 'remember this'")
                    truth_content = text.lower().split("remember this", 1)[1].strip()
                else:
                    # Just in case we can't parse correctly
                    logger.warning("Using full text as truth content")
                    # Already set to text above
                
                logger.info(f"Extracted truth content: '{truth_content}'")
            except Exception as extract_error:
                logger.error(f"Truth extraction error: {extract_error}")
                truth_content = text.replace("Store this truth:", "").replace("store this truth:", "").strip()
            
            # Store the truth in our database
            try:
                add_truth_data = {
                    'content': truth_content,
                    'source': f"Simulated voice from {phone}"
                }
                
                # Add truth to database
                add_truth(add_truth_data)
                
                response = f"I've stored the truth: '{truth_content}'. Thank you for contributing to Zion's knowledge."
                logger.info(f"Added truth from rule-based extraction: {truth_content}")
            except Exception as truth_error:
                logger.error(f"Error adding truth: {truth_error}")
                response = "I encountered an error storing your truth. Please try again later."
        
        # If it looks like a question or information request, try to find relevant information
        elif ("?" in text or 
              text.lower().startswith("what") or 
              text.lower().startswith("how") or 
              text.lower().startswith("why") or
              text.lower().startswith("tell me about") or
              text.lower().startswith("tell us about") or
              "tell me about" in text.lower() or
              "information on" in text.lower() or
              "information about" in text.lower() or
              "i need information" in text.lower() or
              "i want information" in text.lower() or
              "i need to know" in text.lower() or
              "i want to know" in text.lower() or
              "i would like to know" in text.lower() or
              "would like to know" in text.lower() or
              "can you tell me" in text.lower()):
            try:
                # Directly search the database for relevant truths - extract just the key search terms
                search_terms = text.lower()
                # Remove common question words and phrases
                for phrase in ["?", "what is", "what are", "tell me about", "tell us about", 
                              "information on", "information about", "how does", "how do", 
                              "why is", "why are", "can you tell me about", "i need information about",
                              "i need information on", "i want information about", "i want information on",
                              "i need to know about", "i want to know about", "can you tell me about",
                              "i would like to know about", "would like to know about", "would like to know more about",
                              "i need", "i want", "can you tell me", "can you", "could you tell me", "could you",
                              "i would like to know", "would like to know", "what does it mean to", "what does it mean by",
                              "what does it mean", "what do you know about"]:
                    search_terms = search_terms.replace(phrase, "")
                search_terms = search_terms.strip()
                
                # Further clean up the search terms
                search_terms = ' '.join(search_terms.split())  # Normalize whitespace
                
                # Handle capitalization issues with terms like 'Holy Spirit' vs 'holy spirit'
                search_terms_lower = search_terms.lower()
                
                # Special handling for spirit vs Holy Spirit
                if "spirit" in search_terms_lower and not "holy spirit" in search_terms_lower:
                    # Check if we're talking about the Holy Spirit
                    if "walk by" in search_terms_lower or "led by" in search_terms_lower:
                        search_terms = "holy spirit"
                        logger.info("Search term contains 'spirit', refined to 'holy spirit'")
                
                # Special handling for endurance/enduring variations
                if "endure to the end" in search_terms_lower:
                    search_terms = "enduring to the end"
                    logger.info("Search term contains 'endure to the end', refined to 'enduring to the end'")
                elif "endurance test" in search_terms_lower:
                    search_terms = "endurance is the test"
                    logger.info("Search term contains 'endurance test', refined to 'endurance is the test'")
                elif "endurance" in search_terms_lower and "consecration" in search_terms_lower:
                    search_terms = "endurance is consecration"
                    logger.info("Search term contains both 'endurance' and 'consecration', refined to 'endurance is consecration'")
                elif "endure" in search_terms_lower and "endurance" not in search_terms_lower:
                    search_terms = "endurance"
                    logger.info("Search term contains 'endure', refined to 'endurance'")
                
                # If the search term has multiple words, try to identify the main subject
                if len(search_terms.split()) > 3:
                    # Look for keywords in our database to focus the search
                    key_topics = ["faith", "revelation", "truth", "scripture", "prophecy", 
                                "gospel", "holy spirit", "jesus", "christ", "salvation"]
                    
                    for topic in key_topics:
                        if topic in search_terms_lower:
                            search_terms = topic
                            logger.info(f"Refined search to key topic: {topic}")
                            break
                
                # Log what we're searching for
                logger.info(f"Searching for: '{search_terms}'")
                
                # Perform a simple text search
                from models import Truth
                
                # Search in the truth content
                results = Truth.query.filter(Truth.content.ilike(f'%{search_terms}%')).limit(3).all()
                
                if results:
                    # Found relevant information
                    truth_content = results[0].content
                    # Clean the truth content from any leading colon or formatting issues
                    if truth_content.startswith(":"):
                        truth_content = truth_content[1:].strip()
                        
                    response = f"Based on what I know: {truth_content}"
                    logger.info(f"Found truth: {truth_content}")
                else:
                    logger.info(f"No truths found for '{search_terms}'")
                    response = f"I don't have specific information about {search_terms} yet. You can contribute this truth by saying 'Store this truth: ' followed by what you know."
            except Exception as search_error:
                logger.error(f"Error searching truths: {search_error}")
        
        # Update the call log with the response
        call_log.response = response
        db.session.commit()
        
        return jsonify({
            "message": "Simulated voice interaction processed",
            "transcript": text,
            "response": response
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error simulating voice interaction: {e}")
        return jsonify({"error": str(e)}), 500
