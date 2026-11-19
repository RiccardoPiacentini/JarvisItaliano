# ============================================================
#  Da eseguire UNA VOLTA: da' a Jarvis il permesso di INVIARE risposte
#  (sempre e solo dopo la tua conferma). Si apre il browser: accedi con
#  il tuo account Google e accetta anche il nuovo permesso "invia email".
# ============================================================
import os
from google_auth_oauthlib.flow import InstalledAppFlow

BASE = os.path.dirname(os.path.abspath(__file__))
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
          "https://www.googleapis.com/auth/gmail.send"]

flow = InstalledAppFlow.from_client_secrets_file(os.path.join(BASE, "credentials.json"), SCOPES)
creds = flow.run_local_server(port=0)
with open(os.path.join(BASE, "token.json"), "w") as f:
    f.write(creds.to_json())
print("\nFatto! Ora Jarvis puo' inviare le risposte che confermi.")
print("Riavvia Jarvis: ferma_jarvis.bat e poi avvia_jarvis.vbs")
