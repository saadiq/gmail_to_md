import json
from pathlib import Path
from typing import Any, Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def load_token(token_path: Path, context: str = "") -> Optional[Credentials]:
    """Load credentials from a token file.

    Args:
        token_path: Path to token JSON file
        context: Context for error messages (e.g., email address)

    Returns:
        Credentials object or None if loading failed
    """
    if not token_path.exists():
        return None

    try:
        token_data = json.loads(token_path.read_text())
        return Credentials.from_authorized_user_info(token_data)
    except (json.JSONDecodeError, ValueError) as e:
        ctx = f" for {context}" if context else ""
        print(f"Error loading token{ctx}: {e}")
        print(f"Recommendation: Delete {token_path} and reauthenticate.")
        return None


def save_token(creds: Credentials, token_path: Path) -> None:
    """Save credentials to a token file.

    Args:
        creds: Credentials to save
        token_path: Path to token JSON file
    """
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())


def refresh_or_create_credentials(
    creds: Optional[Credentials],
    credentials_file: Path,
    context: str = ""
) -> Credentials:
    """Refresh existing credentials or create new ones via OAuth flow.

    Args:
        creds: Existing credentials (may be None or expired)
        credentials_file: Path to OAuth client credentials JSON
        context: Context for messages (e.g., email address)

    Returns:
        Valid credentials
    """
    ctx = f" for {context}" if context else ""

    # Try refreshing if possible
    if creds and creds.expired and creds.refresh_token:
        try:
            if context:
                print(f"Refreshing credentials{ctx}...")
            creds.refresh(Request())
            return creds
        except Exception as e:
            print(f"Error refreshing credentials{ctx}: {e}")
            print("Will attempt to reauthenticate...")
            creds = None

    # Need fresh authentication
    if not credentials_file.exists():
        raise FileNotFoundError(
            f"credentials.json not found{ctx}. "
            "Please follow the OAuth setup instructions in the README."
        )

    if context:
        print(f"Authenticating{ctx}...")
        print(f"Using credentials from {credentials_file}")

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
    creds = flow.run_local_server(port=0)

    if context:
        print(f"Successfully authenticated{ctx}!")

    return creds


def authenticate_gmail() -> Any:
    """Authenticate with Gmail API using OAuth (legacy single-account mode).

    Returns:
        Authenticated Gmail service object
    """
    token_path = Path('token.json')
    credentials_path = Path('credentials.json')

    creds = load_token(token_path)

    if not creds or not creds.valid:
        creds = refresh_or_create_credentials(creds, credentials_path)
        save_token(creds, token_path)

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
    credentials_file = Path(account_config.get('credentials_file', ''))
    token_file = Path(account_config.get('token_file', ''))
    email = account_config.get('email', 'unknown')

    creds = load_token(token_file, email)

    if not creds or not creds.valid:
        creds = refresh_or_create_credentials(creds, credentials_file, email)
        save_token(creds, token_file)

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