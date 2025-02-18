# EntraIDSecretExpiryNotifier

EntraIDSecretExpiryNotifier is a Python-based tool that retrieves all Entra ID applications via Microsoft Graph API and checks if any application secrets (keys) are set to expire within 30 days. If a secret is expiring exactly in 30 days, the tool automatically sends a notification email to the application owner (if available) as well as to a additional email address for example (`your_team@mail.com`). The email contains detailed information about the expiring secret and a pre-filled ticket submission template for generating a new secret.

## Features

- **Retrieves All Applications:**  
  Uses Microsoft Graph API with pagination support to ensure that all applications are fetched.

- **Secret Expiry Check:**  
  Analyzes the `keyCredentials` for each application to determine if a secret is expiring within 30 days.

- **Automatic Email Notifications:**  
  Sends an HTML email for applications with secrets expiring exactly in 30 days. The email includes:
  - Bold-formatted application details (App, AppId, Key, Expiration, Days Left, Owner).
  - A pre-filled ticket submission template for generating a new secret.
  - Emails are sent to the application owner (if available) and always to `your_team@mail.com`.

## Prerequisites

- Python 3.7 or higher.
- Microsoft Graph API credentials (client_id, client_secret, tenant_id).
- The account used for sending emails must be authorized to send mail via Microsoft Graph API `Application.ReadAll` and `Mail.Send`
- Required Python libraries:
  - `requests`
  - `
  
  You can install the required libraries with:

  ```bash
  pip install requests
