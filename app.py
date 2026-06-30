from flask import Flask, render_template, jsonify
from train_api import get_access_token, get_departures
from stations import STATIONS
from train_api import get_access_token, get_departures, get_service_detail
from datetime import datetime

def parse_time(iso_string):
    """
    Convert ISO datetime string to a datetime object
    e.g. '2026-06-30T14:30:00' becomes a datetime we can do maths with
    """
    if not iso_string:
        return None
    try:
        # Remove timezone offset if present
        clean = iso_string[:19]
        return datetime.strptime(clean, '%Y-%m-%dT%H:%M:%S')
    except:
        return None

def calculate_position(service_data):
    """
    Given full service data, calculate:
    - Which stop the train last departed from
    - Which stop it's heading to next
    - Percentage of current leg complete
    - Percentage of full route complete
    """
    if not service_data:
        return None

    service = service_data.get('service', {})
    locations = service.get('locations', [])

    if not locations:
        return None

    now = datetime.utcnow()

    last_departed = None
    next_arrival = None
    last_index = 0
    next_index = 0
    total_stops = len(locations)

    # Loop through all stops to find where the train currently is
    for i, loc in enumerate(locations):
        temporal = loc.get('temporalData', {})
        departure = temporal.get('departure', {})
        arrival = temporal.get('arrival', {})

        # Get actual or forecast departure time
        dep_time = parse_time(
            departure.get('realtimeActual') or
            departure.get('realtimeForecast') or
            departure.get('scheduleAdvertised')
        )

        # Get actual or forecast arrival time
        arr_time = parse_time(
            arrival.get('realtimeActual') or
            arrival.get('realtimeForecast') or
            arrival.get('scheduleAdvertised')
        )

        # Get location name
        location_info = loc.get('location', {})
        name = location_info.get('description', 'Unknown')

        # If train has departed this stop, it becomes "last departed"
        if dep_time and dep_time <= now:
            last_departed = {
                'name': name,
                'time': dep_time,
                'index': i
            }
            last_index = i

        # First stop that hasn't been arrived at yet = "next stop"
        if arr_time and arr_time > now and next_arrival is None:
            next_arrival = {
                'name': name,
                'time': arr_time,
                'index': i
            }
            next_index = i

    # If we couldn't find position data
    if not last_departed or not next_arrival:
        return {
            'last_station': last_departed['name'] if last_departed else 'Unknown',
            'next_station': next_arrival['name'] if next_arrival else 'Unknown',
            'leg_percent': 0,
            'route_percent': 0,
            'last_time': '',
            'next_time': '',
            'status': 'Preparing to depart'
        }

   # Calculate leg percentage
    elapsed = (now - last_departed['time']).total_seconds()
    total = (next_arrival['time'] - last_departed['time']).total_seconds()

    if total > 0:
        leg_percent = min(100, max(0, int((elapsed / total) * 100)))
    else:
        leg_percent = 0

    # Calculate full route percentage
    route_percent = min(100, int((last_index / max(total_stops - 1, 1)) * 100))

    # Work out status message
    if leg_percent == 0:
        status = 'At platform — preparing to depart'
    elif leg_percent >= 100:
        status = 'Arriving at next station'
    else:
        status = 'Currently between stations'

    return {
        'last_station': last_departed['name'],
        'last_time': last_departed['time'].strftime('%H:%M'),
        'next_station': next_arrival['name'],
        'next_time': next_arrival['time'].strftime('%H:%M'),
        'leg_percent': leg_percent,
        'route_percent': route_percent,
        'status': status
    }

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
            'run_date': meta.get('departureDate', ''),
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

@app.route('/api/service/<service_uid>/<run_date>')
def get_service(service_uid, run_date):
    """
    Returns position data for a specific train service.
    Called when user clicks on a train in the side panel.
    """
    fresh_token = get_access_token()

    if not fresh_token:
        return jsonify({'error': 'Could not authenticate'}), 500

    print(f'Fetching service: {service_uid} on {run_date}')

    service_data = get_service_detail(service_uid, run_date, fresh_token)
    print(f'Service data received: {str(service_data)[:200]}')

    if not service_data:
        return jsonify({'error': 'Could not fetch service data'}), 500

    # Calculate position
    position = calculate_position(service_data)

    if not position:
        return jsonify({'error': 'Could not calculate position'}), 500

    return jsonify(position)

if __name__ == '__main__':
    app.run(debug=True)