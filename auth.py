import os
import json
from typing import Any
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    """Authenticate with Gmail API using OAuth."""
    creds = None
    
    # Check for existing token in newsletter_summary directory first
    newsletter_token = '../newsletter_summary/token.json'
    local_token = 'token.json'
    
    # Try to use existing token from newsletter_summary if available
    if os.path.exists(newsletter_token):
        try:
            with open(newsletter_token, 'r') as f:
                token_data = json.load(f)
            creds = Credentials.from_authorized_user_info(token_data)
        except Exception as e:
            print(f"Error loading credentials from newsletter_summary token: {str(e)}")
    elif os.path.exists(local_token):
        try:
            with open(local_token, 'r') as f:
                token_data = json.load(f)
            creds = Credentials.from_authorized_user_info(token_data)
        except Exception as e:
            print(f"Error loading credentials from local token: {str(e)}")
            print("Recommendation: Delete token.json and reauthenticate.")
            raise Exception("Invalid JSON")
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing credentials: {str(e)}")
                print("Recommendation: Delete token.json and reauthenticate.")
                raise
        else:
            # Check for credentials.json in newsletter_summary or local
            newsletter_creds = '../newsletter_summary/credentials.json'
            local_creds = 'credentials.json'
            
            creds_file = None
            if os.path.exists(newsletter_creds):
                creds_file = newsletter_creds
                print(f"Using credentials from {newsletter_creds}")
            elif os.path.exists(local_creds):
                creds_file = local_creds
                print(f"Using credentials from {local_creds}")
            else:
                raise FileNotFoundError(
                    "credentials.json not found. Please copy it from ../newsletter_summary/ "
                    "or follow the OAuth setup instructions."
                )
            
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save token locally
        with open(local_token, 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)