#!/usr/bin/env python3
"""
Account Manager for Gmail to Markdown Exporter

Manages multiple Gmail account configurations and provides
interactive account selection functionality.
"""

import sys

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional


class AccountManager:
    """Manages multiple Gmail account configurations."""
    
    def __init__(self, config_file: str = 'accounts.yaml'):
        """Initialize the account manager.
        
        Args:
            config_file: Path to the accounts configuration file
        """
        self.config_file = Path(config_file)
        self.accounts = {}
        self.load_accounts()
    
    def load_accounts(self) -> None:
        """Load account configurations from YAML file."""
        if not self.config_file.exists():
            # Check for legacy single-account setup
            if Path('token.json').exists():
                self._migrate_legacy_account()
            return
        
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f) or {}
                self.accounts = config.get('accounts', {})
        except Exception as e:
            print(f"Error loading accounts configuration: {e}")
            self.accounts = {}
    
    def _migrate_legacy_account(self) -> None:
        """Migrate from legacy single-account setup to multi-account."""
        # Skip migration in non-interactive mode
        if not sys.stdin.isatty():
            return
            
        print("\nDetected existing single-account setup.")
        print("Would you like to migrate to multi-account configuration? [Y/n]: ", end='')
        
        try:
            response = input().strip().lower()
            if response and response != 'y':
                return
        except (EOFError, KeyboardInterrupt):
            return
        
        print("\nMigrating existing account...")
        print("Enter a nickname for this account (e.g., personal, work): ", end='')
        nickname = input().strip() or 'default'
        
        print("Enter the email address for this account: ", end='')
        email = input().strip()
        
        print("Enter a description (optional): ", end='')
        description = input().strip() or "Migrated account"
        
        # Create directories
        Path('credentials').mkdir(exist_ok=True)
        Path('tokens').mkdir(exist_ok=True)
        
        # Move existing files
        legacy_creds = Path('credentials.json')
        legacy_token = Path('token.json')
        
        new_creds = Path(f'credentials/{nickname}_credentials.json')
        new_token = Path(f'tokens/{nickname}_token.json')
        
        if legacy_creds.exists():
            legacy_creds.rename(new_creds)
            print(f"Moved credentials.json to {new_creds}")
        
        if legacy_token.exists():
            legacy_token.rename(new_token)
            print(f"Moved token.json to {new_token}")
        
        # Save configuration
        self.accounts[nickname] = {
            'email': email,
            'description': description,
            'credentials_file': str(new_creds),
            'token_file': str(new_token)
        }
        
        self.save_accounts()
        print(f"\nSuccessfully migrated account '{nickname}'!")
    
    def save_accounts(self) -> None:
        """Save account configurations to YAML file."""
        config = {'accounts': self.accounts}
        
        with open(self.config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    def add_account(
        self,
        nickname: str,
        email: str,
        description: str = "",
        credentials_file: Optional[str] = None,
        token_file: Optional[str] = None
    ) -> None:
        """Add a new account configuration."""
        self.accounts[nickname] = {
            'email': email,
            'description': description,
            'credentials_file': credentials_file or f'credentials/{nickname}_credentials.json',
            'token_file': token_file or f'tokens/{nickname}_token.json'
        }
        self.save_accounts()
    
    def get_account(self, nickname: str) -> Optional[Dict[str, Any]]:
        """Get account configuration by nickname."""
        return self.accounts.get(nickname)

    def list_accounts(self) -> List[str]:
        """Get list of configured account nicknames."""
        return list(self.accounts.keys())
    
    def get_account_display_info(self) -> List[Dict[str, str]]:
        """Get display information for all accounts.

        Returns:
            List of dicts with nickname, email, and description
        """
        return [
            {
                'nickname': nickname,
                'email': config.get('email', 'Unknown'),
                'description': config.get('description', '')
            }
            for nickname, config in self.accounts.items()
        ]
    
    def select_accounts_interactive(self, allow_all: bool = True) -> List[str]:
        """Interactive account selection menu."""
        if not self.accounts:
            print("\nNo accounts configured. Please run --setup-account first.")
            return []
        
        accounts = self.get_account_display_info()
        
        print("\nAvailable Gmail Accounts:")
        for i, acc in enumerate(accounts, 1):
            desc = f" - {acc['description']}" if acc['description'] else ""
            print(f"[{i}] {acc['nickname']}{desc} ({acc['email']})")
        
        if allow_all:
            print("[A] All accounts")
        print("[Q] Quit")
        
        print("\nSelect accounts (comma-separated for multiple, e.g., 1,3): ", end='')
        selection = input().strip().upper()
        
        if selection == 'Q':
            return []
        
        if selection == 'A' and allow_all:
            return self.list_accounts()
        
        # Parse comma-separated numbers
        selected = []
        try:
            indices = [int(x.strip()) for x in selection.split(',')]
            for idx in indices:
                if 1 <= idx <= len(accounts):
                    selected.append(accounts[idx - 1]['nickname'])
                else:
                    print(f"Warning: Invalid selection {idx}, skipping")
        except ValueError:
            print("Invalid selection format. Please use numbers separated by commas.")
            return []
        
        return selected
    
    def remove_account(self, nickname: str) -> bool:
        """Remove an account configuration."""
        if nickname in self.accounts:
            # Get file paths before removing
            config = self.accounts[nickname]
            creds_file = Path(config.get('credentials_file', ''))
            token_file = Path(config.get('token_file', ''))
            
            # Remove from configuration
            del self.accounts[nickname]
            self.save_accounts()
            
            # Optionally delete credential files
            print(f"\nAccount '{nickname}' removed from configuration.")
            print("Delete associated credential files? [y/N]: ", end='')
            if input().strip().lower() == 'y':
                if creds_file.exists():
                    creds_file.unlink()
                    print(f"Deleted {creds_file}")
                if token_file.exists():
                    token_file.unlink()
                    print(f"Deleted {token_file}")
            
            return True
        
        return False
    
    def validate_account(self, nickname: str) -> Dict[str, Any]:
        """Validate account configuration files exist."""
        config = self.get_account(nickname)
        if not config:
            return {'exists': False}

        creds_file = Path(config.get('credentials_file', ''))
        token_file = Path(config.get('token_file', ''))

        return {
            'exists': True,
            'has_credentials': creds_file.exists(),
            'has_token': token_file.exists(),
            'credentials_path': str(creds_file),
            'token_path': str(token_file)
        }


def setup_account_interactive(manager: AccountManager) -> Optional[str]:
    """Interactive account setup wizard.
    
    Args:
        manager: AccountManager instance
        
    Returns:
        Nickname of the created account or None if cancelled
    """
    print("\n=== Gmail Account Setup Wizard ===\n")
    
    # Get account nickname
    print("Enter account nickname (e.g., personal, work): ", end='')
    nickname = input().strip()
    if not nickname:
        print("Account nickname is required.")
        return None
    
    # Check if account already exists
    if manager.get_account(nickname):
        print(f"\nAccount '{nickname}' already exists.")
        print("Overwrite? [y/N]: ", end='')
        if input().strip().lower() != 'y':
            return None
    
    # Get email address
    print("Enter email address: ", end='')
    email = input().strip()
    if not email:
        print("Email address is required.")
        return None
    
    # Get description
    print("Enter description (optional): ", end='')
    description = input().strip()
    
    # Create directories
    Path('credentials').mkdir(exist_ok=True)
    Path('tokens').mkdir(exist_ok=True)
    
    # Set file paths
    credentials_file = f'credentials/{nickname}_credentials.json'
    token_file = f'tokens/{nickname}_token.json'
    
    # Add account to configuration
    manager.add_account(
        nickname=nickname,
        email=email,
        description=description,
        credentials_file=credentials_file,
        token_file=token_file
    )
    
    print(f"\nAccount '{nickname}' configuration saved.")
    print(f"Next step: Set up OAuth credentials for this account.")
    print(f"Run: python gmail_to_markdown.py --setup-oauth {nickname}")
    
    return nickname