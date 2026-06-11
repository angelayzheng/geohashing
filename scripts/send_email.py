"""
Geohashing Email Sender
"""

import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from geohash_calc import DISTANCE_KM, get_today_hashes

# Load email configuration
CONFIG_PATH = Path(__file__).parent.parent / "config" / "email_config.json"
with open(CONFIG_PATH) as f:
    email_config = json.load(f)


def build_email_body() -> dict[str, str]:
    """Return the email subject and body."""
    try:
        result = get_today_hashes()
    except Exception as exc:
        return {"error": f"Geohashing calculation failed: {exc}"}

    return {
        "body": (
            f"Date: {result['date']}\n"
            f"DOW date used: {result['dow_date']}\n"
            f"DJIA open: {result['djia']}\n\n"
            f"Home graticule hash: {result['graticule']['lat']}, {result['graticule']['lng']}\n"
            f"Global hash: {result['global']['lat']}, {result['global']['lng']}\n\n"
            "Closest hash (home + 8 surrounding):\n"
            f"- Coordinates: {result['closest_hash']['hash']['lat']}, {result['closest_hash']['hash']['lng']}\n"
            f"- Graticule: {result['closest_hash']['graticule']['lat']}, {result['closest_hash']['graticule']['lng']}\n"
            f"- Distance: {result['closest_hash']['distance_km']} km\n\n"
            f"Within {DISTANCE_KM} km: {result['within_distance']}\n"
        ),
        "subject": f"[{result['date']}] Geohashing: {result['distance']} km",
    }


def send_email():
    # 1. Load email configuration
    smtp_server = email_config["smtp_server"]
    smtp_port = email_config["smtp_port"]
    sender_email = email_config["sender_email"]
    sender_password = email_config["sender_password"]
    recipient_email = email_config["recipient_email"]

    # 2. Create the message envelope
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email

    # 3. Add the email body text
    email_content = build_email_body()
    msg["Subject"] = email_content.get("subject", "Geohashing Daily Update")
    msg.attach(MIMEText(email_content.get("body", ""), "plain"))

    server = None
    try:
        # 4. Connect to the server and send
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Upgrade connection to secure TLS
        server.login(sender_email, sender_password)
        server.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        if server is not None:
            server.quit()


if __name__ == "__main__":
    send_email()
