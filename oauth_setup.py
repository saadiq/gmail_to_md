#!/usr/bin/env python3
"""
OAuth Setup Module for Gmail to Markdown Exporter

Provides multiple methods for setting up OAuth credentials:
- Google Cloud Console (Web UI) guidance
- gcloud CLI automated setup
- Using existing credentials.json file
"""

import json
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple


class OAuthSetup:
    """Handles OAuth credential setup for Gmail API access."""
    
    GMAIL_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
    
    @staticmethod
    def check_gcloud_installed() -> bool:
        """Check if gcloud CLI is installed and available."""
        try:
            result = subprocess.run(
                ['gcloud', '--version'], capture_output=True, text=True, check=False
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    @staticmethod
    def run_gcloud_command(command: str, capture: bool = True) -> Tuple[bool, str]:
        """Run a gcloud command and return (success, output)."""
        try:
            cmd = ['gcloud'] + shlex.split(command)
            result = subprocess.run(cmd, capture_output=capture, text=True, check=False)
            output = (result.stdout + result.stderr) if capture else ""
            return result.returncode == 0, output
        except Exception as e:
            return False, str(e)
    
    def setup_with_gcloud(self, account_name: str, email: str) -> Optional[str]:
        """Set up OAuth using gcloud CLI."""
        print("\n=== gcloud CLI OAuth Setup ===\n")
        
        if not self.check_gcloud_installed():
            print("gcloud CLI is not installed.")
            print("Install it from: https://cloud.google.com/sdk/docs/install")
            print("\nWould you like to use Web Console setup instead? [Y/n]: ", end='')
            if input().strip().lower() != 'n':
                return self.setup_with_console_guide(account_name, email)
            return None
        
        print("This will set up OAuth credentials using gcloud CLI.")
        print(f"Account: {account_name}")
        print(f"Email: {email}")
        print()
        
        # Step 1: Check authentication and switch to correct account
        print("Step 1: Checking gcloud authentication...")
        
        # Get current active account
        success, current_account = self.run_gcloud_command('config get-value account')
        current_account = current_account.strip()
        
        # Check if we need to switch accounts
        if current_account != email:
            print(f"Current gcloud account: {current_account}")
            print(f"Target email: {email}")
            
            # Check if target email is already authenticated
            success, auth_list = self.run_gcloud_command('auth list')
            
            if email in auth_list:
                print(f"Switching to account {email}...")
                success, _ = self.run_gcloud_command(f'config set account {email}')
                if success:
                    print(f"Switched to {email}")
                else:
                    print(f"Failed to switch to {email}")
                    return None
            else:
                print(f"\nAccount {email} is not authenticated with gcloud.")
                print(f"Please authenticate with the correct account:")
                print(f"\n  gcloud auth login {email}")
                print("\nPress Enter after authentication is complete...")
                input()
                
                # Switch to the newly authenticated account
                success, _ = self.run_gcloud_command(f'config set account {email}')
                if not success:
                    print(f"Failed to switch to {email}")
                    return None
        else:
            print(f"Already using correct account: {email}")
        
        # Step 2: Create or select project
        # Sanitize project ID: replace dots and underscores with hyphens, ensure valid format
        sanitized_name = account_name.replace('.', '-').replace('_', '-').lower()
        # Remove consecutive hyphens and ensure it starts with a letter
        sanitized_name = '-'.join(filter(None, sanitized_name.split('-')))
        if sanitized_name and not sanitized_name[0].isalpha():
            sanitized_name = 'g-' + sanitized_name
        project_id = f"gmail-export-{sanitized_name}"[:30]  # Max 30 chars
        print(f"\nStep 2: Setting up project...")
        print(f"  Project ID: {project_id}")
        print(f"  Display Name: Gmail Export")
        
        # Check if project exists
        success, _ = self.run_gcloud_command(f"projects describe {project_id}")
        
        if not success:
            print(f"Creating new project '{project_id}'...")
            # Use a generic display name since project is already account-specific
            success, output = self.run_gcloud_command(
                f'projects create {project_id} --name="Gmail Export"'
            )
            if not success:
                print(f"Failed to create project: {output}")
                print("\nYou may need to:")
                print("1. Enable billing for your Google Cloud account")
                print("2. Use a different project ID if it already exists")
                return None
        
        # Set as current project
        print(f"Setting '{project_id}' as current project...")
        self.run_gcloud_command(f"config set project {project_id}")
        
        # Step 3: Enable Gmail API
        print("\nStep 3: Enabling Gmail API...")
        success, output = self.run_gcloud_command(f"services enable gmail.googleapis.com")
        if not success:
            print(f"Failed to enable Gmail API: {output}")
            print("\nYou may need to enable billing for this project.")
            return None
        
        print("Gmail API enabled successfully!")
        
        # Step 4: Create OAuth client
        print("\nStep 4: Creating OAuth 2.0 credentials...")
        print("\nNote: Creating desktop OAuth clients via gcloud requires additional steps.")
        print("We'll guide you through the Google Cloud Console for this part.")
        print()
        print("Please follow these steps:")
        print(f"1. Open: https://console.cloud.google.com/apis/credentials?project={project_id}")
        print("2. Click 'Create Credentials' → 'OAuth client ID'")
        print("3. If prompted, configure the OAuth consent screen:")
        print(f"   - App name: Gmail Export {account_name.title()}")
        print(f"   - User support email: {email}")
        print(f"   - Add scope: {self.GMAIL_SCOPE}")
        print("4. For Application type, choose 'Desktop app'")
        print(f"5. Name: gmail-export-{account_name}")
        print("6. Click 'Create' and download the JSON file")
        print()
        
        return self._get_credentials_file_path(account_name)
    
    def setup_with_console_guide(self, account_name: str, email: str) -> Optional[str]:
        """Guide user through Web Console setup."""
        print("\n=== Google Cloud Console Setup Guide ===\n")
        print(f"Setting up OAuth for account: {account_name} ({email})")
        print()
        print("Follow these steps to set up OAuth credentials:\n")
        
        print("1. CREATE A GOOGLE CLOUD PROJECT")
        print("   - Go to: https://console.cloud.google.com/")
        print("   - Click 'Select a project' → 'New Project'")
        print(f"   - Name it: 'Gmail Export {account_name.title()}'")
        print("   - Click 'Create'\n")
        
        print("2. ENABLE GMAIL API")
        print("   - In the project dashboard, go to 'APIs & Services' → 'Library'")
        print("   - Search for 'Gmail API'")
        print("   - Click on it and press 'Enable'\n")
        
        print("3. CONFIGURE OAUTH CONSENT SCREEN")
        print("   - Go to 'APIs & Services' → 'OAuth consent screen'")
        print("   - Choose 'External' (unless you have Google Workspace)")
        print("   - Fill in:")
        print(f"     • App name: Gmail Export {account_name.title()}")
        print(f"     • User support email: {email}")
        print(f"     • Developer contact: {email}")
        print("   - Click 'Save and Continue'")
        print("   - On Scopes screen, click 'Add or Remove Scopes'")
        print(f"   - Search for and select: {self.GMAIL_SCOPE}")
        print("   - Click 'Update' → 'Save and Continue'")
        print(f"   - Add {email} as a test user")
        print("   - Click 'Save and Continue'\n")
        
        print("4. CREATE OAUTH CREDENTIALS")
        print("   - Go to 'APIs & Services' → 'Credentials'")
        print("   - Click 'Create Credentials' → 'OAuth client ID'")
        print("   - Application type: 'Desktop app'")
        print(f"   - Name: gmail-export-{account_name}")
        print("   - Click 'Create'")
        print("   - Click 'Download JSON'\n")
        
        return self._get_credentials_file_path(account_name)
    
    def setup_with_existing_file(self, account_name: str, source_path: str) -> Optional[str]:
        """Set up using an existing credentials.json file."""
        source = Path(source_path)
        
        if not source.exists():
            print(f"Error: File not found: {source_path}")
            return None
        
        # Validate it's a valid OAuth credentials file
        try:
            with open(source, 'r') as f:
                data = json.load(f)
                if 'installed' not in data and 'web' not in data:
                    print("Error: Invalid OAuth credentials file format.")
                    print("The file should contain 'installed' or 'web' application credentials.")
                    return None
        except json.JSONDecodeError:
            print("Error: Invalid JSON file.")
            return None
        except Exception as e:
            print(f"Error reading credentials file: {e}")
            return None
        
        # Create credentials directory if needed
        Path('credentials').mkdir(exist_ok=True)
        
        # Copy to account-specific location
        dest_path = f'credentials/{account_name}_credentials.json'
        dest = Path(dest_path)
        
        try:
            shutil.copy2(source, dest)
            print(f"Credentials copied to: {dest_path}")
            return dest_path
        except Exception as e:
            print(f"Error copying credentials file: {e}")
            return None
    
    def _get_credentials_file_path(self, account_name: str) -> Optional[str]:
        """Prompt user for downloaded credentials file path."""
        print("\nAfter downloading the credentials JSON file:")
        print("Enter the path to the downloaded file (or drag & drop): ", end='')
        
        source_path = input().strip().strip('"').strip("'")
        
        if not source_path:
            print("No file path provided.")
            return None
        
        return self.setup_with_existing_file(account_name, source_path)
    
    def interactive_setup(self, account_name: str, email: str) -> Optional[str]:
        """Interactive OAuth setup with method selection."""
        print("\n=== OAuth Setup Method Selection ===\n")
        print("Choose your preferred setup method:")
        print("[1] Google Cloud Console (Web UI)")
        print("[2] gcloud CLI")
        print("[3] I already have a credentials.json file")
        print("[Q] Cancel")
        
        print("\nSelection: ", end='')
        choice = input().strip().upper()
        
        if choice == '1':
            return self.setup_with_console_guide(account_name, email)
        elif choice == '2':
            return self.setup_with_gcloud(account_name, email)
        elif choice == '3':
            print("\nEnter path to existing credentials.json file: ", end='')
            source_path = input().strip().strip('"').strip("'")
            if source_path:
                return self.setup_with_existing_file(account_name, source_path)
        elif choice == 'Q':
            return None
        else:
            print("Invalid selection.")
            return None
    
    def validate_and_test_credentials(self, credentials_path: str) -> bool:
        """Validate OAuth credentials file structure."""
        creds_file = Path(credentials_path)

        if not creds_file.exists():
            print(f"Credentials file not found: {credentials_path}")
            return False

        try:
            data = json.loads(creds_file.read_text())
            app_data = data.get('installed') or data.get('web')

            if not app_data:
                print("Invalid credentials format: missing 'installed' or 'web' section")
                return False

            required = ['client_id', 'client_secret', 'auth_uri', 'token_uri']
            for field in required:
                if field not in app_data:
                    print(f"Invalid credentials: missing '{field}'")
                    return False

            print("Credentials file is valid")
            return True

        except json.JSONDecodeError:
            print("Invalid JSON in credentials file")
            return False
        except Exception as e:
            print(f"Error validating credentials: {e}")
            return False


def setup_oauth_for_account(account_name: str, email: str) -> bool:
    """Complete OAuth setup process for an account."""
    setup = OAuthSetup()

    # Check if credentials already exist
    creds_path = Path(f'credentials/{account_name}_credentials.json')
    if creds_path.exists():
        print(f"\nCredentials already exist for account '{account_name}'")
        print("Overwrite? [y/N]: ", end='')
        if input().strip().lower() != 'y':
            return False

    result = setup.interactive_setup(account_name, email)

    if result:
        print(f"\nOAuth credentials configured for account '{account_name}'")
        print(f"  Credentials saved to: {result}")
        print("\nNext step: Authenticate the account")
        print(f"Run: python gmail_to_markdown.py --account {account_name} --test")
        return True

    print("\nOAuth setup cancelled or failed.")
    return False