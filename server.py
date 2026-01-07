from flask import Flask, request, jsonify
import requests
import threading
import time
import csv
import os
import json
from datetime import datetime
from typing import Optional, Tuple

app = Flask(__name__)

# Configuration
API_KEY = open("key.key").read() 
PLACE_ID = "ChIJlf0s_HFLtokRRa9H_ouBaLM" 
CHECK_INTERVAL = 300 
CSV_FILE = "station_availability.csv"

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
    
    while True:
        print(f"Checking station availability at {datetime.now()}")
        available, update_time, error, available_count, total_count = check_station_availability(PLACE_ID)
        
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
