import os
import json
from pathlib import Path
from typing import Any, Optional, Dict
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    """Authenticate with Gmail API using OAuth (legacy single-account mode)."""
    creds = None
    local_token = 'token.json'
    
    # Try to use existing token if available
    if os.path.exists(local_token):
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
            # Check for credentials.json in local directory
            local_creds = 'credentials.json'
            
            if os.path.exists(local_creds):
                creds_file = local_creds
                print(f"Using credentials from {local_creds}")
            else:
                raise FileNotFoundError(
                    "credentials.json not found. "
                    "Please follow the OAuth setup instructions in the README."
                )
            
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save token locally
        with open(local_token, 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)


def authenticate_gmail_account(account_config: Dict[str, Any]) -> Any:
    """Authenticate with Gmail API for a specific account.
    
    Args:
        account_config: Account configuration dict with:
            - credentials_file: Path to OAuth credentials JSON
            - token_file: Path to store/read authentication token
            - email: Email address (for display)
    
    Returns:
        Authenticated Gmail service object
    """
    creds = None
    
    credentials_file = Path(account_config.get('credentials_file', ''))
    token_file = Path(account_config.get('token_file', ''))
    email = account_config.get('email', 'unknown')
    
    # Ensure directories exist
    token_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Try to load existing token
    if token_file.exists():
        try:
            with open(token_file, 'r') as f:
                token_data = json.load(f)
            creds = Credentials.from_authorized_user_info(token_data)
        except Exception as e:
            print(f"Error loading token for {email}: {str(e)}")
            print(f"Recommendation: Delete {token_file} and reauthenticate.")
            creds = None
    
    # Refresh or create new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print(f"Refreshing credentials for {email}...")
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing credentials for {email}: {str(e)}")
                print(f"Will attempt to reauthenticate...")
                creds = None
        
        if not creds:
            # Check for credentials file
            if not credentials_file.exists():
                raise FileNotFoundError(
                    f"Credentials file not found for account '{email}': {credentials_file}\n"
                    f"Please run: python gmail_to_markdown.py --setup-oauth {account_config.get('nickname', 'account')}"
                )
            
            print(f"Authenticating {email}...")
            print(f"Using credentials from {credentials_file}")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_file), SCOPES
            )
            creds = flow.run_local_server(port=0)
            
            print(f"Successfully authenticated {email}!")
        
        # Save token for future use
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)


def authenticate_multiple_accounts(account_configs: list) -> Dict[str, Any]:
    """Authenticate multiple Gmail accounts.
    
    Args:
        account_configs: List of account configuration dicts
    
    Returns:
        Dict mapping account nicknames to authenticated service objects
    """
    services = {}
    
    for config in account_configs:
        nickname = config.get('nickname', 'unknown')
        email = config.get('email', 'unknown')
        
        try:
            print(f"\nAuthenticating account '{nickname}' ({email})...")
            service = authenticate_gmail_account(config)
            services[nickname] = service
            print(f"✓ Successfully authenticated '{nickname}'")
        except Exception as e:
            print(f"✗ Failed to authenticate '{nickname}': {str(e)}")
            # Continue with other accounts
    
    return services