import requests
import os
from dotenv import load_dotenv

load_dotenv()
REFRESH_TOKEN = os.getenv('RTT_TOKEN')

def get_access_token():
    """Exchange refresh token for working access token"""
    url = 'https://data.rtt.io/api/get_access_token'
    headers = {'Authorization': f'Bearer {REFRESH_TOKEN}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('token')
    else:
        print(f'Token error {response.status_code}: {response.text[:200]}')
        return None

def get_departures(station_code, access_token):
    """
    Fetch live departures from a UK station
    station_code = 3-letter CRS code e.g. LIV for Liverpool
    Returns the full JSON response as a Python dictionary
    """
    url = f'https://data.rtt.io/gb-nr/location?code={station_code}'

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Version': '2026-06-28'
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f'Error {response.status_code}: {response.text[:200]}')
        return None

def format_time(iso_string):
    """
    Convert ISO datetime like '2026-06-30T14:30:00+01:00'
    to readable '14:30'
    """
    if not iso_string:
        return 'N/A'
    try:
        # Time is between T and the timezone offset
        time_part = iso_string.split('T')[1][:5]
        return time_part
    except:
        return 'N/A'

def get_service_detail(service_uid, run_date, access_token):
    """
    Fetch the full route detail for a specific train service.
    service_uid = unique ID like 'W34264'
    run_date = date like '2026-06-30'
    Returns full list of stops with times
    """
    url = f'https://data.rtt.io/gb-nr/service?uniqueIdentity={service_uid}:{run_date}'
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Version': '2026-06-28'
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f'Service detail error {response.status_code}: {response.text[:200]}')
        return None

if __name__ == '__main__':
    print('Step 1: Getting access token...')
    access_token = get_access_token()

    if not access_token:
        print('Failed to get access token.')
    else:
        print('Got access token!')
        print()
        print('Fetching live trains from Liverpool Lime Street...')
        print()

        data = get_departures('LIV', access_token)

        if data:
            print('Full response keys:', data.keys())
            print('Full response:', str(data)[:1000])
            # Print station name
            location = data.get('query', {}).get('location', {})
            print(f"Station: {location.get('description', 'Unknown')}")
            print()

            # Get the list of services
            services = data.get('services', [])

            if not services:
                print('No services found right now.')
                print('(This is normal overnight — try again after 5am)')
            else:
                print(f'Found {len(services)} services. Showing first 5:')
                print()

                # Filter to only show services that have a departure time
                departing = [s for s in services if s.get('temporalData', {}).get('departure')]
                print(f'Found {len(departing)} departing services. Showing first 5:')
                print()

                for service in departing[:5]:
                    # Get schedule metadata
                    meta = service.get('scheduleMetadata', {})
                    temporal = service.get('temporalData', {})
                    departure = temporal.get('departure', {})

                    # Get destination
                    destinations = service.get('destination', [])
                    dest = destinations[0].get('location', {}).get('description', 'Unknown') if destinations else 'Unknown'

                    # Get times
                    scheduled = format_time(departure.get('scheduleAdvertised'))
                    actual = format_time(
                        departure.get('realtimeActual') or
                        departure.get('realtimeForecast') or
                        departure.get('scheduleAdvertised')
                    )

                    # Get operator
                    operator = meta.get('operator', {}).get('name', 'Unknown')

                    print(f'To:        {dest}')
                    print(f'Scheduled: {scheduled}')
                    print(f'Actual:    {actual}')
                    print(f'Operator:  {operator}')
                    print('---')