"""Distribution phase tools: subscriber list, Gmail sending, Drive upload."""

import base64
import io
import logging
import os
from email.mime.text import MIMEText
from typing import Dict, List, Optional

from googleapiclient.http import MediaIoBaseUpload

from .config import Config
from .google_client import get_google_service
from .server import mcp
from .utils import safe_api_call

logger = logging.getLogger(__name__)

# subscribers.txt lives in the project root, one email per line
SUBSCRIBERS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "subscribers.txt"
)


def load_subscribers() -> List[str]:
    """Read subscriber emails from subscribers.txt (one per line, # for comments)"""
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    with open(SUBSCRIBERS_FILE) as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


@mcp.tool()
def list_subscribers() -> Dict:
    """
    List all newsletter subscribers.

    Returns:
        List of subscriber email addresses
    """
    subscribers = load_subscribers()
    return {
        "status": "success",
        "count": len(subscribers),
        "subscribers": subscribers
    }


@mcp.tool()
def add_subscriber(email: str) -> Dict:
    """
    Add a subscriber email to the newsletter list.

    Args:
        email: Email address to add

    Returns:
        Updated subscriber count
    """
    email = email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        return {"status": "error", "message": f"Invalid email address: {email}"}

    subscribers = load_subscribers()
    if email in subscribers:
        return {"status": "success", "message": f"{email} is already subscribed", "count": len(subscribers)}

    with open(SUBSCRIBERS_FILE, "a") as f:
        f.write(email + "\n")

    logger.info(f"Added subscriber: {email}")
    return {"status": "success", "message": f"Added {email}", "count": len(subscribers) + 1}


@mcp.tool()
def remove_subscriber(email: str) -> Dict:
    """
    Remove a subscriber email from the newsletter list.

    Args:
        email: Email address to remove

    Returns:
        Updated subscriber count
    """
    email = email.strip().lower()
    subscribers = load_subscribers()
    if email not in subscribers:
        return {"status": "error", "message": f"{email} is not in the subscriber list"}

    subscribers.remove(email)
    with open(SUBSCRIBERS_FILE, "w") as f:
        f.write("\n".join(subscribers) + ("\n" if subscribers else ""))

    logger.info(f"Removed subscriber: {email}")
    return {"status": "success", "message": f"Removed {email}", "count": len(subscribers)}


@mcp.tool()
@safe_api_call
def send_newsletter_email(
    subject: str,
    html_content: Optional[str] = None,
    drive_file_id: Optional[str] = None,
    recipients: Optional[List[str]] = None,
    test_only: bool = False
) -> Dict:
    """
    Send the newsletter to subscribers via Gmail (as BCC to protect privacy).

    Args:
        subject: Email subject line
        html_content: Newsletter HTML (or use drive_file_id instead)
        drive_file_id: Google Drive file ID to send (e.g. from save_to_drive)
        recipients: Explicit recipient list (defaults to subscribers.txt)
        test_only: If True, send only to yourself as a preview

    Returns:
        Send confirmation with recipient count
    """
    if not html_content and not drive_file_id:
        return {"status": "error", "message": "Provide html_content or drive_file_id"}

    # Fetch HTML from Drive if a file ID was given
    if drive_file_id and not html_content:
        drive = get_google_service('drive', 'v3')
        html_content = drive.files().get_media(fileId=drive_file_id).execute().decode('utf-8')

    gmail = get_google_service('gmail', 'v1')
    sender = gmail.users().getProfile(userId='me').execute()['emailAddress']

    if test_only:
        recipients = [sender]
    elif recipients is None:
        recipients = load_subscribers()

    if not recipients:
        return {
            "status": "error",
            "message": "No recipients. Add subscribers with add_subscriber() or create subscribers.txt"
        }

    # Send in batches of 90 BCC recipients (Gmail limits recipients per message)
    sent_batches = 0
    for i in range(0, len(recipients), 90):
        batch = recipients[i:i + 90]
        message = MIMEText(html_content, 'html')
        message['To'] = sender
        message['Bcc'] = ", ".join(batch)
        message['Subject'] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        gmail.users().messages().send(userId='me', body={'raw': raw}).execute()
        sent_batches += 1

    logger.info(f"Newsletter sent to {len(recipients)} recipients in {sent_batches} batch(es)")

    return {
        "status": "success",
        "recipients_count": len(recipients),
        "batches": sent_batches,
        "from": sender,
        "subject": subject,
        "test_only": test_only
    }


@mcp.tool()
@safe_api_call
def save_to_drive(
    content: str,
    filename: str,
    folder_id: Optional[str] = None
) -> Dict:
    """
    Save generated newsletter to Google Drive.

    Args:
        content: Newsletter HTML content
        filename: Name for the file
        folder_id: Target folder ID (uses NEWSLETTER_FOLDER_ID if not provided)

    Returns:
        File ID and link to the saved newsletter
    """
    if folder_id is None:
        folder_id = Config.NEWSLETTER_FOLDER_ID

    if not folder_id:
        return {
            "status": "error",
            "message": "No folder ID provided. Set NEWSLETTER_FOLDER_ID environment variable."
        }

    service = get_google_service('drive', 'v3')

    # Create file metadata
    file_metadata = {
        'name': filename,
        'parents': [folder_id],
        'mimeType': 'text/html'
    }

    # Create file content using MediaIoBaseUpload (fixed from MediaFileUpload)
    media = MediaIoBaseUpload(
        io.BytesIO(content.encode('utf-8')),
        mimetype='text/html',
        resumable=True
    )

    # Upload file
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    logger.info(f"Saved newsletter to Drive: {filename}")

    return {
        "status": "success",
        "file_id": file['id'],
        "url": file['webViewLink'],
        "filename": filename
    }
