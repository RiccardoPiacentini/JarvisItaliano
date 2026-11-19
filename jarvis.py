# ============================================================
#  JARVIS - Gmail -> Telegram (con domande e risposte)
#  Le chiavi e le preferenze sono nel file impostazioni.py
# ============================================================
import os
import sys
import json
import time
import datetime
import requests
from google import genai
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import impostazioni as cfg
import jarvis_mail as mail

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
SCOPES_READ = ["https://www.googleapis.com/auth/gmail.readonly"]
SCOPES = SCOPES_READ + ["https://www.googleapis.com/auth/gmail.send"]   # leggere + inviare risposte (solo su tua conferma)
TG = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"

client = genai.Client(api_key=cfg.GEMINI_API_KEY)

# Se parte con "python jarvis.py" gli altri moduli devono trovare QUESTO stesso modulo (e un solo client Gemini).
sys.modules.setdefault("jarvis", sys.modules[__name__])
import jarvis_telegram as tg    # noqa: E402  (il bot Telegram vero e proprio)


# ---------------------------- GMAIL ----------------------------
def gmail_service():
    token_path = os.path.join(BASE, "token.json")
    creds = None
    if os.path.exists(token_path):
        # usa i permessi che il tuo token ha DAVVERO (il vecchio token ha solo la lettura:
        # continua a funzionare finche' non esegui autorizza_gmail.bat)
        try:
            with open(token_path, encoding="utf-8") as f:
                granted = json.load(f).get("scopes") or SCOPES_READ
        except Exception:
            granted = SCOPES_READ
        creds = Credentials.from_authorized_user_file(token_path, granted)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.path.join(BASE, "credentials.json"), SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def fetch_emails(query, max_results=30):
    svc = gmail_service()
    res = svc.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    emails = []
    for m in res.get("messages", []):
        msg = svc.users().messages().get(
            userId="me", id=m["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        h = {x["name"]: x["value"] for x in msg["payload"]["headers"]}
        emails.append({
            "id": m["id"],
            "from": h.get("From", ""),
            "subject": h.get("Subject", "(senza oggetto)"),
            "date": h.get("Date", ""),
            "snippet": msg.get("snippet", ""),
        })
    return emails


def emails_to_text(emails):
    lines = []
    for i, e in enumerate(emails, 1):
        lines.append(
            f"{i}. Da: {e['from']} | Oggetto: {e['subject']} | "
            f"Data: {e['date']} | Anteprima: {e['snippet']}"
        )
    return "\n".join(lines)


# ---------------------------- GEMINI ----------------------------
def ask_gemini(prompt, json_mode=False):
    for _ in range(3):
        try:
            if json_mode:
                r = client.models.generate_content(
                    model=cfg.GEMINI_MODEL, contents=prompt,
                    config={"response_mime_type": "application/json"},
                )
            else:
                r = client.models.generate_content(model=cfg.GEMINI_MODEL, contents=prompt)
            return (r.text or "").strip()
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                time.sleep(20)   # limite gratuito: aspetta e riprova
                continue
            return f"Errore con Gemini: {err[:300]}"
    return "Gemini e' occupato (limite gratuito). Riprova tra un minuto."


# ---------------------------- TELEGRAM ----------------------------
def send(text):
    text = text or "(vuoto)"
    for i in range(0, len(text), 4000):
        requests.post(
            f"{TG}/sendMessage",
            json={"chat_id": cfg.TELEGRAM_CHAT_ID, "text": text[i:i + 4000]},
            timeout=30,
        )


def format_mails(mails):
    blocchi = []
    for i, m in enumerate(mails, 1):
        blocchi.append(
            f"{i}. {mail.short_sender(m['from'])} - {m['subject']}\n   {m.get('why', '')}"
        )
    return "\n\n".join(blocchi)


# ---------------------------- LOGICA ----------------------------
def auto_check():
    """Avvisa su Telegram solo le mail importanti che nessuno ha ancora comunicato."""
    nuove, _ = mail.check_and_claim("telegram")
    if nuove:
        tg.notify_new_mails(nuove)


def main():
    print("Jarvis avviato. (CTRL+C per fermare)")
    mail.init(gmail_service, ask_gemini)
    gmail_service()   # al primo avvio apre il browser per il login Google
    tg.loop(auto_check, cfg.CHECK_MINUTES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nFermato.")
