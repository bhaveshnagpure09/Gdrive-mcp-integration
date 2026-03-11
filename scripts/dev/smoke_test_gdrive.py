"""
Smoke test: fetch a single Google Doc and print the first 500 chars.

Usage:
    python scripts/dev/smoke_test_gdrive.py <DOC_ID>

The DOC_ID is the long string from the document URL:
    https://docs.google.com/document/d/<DOC_ID>/edit
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from app.core.mcp_client import GoogleDriveMCPClient, GDriveError


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python smoke_test_gdrive.py <DOC_ID>")
        print("\nTo list all docs in Drive without specifying an ID:")
        print("  python smoke_test_gdrive.py --list")
        sys.exit(1)

    credentials_path = os.environ.get("GDRIVE_CREDENTIALS_PATH", "credentials.json")
    client = GoogleDriveMCPClient(credentials_path)

    try:
        client.authenticate()
        print(f"✓ Authenticated using: {credentials_path}\n")
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
        print("\nRun scripts/dev/setup_gdrive_auth.py first to generate credentials.json")
        sys.exit(1)

    if sys.argv[1] == "--list":
        docs = client.list_resumes()
        if not docs:
            print("No Google Docs found in Drive.")
        else:
            print(f"Found {len(docs)} Google Doc(s):")
            for d in docs:
                print(f"  {d['id']}  →  {d['name']}")
        return

    doc_id = sys.argv[1]
    print(f"Fetching doc: {doc_id}")
    try:
        text = client.fetch_resume(doc_id)
        print(f"✓ Fetched {len(text)} characters\n")
        print("--- First 500 chars ---")
        print(text[:500])
        print("-----------------------")
    except GDriveError as e:
        print(f"✗ Failed to fetch document: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
