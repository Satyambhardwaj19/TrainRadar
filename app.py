from flask import Flask, render_template, jsonify
from train_api import get_access_token, get_departures
from stations import STATIONS

app = Flask(__name__)

# Get access token once when the app starts
# We store it in a variable so we don't fetch it every single request
access_token = get_access_token()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/trains/<station_code>')
def get_trains(station_code):
    """
    This is an API endpoint our map page will call.
    It fetches live train data and returns it as JSON.
    
    Example: visiting /api/trains/LIV returns Liverpool trains
    Example: visiting /api/trains/MAN returns Manchester trains
    """
    global access_token

    # Fetch train data from RTT API
    data = get_departures(station_code.upper(), access_token)

    if not data:
        # Return an error if something went wrong
        return jsonify({'error': 'Could not fetch train data'}), 500

    # Get list of services
    services = data.get('services') or []

    # Filter to only departing trains
    departing = [s for s in services 
                 if s.get('temporalData', {}).get('departure')]

    # Build a clean list of trains to send to the browser
    trains = []
    for service in departing:
        temporal = service.get('temporalData', {})
        departure = temporal.get('departure', {})
        meta = service.get('scheduleMetadata', {})
        destinations = service.get('destination', [])

        # Get destination name
        dest = 'Unknown'
        if destinations:
            dest = destinations[0].get('location', {}).get(
                'description', 'Unknown'
            )

        # Get scheduled time
        scheduled_raw = departure.get('scheduleAdvertised', '')
        scheduled = scheduled_raw[11:16] if scheduled_raw else 'N/A'

        # Get actual time (use forecast if actual not available yet)
        actual_raw = (departure.get('realtimeActual') or
                     departure.get('realtimeForecast') or
                     scheduled_raw)
        actual = actual_raw[11:16] if actual_raw else 'N/A'

        # Get operator name
        operator = meta.get('operator', {}).get('name', 'Unknown')

        # Get platform
        platform = service.get('locationMetadata', {}).get(
            'platform', {}
        ).get('planned', 'N/A')

        # Get unique train ID
        train_id = meta.get('identity', 'Unknown')

        trains.append({
            'id': train_id,
            'destination': dest,
            'scheduled': scheduled,
            'actual': actual,
            'operator': operator,
            'platform': platform,
        })
     # Return the data as JSON
    return jsonify({
        'station': data.get('query', {}).get(
            'location', {}
        ).get('description', station_code),
        'trains': trains
    })

@app.route('/api/stations')
def get_stations():
    """
    Returns all station coordinates as JSON
    The map page uses this to place markers
    """
    return jsonify(STATIONS)

if __name__ == '__main__':
    app.run(debug=True)