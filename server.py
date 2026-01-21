from flask import Flask, request, jsonify
import requests
import threading
import time
import csv
import os
import json
import jwt
import httpx
import uuid
from datetime import datetime
from typing import Optional, Tuple

app = Flask(__name__)

# Configuration
API_KEY = open("key.key").read() 
PLACE_ID = "ChIJlf0s_HFLtokRRa9H_ouBaLM" 
CHECK_INTERVAL = 120 
CSV_FILE = "station_availability.csv"
NOTIFICATION_SERVER = "api.sandbox.push.apple.com:443"
DEVICE_TOKEN = "c0d33fed8655316b4046394091ede6ec9478f16fd9fdd6111d7a6dc877753379"

# Global state
station_status = {
    "available": False,
    "last_update_time": None,
    "last_check": None,
    "error": None
}

def initialize_csv():
    """Create CSV file with headers if it doesn't exist."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'available', 'available_count', 'total_count', 'update_time', 'error'])

def log_to_csv(available: bool, available_count: int, total_count: int, 
               update_time: Optional[str], error: Optional[str]):
    """Append availability check to CSV file."""
    try:
        with open(CSV_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                available,
                available_count,
                total_count,
                update_time if update_time else '',
                error if error else ''
            ])
    except Exception as e:
        print(f"Error writing to CSV: {e}")

def check_station_availability(place_id: str) -> Tuple[bool, Optional[str], Optional[str], int, int]:
    """
    Check EV charging station availability.
    Returns: (available, update_time, error_message, available_count, total_count)
    """
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "evChargeOptions"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Find the connector with the smallest maxChargeRateKw
        ev_options = data.get("evChargeOptions", {})
        connectors = ev_options.get("connectorAggregation", [])
        
        if connectors:
            # Sort by maxChargeRateKw and get the slowest connector
            slowest_connector = min(
                connectors,
                key=lambda x: x.get("maxChargeRateKw", 0)
            )
            
            available_count = slowest_connector.get("availableCount", 0)
            total_count = slowest_connector.get("count", 0)
            available = available_count > 0
            update_time = slowest_connector.get("availabilityLastUpdateTime")
            
            return (available, update_time, None, available_count, total_count)
        
        return (False, None, "No connector data available", 0, 0)
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Error fetching station status: {str(e)}"
        print(error_msg)
        return (False, None, error_msg, 0, 0)

def background_checker():
    """Background thread that checks station availability every 5 minutes."""
    global station_status
    
    # Track the last availability state
    last_available = None
    
    while True:
        print(f"Checking station availability at {datetime.now()}")
        available, update_time, error, available_count, total_count = check_station_availability(PLACE_ID)
        
        # Check if status changed from unavailable to available
        if (not last_available) and available:
            print("Charger is now available! Sending notification...")
            try:
                # Generate JWT token
                jwt_token = generate_apns_token()
                
                # Send push notification
                status_code, response, apns_id = send_apns_notification(
                    device_token=DEVICE_TOKEN,
                    alert_message='Charger is now available',
                    jwt_token=jwt_token,
                    sandbox=True
                )
                
                print(f"Notification sent - Status: {status_code}, APNs ID: {apns_id}")
            except Exception as e:
                print(f"Failed to send notification: {e}")
        
        # Update the last available state
        last_available = available
        
        station_status.update({
            "available": available,
            "last_update_time": update_time,
            "last_check": datetime.now().isoformat(),
            "error": error
        })
        
        # Log to CSV
        log_to_csv(available, available_count, total_count, update_time, error)
        
        time.sleep(CHECK_INTERVAL)
@app.route('/status', methods=['GET'])
def get_status():
    """Get the current availability status of the charging station."""
    return jsonify({
        "available": station_status["available"],
        "last_update_time": station_status["last_update_time"],
        "last_check": station_status["last_check"],
        "error": station_status["error"]
    })

@app.route('/check-now', methods=['POST'])
def check_now():
    """Manually trigger an immediate availability check."""
    available, update_time, error, available_count, total_count = check_station_availability(PLACE_ID)
    
    station_status.update({
        "available": available,
        "last_update_time": update_time,
        "last_check": datetime.now().isoformat(),
        "error": error
    })
    
    # Log to CSV
    log_to_csv(available, available_count, total_count, update_time, error)
    
    return jsonify({
        "available": available,
        "last_update_time": update_time,
        "last_check": station_status["last_check"],
        "error": error
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "running", "last_check": station_status["last_check"]})

TOKENS_FILE = 'device_tokens.json'

def load_tokens():
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_tokens(tokens):
    with open(TOKENS_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)

@app.route('/api/device-token', methods=['POST'])
def register_device_token():
    try:
        data = request.get_json()
        
        if not data or 'device_token' not in data:
            return jsonify({'error': 'device_token is required'}), 400
        
        device_token = data['device_token']
        print(device_token)
        
        # Load existing tokens
        tokens = load_tokens()
        
        # Save token with timestamp
        tokens[device_token] = {
            'token': device_token,
            'registered_at': datetime.utcnow().isoformat(),
            'last_updated': datetime.utcnow().isoformat()
        }
        
        # Save to file
        save_tokens(tokens)
        
        print(f"Device token registered: {device_token}")
        
        return jsonify({
            'success': True,
            'message': 'Device token registered successfully'
        }), 200
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

def generate_apns_token(key_id_file='key.id', p8_file='AuthKey.p8', team_id='SM7F898GQH'):
    # Read the Key ID from file
    with open(key_id_file, 'r') as f:
        key_id = f.read().strip()
    
    # Read the private key from .p8 file
    with open(p8_file, 'r') as f:
        private_key = f.read()
    
    # Create the token headers
    headers = {
        'alg': 'ES256',
        'kid': key_id
    }
    
    # Create the token payload
    payload = {
        'iss': team_id,
        'iat': int(time.time())
    }
    
    # Generate the JWT token
    token = jwt.encode(
        payload,
        private_key,
        algorithm='ES256',
        headers=headers
    )
    
    return token

def send_apns_notification(device_token, alert_message, jwt_token, 
                          bundle_id='com.technaplex.blinkify',
                          sandbox=True,
                          apns_priority=10,
                          apns_expiration=0,
                          apns_id=None):
    # Determine the APNs server
    host = 'api.sandbox.push.apple.com' if sandbox else 'api.push.apple.com'
    port = 443
    
    # Build the URL path with device token
    path = f'/3/device/{device_token}'
    url = f'https://{host}:{port}{path}'
    
    # Generate apns-id if not provided
    if apns_id is None:
        apns_id = str(uuid.uuid4())
    
    # Build headers
    headers = {
        'authorization': f'bearer {jwt_token}',
        'apns-id': apns_id,
        'apns-push-type': 'alert',
        'apns-expiration': str(apns_expiration),
        'apns-priority': str(apns_priority),
        'apns-topic': bundle_id
    }
    
    # Build the payload
    payload = {
        'aps': {
            'alert': alert_message
        }
    }
    
    # Send the notification using HTTP/2
    with httpx.Client(http2=True) as client:
        response = client.post(
            url,
            headers=headers,
            json=payload,
            timeout=10.0
        )
    
    return response.status_code, response.text, apns_id


if __name__ == '__main__':
    # Initialize CSV file
    initialize_csv()
    
    # Start background checker thread
    checker_thread = threading.Thread(target=background_checker, daemon=True)
    checker_thread.start()
    
    # Run initial check
    print("Running initial availability check...")
    available, update_time, error, available_count, total_count = check_station_availability(PLACE_ID)
    station_status.update({
        "available": available,
        "last_update_time": update_time,
        "last_check": datetime.now().isoformat(),
        "error": error
    })
    
    # Log initial check to CSV
    log_to_csv(available, available_count, total_count, update_time, error)
    
    # Start Flask app
    app.run(host='0.0.0.0', port=5121, debug=False)
