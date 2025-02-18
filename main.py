import requests
import json
from datetime import datetime, timedelta, timezone
from collections import defaultdict

def get_access_token(client_id, client_secret, tenant_id, scope="https://graph.microsoft.com/.default"):
    """
    Retrieves an access token using client credentials (SPN).
    """
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "scope": scope,
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    }
    
    response = requests.post(token_url, data=data)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Failed to obtain token: {response.text}")

def get_all_applications(access_token):
    """
    Retrieves all applications from Graph API by handling pagination.
    """
    url = "https://graph.microsoft.com/v1.0/applications"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    applications = []
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            applications.extend(data.get("value", []))
            url = data.get("@odata.nextLink")  # Move to the next page if available
        else:
            raise Exception(f"Error retrieving applications: {response.text}")
    return applications

def get_application_owner(access_token, app_object_id):
    """
    Retrieves the first owner of an application using the application's object id.
    Returns the owner's email (or displayName) if available, otherwise returns "No owner".
    """
    url = f"https://graph.microsoft.com/v1.0/applications/{app_object_id}/owners?$select=mail,displayName"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        owners = response.json().get("value", [])
        if owners:
            owner = owners[0]
            return owner.get("mail") or owner.get("displayName") or "No owner"
        else:
            return "No owner"
    else:
        print(f"Error retrieving owner for app {app_object_id}: {response.text}")
        return "No owner"

def classify_expiring_keys(applications, access_token, threshold_30=30):
    """
    For each application, checks its keyCredentials to determine if any keys are expiring within 30 days.
    Skips keys that are already expired.
    
    - For keys expiring within 30 days, the application owner is retrieved.
    - Also extracts the application's IP from identifierUris (but it will not be included in the email).
    - Calculates the exact number of days until expiration.
    """
    now = datetime.now(timezone.utc)
    threshold_date_30 = now + timedelta(days=threshold_30)

    expiring_within_30 = []  # Keys expiring within 30 days

    for app in applications:
        app_display = app.get("displayName", "No display name")
        app_appId = app.get("appId", "No appId")
        app_object_id = app.get("id")  # Used to get owners
        # Get IP from identifierUris (if available)
        identifier_uris = app.get("identifierUris", [])
        app_ip = identifier_uris[0] if identifier_uris else "No IP"
        
        key_credentials = app.get("keyCredentials", [])
        
        for key in key_credentials:
            end_date_str = key.get("endDateTime")
            if not end_date_str:
                continue  # Skip keys without an expiration date

            try:
                # Parse the end date as UTC
                end_date = datetime.strptime(end_date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except ValueError as ve:
                print(f"Error parsing date for key {key.get('keyId', 'N/A')}: {ve}")
                continue

            days_to_expire = (end_date - now).days

            # Skip expired keys
            if days_to_expire < 0:
                continue

            # Only consider keys expiring within 30 days
            if end_date <= threshold_date_30:
                owner = get_application_owner(access_token, app_object_id) if app_object_id else "No owner"
                key_info = {
                    "App": app_display,
                    "AppId": app_appId,
                    "Key": key.get("keyId", "No keyId"),
                    "Expiration": end_date_str,
                    "Days Left": days_to_expire,
                    "Owner": owner,
                    "IP": app_ip  # will not be included in the email output
                }
                expiring_within_30.append(key_info)

    return expiring_within_30

def format_key_details(key):
    """
    Formats the key details in a human-readable format with bold labels.
    """
    details = (
        f"<strong>App:</strong> {key['App']}<br>"
        f"<strong>AppId:</strong> {key['AppId']}<br>"
        f"<strong>Key:</strong> {key['Key']}<br>"
        f"<strong>Expiration:</strong> {key['Expiration']}<br>"
        f"<strong>Days Left:</strong> {key['Days Left']}<br>"
        f"<strong>Owner:</strong> {key['Owner']}<br>"
    )
    return details

def send_email_with_graph(access_token, recipient_emails, subject, body, sender_email):
    """
    Sends an email using Microsoft Graph API.
    """
    url = f"https://graph.microsoft.com/v1.0/users/{sender_email}/sendMail"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    to_recipients = [{"emailAddress": {"address": email}} for email in recipient_emails]
    email_data = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body
            },
            "toRecipients": to_recipients
        },
        "saveToSentItems": "true"
    }

    response = requests.post(url, headers=headers, json=email_data)
    if response.status_code == 202:
        print(f"Email sent to {', '.join(recipient_emails)}.")
    else:
        print("Error sending email:", response.json())

def main():
    # Configuration for SPN (Service Principal)
    tenant_id = "your_tenant_id"
    client_id = "your_client_id"
    client_secret = "your_client_secret"

    try:
        access_token = get_access_token(client_id, client_secret, tenant_id)
        print("Access token obtained.")
    except Exception as e:
        print(e)
        return

    try:
        applications = get_all_applications(access_token)
        print(f"Retrieved {len(applications)} applications from the tenant.")
    except Exception as e:
        print(e)
        return

    # Classify keys expiring within 30 days.
    expiring_within_30 = classify_expiring_keys(applications, access_token, threshold_30=30)

    # Group keys expiring exactly in 30 days by application.
    apps_with_exactly_30 = defaultdict(list)
    for key in expiring_within_30:
        if key["Days Left"] == 30: 
            apps_with_exactly_30[key["App"]].append(key)

    # For each application group, send an email with a custom template.
    for app_name, keys in apps_with_exactly_30.items():
        subject = f"Alert: Keys expiring in 30 days for application: {app_name}"
        
        # Build the email body as HTML.
        email_body = "<p>The following key(s) are scheduled to expire in exactly 30 days:</p>"
        for key in keys:
            key_details_html = format_key_details(key)
            email_body += f"<p>{key_details_html}</p><hr>"

        email_body += "<p>If you wish to extend the application's validity (i.e. generate a new secret), please submit a ticket using the link below:</p>"
        email_body += '<p><https://link_to_ticketing_system">Submit Ticket</a></p>'
        email_body += "<hr>"

        # Create a pre-filled Ticket Submission Template.
        sample = keys[0]
        ticket_template = (
            f"<h3>Ticket Submission Template</h3>"
            f"<p><strong>Summary:</strong> Request to Generate New Secret for {sample['App']}</p>"
            f"<p><strong>Description:</strong><br>"
            f"<strong>Application Name:</strong> {sample['App']}<br>"
            f"<strong>AppId:</strong> {sample['AppId']}<br>"
            f"<strong>Current Secret Expiration Date:</strong> {sample['Expiration']}<br>"
            f"<strong>Owner:</strong> {sample['Owner']}<br><br>"
            f"Please generate a new secret for the above application to extend its validity. "
            f"If additional details are required, please contact the application owner.</p>"
        )
        email_body += ticket_template

        # Prepare recipients:
        # Always include your_email@mail.com.
        # Also include the owner if available (and not "No owner").
        owner_email = sample["Owner"]
        recipient_emails = []
        if owner_email != "No owner":
            recipient_emails.append(owner_email)
        recipient_emails.append("your_email@mail.com")
        
        sender_email = "placeholder for email"  # Ensure this account is allowed to send via Graph API.
        send_email_with_graph(access_token, recipient_emails, subject, email_body, sender_email)
    else:
        if not apps_with_exactly_30:
            print("No keys expiring exactly in 30 days; no email sent.")

if __name__ == "__main__":
    main()
