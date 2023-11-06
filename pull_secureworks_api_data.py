import json
import os
import pathlib
import string

import requests

# Set the variables for the access token and tenant ID
ACCESS_TOKEN = 'PUT YOUR ACCESS TOKEN HERE (IT SHOULD BE LONG)'
TENANT_ID = 'PUT YOUR TENANT ID HERE (6 digits)'

# Prepare the headers for the request
headers = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'X-Tenant-Context': TENANT_ID,
    'Content-type': 'application/json'
}


# Valid filename character function
def valid_filename(name):
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
    filename = ''.join(c for c in name if c in valid_chars)
    return filename.replace(" ", "_")


# Additional function to download latest threat intel publications
def download_latest_threat_intel_publications():
    # Create a directory for the latest threat intel publications
    os.makedirs('downloads/latest_threat_intel_publications', exist_ok=True)

    # GraphQL query payload
    latest_publications_payload = {
        "query": """
        query threatLatestPublications($from: Int!, $size: Int!) {
            threatLatestPublications(from: $from, size: $size) {
                id 
                Type 
                Name 
                Description 
                Published 
                Content 
                TLP 
                VID 
                ReportID 
                Reference 
                Category 
                Language
            }
        }
        """,
        "variables": {
            "from": 0,
            "size": 10
        }
    }

    # Make the POST request for the latest publications
    response = requests.post(
        'https://api.ctpx.secureworks.com/graphql',
        headers=headers,
        json=latest_publications_payload
    )

    if response.status_code == 200:
        publications = response.json().get('data', {}).get('threatLatestPublications', [])
        for publication in publications:
            pub_id = publication.get('id', 'unknown_id')
            file_name = valid_filename(publication.get('Name', 'unknown') + '.json')
            pretty_file_name = "PRETTY_" + file_name
            path = pathlib.Path('downloads/latest_threat_intel_publications') / file_name
            pretty_path = pathlib.Path('downloads/latest_threat_intel_publications') / pretty_file_name
            with open(path, 'w', encoding='utf-8') as file:
                json.dump(publication, file, ensure_ascii=False)
            with open(pretty_path, 'w', encoding='utf-8') as pretty_file:
                json.dump(publication, pretty_file, ensure_ascii=False, indent=4)
            print(f"Downloaded publication: {file_name}")
    else:
        print(f"Failed to download latest threat intelligence publications with status code {response.status_code}")


# Function to download all threat intel indicator lists
def download_threat_intel_lists_and_watchlists():
    intel_list_url = 'https://api.ctpx.secureworks.com/intel-requester/ti-list/latest'
    intel_list_response = requests.get(intel_list_url, headers=headers)

    # Create a directory for the threat intel indicator lists
    os.makedirs('downloads/threat_intel_indicator_lists', exist_ok=True)
    os.makedirs('downloads/watchlist_indicators_by_type', exist_ok=True)

    if intel_list_response.status_code == 200:
        intel_lists = intel_list_response.json()
        for intel_list in intel_lists:
            list_name = valid_filename(intel_list['name'])
            list_link = intel_list['link']
            # Check for a valid response before attempting to save the file
            file_response = requests.get(list_link)
            if file_response.status_code == 200:
                # Define a path object using pathlib to handle file paths correctly
                path = pathlib.Path('downloads/threat_intel_indicator_lists') / f"{list_name}"
                with open(path, 'wb') as file:
                    file.write(file_response.content)
            else:
                print(f'Failed to download the list: {list_name}')
    else:
        print('Failed to retrieve threat intel indicator lists.')

    # Preparing the headers for GraphQL request
    graphql_headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'X-Tenant-Context': TENANT_ID,
        'Content-type': 'application/json'
    }

    # Watchlist types we're interested in
    type_names = [
        'CTU Botnet Indicators IP List - MSS',
        'CTU Threat Group Indicators IP List - MSS',
        'Third Party Threat Group Indicators IP List - MSS',
        'CTU Botnet Indicators Domain List - MSS',
        'CTU Threat Group Indicators Domain List - MSS',
        'Third Party Threat Group Indicators Domain List - MSS'
    ]

    # Downloading the watchlist by type
    for list_name in type_names:
        list_type = 'IP' if 'IP List' in list_name else 'DOMAIN'
        watchlist_payload = {
            "query": """
                query threatWatchlist($type: ThreatParentType!) {
                    threatWatchlist(type: $type) {
                        id
                        description
                        indicator_class
                        label
                        type
                    }
                }
            """,
            "variables": {
                "type": list_type
            }
        }
        response = requests.post(
            'https://api.ctpx.secureworks.com/graphql',
            headers=graphql_headers,
            json=watchlist_payload
        )

        if response.status_code == 200:
            # Process the response and save to files
            watchlists = response.json().get('data', {}).get('threatWatchlist', [])
            print(f"Downloaded {len(watchlists)} items from watchlist type {list_type}")

            # Save the response to a file
            filename = valid_filename(list_name) + '.json'
            pretty_file_name = "PRETTY_" + filename
            path = pathlib.Path('downloads/watchlist_indicators_by_type') / filename
            pretty_path = pathlib.Path('downloads/watchlist_indicators_by_type') / pretty_file_name
            with open(path, 'w') as file:  # Writing as text, assuming the data is JSON serializable
                file.write(str(watchlists))
            with open(pretty_path, 'w', encoding='utf-8') as pretty_file:
                json.dump(watchlists, pretty_file, ensure_ascii=False, indent=4)
        else:
            print(f"Failed to download watchlist for {list_name}")


# Initial payload for creating the client
create_client_payload = {
    "query": """
    mutation createClient($name: String!, $roles: [ID!]) {
        createClient(name: $name, roles: $roles) {
            client {
                id
                name
                client_id
                roles
                role_assignments {
                    id
                    tenant_id
                    role_id
                    role_name
                    expires_at
                }
                tenant_id
                created_at
                updated_at
                created_by
                updated_by
                environment
            }
            client_secret
        }
    }
    """,
    "variables": {
        "name": "Pull From SecureWorks API"
    }
}

# Make the POST request to create the client
response = requests.post('https://api.ctpx.secureworks.com/graphql', headers=headers, json=create_client_payload)

# Check for response status and process the response
if response.status_code == 200:
    response_data = response.json()
    if 'errors' in response_data and any(
            "existing client in tenant" in error['message'] for error in response_data['errors']):
        print("A client already exists for tenant ID " + TENANT_ID)
        # Query to fetch the existing client information
        get_client_payload = {
            "query": """
                query {
                    clients {
                        id
                        name
                        client_id
                        roles
                        role_assignments {
                            id
                            tenant_id
                            role_id
                            role_name
                            expires_at
                        }
                        tenant_id
                        created_at
                        updated_at
                        created_by
                        updated_by
                        environment
                    }
                }
            """
        }

        # Make the POST request to get the existing client's information
        client_response = requests.post('https://api.ctpx.secureworks.com/graphql', headers=headers,
                                        json=get_client_payload)
        if client_response.status_code == 200:
            clients_data = client_response.json()['data']['clients']
            if len(clients_data) == 0:
                print('No clients found.')
            else:
                print('Available Clients:')
                for index, client in enumerate(clients_data):
                    print(f"{index + 1}. Client ID: {client['client_id']} - Client Name: {client['name']}")

                client_selection = None
                while client_selection is None:
                    try:
                        user_input = int(input("Select a client by number (e.g., 1 for the first client): "))
                        if 1 <= user_input <= len(clients_data):
                            client_selection = clients_data[user_input - 1]
                        else:
                            print(f"Please select a number between 1 and {len(clients_data)}.")
                    except ValueError:
                        print("Please enter a valid number.")

                # Proceed with the selected client's data
                client_id = client_selection['client_id']
                print(f"You have selected Client ID: {client_id}")

                rotate_secret_query = """
                mutation rotateClientSecret($id: ID!) {
                    rotateClientSecret(id: $id) {
                        client {
                            id name client_id roles role_assignments {
                                id tenant_id role_id role_name expires_at
                            } tenant_id created_at updated_at created_by updated_by environment
                        } 
                        client_secret
                    }
                }
                """

                variables = {
                    "id": client_id
                }

                rotate_secret_response = requests.post(
                    'https://api.ctpx.secureworks.com/graphql',
                    json={'query': rotate_secret_query, 'variables': variables},
                    headers=headers
                    # This uses the headers dictionary we defined above, which includes the ACCESS_TOKEN
                )

                if rotate_secret_response.status_code == 200:
                    client_secret_data = rotate_secret_response.json()['data']['rotateClientSecret']
                    client_secret = client_secret_data['client_secret']
                    print(f'New Client Secret: {client_secret}')
                else:
                    print('Failed to rotate client secret.')
        else:
            print('Failed to retrieve clients.')

    else:
        # Processing the createClient mutation response
        client_data = response_data['data']['createClient']['client']
        client_id = client_data['client_id']
        client_secret = client_data['client_secret']

        # Printing the new client's client_id and client_secret
        print(f'Client ID: {client_id}')
        print(f'Client Secret: {client_secret}')
else:
    print('Error:')
    print(response.text)

# Invoke the function where appropriate in your code
download_threat_intel_lists_and_watchlists()
download_latest_threat_intel_publications()
