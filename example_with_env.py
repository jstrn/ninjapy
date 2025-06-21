#!/usr/bin/env python3
"""
Example script showing how to use environment variables with NinjaRMM client.

This example demonstrates:
1. Loading configuration from environment variables
2. Using python-dotenv to load from .env file
3. Basic API operations

Prerequisites:
1. Copy .env.example to .env and fill in your credentials
2. Install dependencies: pip install python-dotenv
3. Run: python example_with_env.py
"""

import os
from typing import Optional

# Optional: Use python-dotenv to automatically load .env file
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()  # This loads variables from .env file if it exists
    print("✓ Loaded environment variables from .env file")
except ImportError:
    print("⚠ python-dotenv not installed. Using system environment variables.")
    print("  Install with: pip install python-dotenv")

from ninjapy import NinjaRMMClient


def get_env_var(key: str, default: Optional[str] = None, required: bool = True) -> str:
    """Get environment variable with helpful error messages."""
    value = os.getenv(key, default)
    if required and not value:
        raise ValueError(
            f"Environment variable {key} is required but not set. "
            f"Please check your .env file or set the environment variable."
        )
    # When required=True, we either return a string or raise an exception
    # When required=False, we might return None but the default should be provided
    return value or ""


def main():
    """Main example function."""
    print("🥷 NinjaRMM API Client - Environment Variables Example")
    print("=" * 50)
    
    try:
        # Load configuration from environment variables
        token_url = get_env_var("NINJA_TOKEN_URL")
        client_id = get_env_var("NINJA_CLIENT_ID")
        client_secret = get_env_var("NINJA_CLIENT_SECRET")
        scope = get_env_var("NINJA_SCOPE")
        base_url = get_env_var("NINJA_BASE_URL", "https://api.ninjarmm.com", required=False)
        
        print(f"📍 Token URL: {token_url}")
        print(f"🔑 Client ID: {client_id[:8]}..." if len(client_id) > 8 else f"🔑 Client ID: {client_id}")
        print(f"🔐 Client Secret: {'*' * len(client_secret)}")
        print(f"🎯 Scope: {scope}")
        print(f"🌐 Base URL: {base_url}")
        print()
        
        # Initialize the client
        print("🚀 Initializing NinjaRMM client...")
        with NinjaRMMClient(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            base_url=base_url
        ) as client:
            print("✓ Client initialized successfully!")
            
            # Example API calls
            print("\n📋 Fetching organizations...")
            try:
                organizations = client.get_organizations(page_size=5)
                print(f"✓ Found {len(organizations)} organizations:")
                for org in organizations:
                    print(f"  - ID: {org.get('id')}, Name: {org.get('name')}")
            except Exception as e:
                print(f"❌ Error fetching organizations: {e}")
                
            print("\n🖥️ Fetching devices...")
            try:
                devices = client.get_devices(page_size=5)
                print(f"✓ Found {len(devices)} devices:")
                for device in devices:
                    print(f"  - ID: {device.get('id')}, Name: {device.get('displayName')}")
            except Exception as e:
                print(f"❌ Error fetching devices: {e}")
                
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("\n💡 To fix this:")
        print("1. Copy .env.example to .env")
        print("2. Fill in your NinjaRMM API credentials")
        print("3. Run this script again")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        
    print("\n🎉 Example completed!")


if __name__ == "__main__":
    main() 