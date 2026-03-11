"""
One-time Google Drive OAuth2 setup script.

Usage:
    python scripts/dev/setup_gdrive_auth.py [--secret path/to/client_secret.json]

Steps it performs:
  1. Opens a browser for Google OAuth consent
  2. Saves credentials.json in the repo root (gitignored)
  3. Verifies auth by listing Google Docs in your Drive
"""

import argparse
import json
import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
DEFAULT_SECRET = "client_secret.json"
DEFAULT_OUTPUT = "credentials.json"


def run_auth_flow(secret_path: str, output_path: str) -> None:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        sys.exit("ERROR: google-auth-oauthlib not installed. Run: pip install google-auth-oauthlib")

    if not Path(secret_path).exists():
        print(
            f"\nERROR: '{secret_path}' not found.\n\n"
            "How to get it:\n"
            "  1. Go to https://console.cloud.google.com\n"
            "  2. Create a project (or select an existing one)\n"
            "  3. Enable the Google Drive API:\n"
            "     APIs & Services → Library → search 'Google Drive API' → Enable\n"
            "  4. Create credentials:\n"
            "     APIs & Services → Credentials → Create Credentials → OAuth client ID\n"
            "     Application type: Desktop app → Create\n"
            "  5. Download the JSON → save as client_secret.json in the repo root\n"
            "  6. Re-run this script\n"
        )
        sys.exit(1)

    print(f"Loading client secret from: {secret_path}")
    flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
    print("\nOpening browser for Google OAuth consent...")
    print("Sign in with the Google account that owns the Drive resumes.\n")
    creds = flow.run_local_server(port=0)

    with open(output_path, "w") as f:
        f.write(creds.to_json())

    print(f"\n✓ credentials.json saved to: {Path(output_path).resolve()}")


def verify_connection(credentials_path: str) -> None:
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit("ERROR: google-api-python-client not installed.")

    print("\nVerifying Google Drive connection...")
    creds = Credentials.from_authorized_user_file(credentials_path)
    service = build("drive", "v3", credentials=creds)

    results = (
        service.files()
        .list(
            q="mimeType='application/vnd.google-apps.document' and trashed=false",
            fields="files(id, name)",
            pageSize=10,
        )
        .execute()
    )
    files = results.get("files", [])

    if files:
        print(f"\n✓ Auth successful! Found {len(files)} Google Doc(s) in Drive:")
        for f in files:
            print(f"   {f['id']}  →  {f['name']}")
        print(
            "\nTo ingest a specific doc, copy its ID from the URL:\n"
            "  https://docs.google.com/document/d/<DOC_ID>/edit\n"
        )
    else:
        print(
            "\n✓ Auth successful! No Google Docs found in Drive yet.\n"
            "  Upload or create a Google Doc with a resume to test ingestion.\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up Google Drive OAuth credentials")
    parser.add_argument("--secret", default=DEFAULT_SECRET, help="Path to client_secret.json")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Where to save credentials.json")
    parser.add_argument("--verify-only", action="store_true", help="Skip auth flow, just verify existing credentials")
    args = parser.parse_args()

    if not args.verify_only:
        run_auth_flow(args.secret, args.output)

    verify_connection(args.output)


if __name__ == "__main__":
    main()
