# ============================================================
#  IMPOSTAZIONI DI JARVIS  (modello)
#  Copia questo file con il nome  impostazioni.py  e compila i valori.
#  impostazioni.py NON viene caricato su GitHub (e' nel .gitignore).
# ============================================================

# --- Chiavi ---
TELEGRAM_TOKEN = "INCOLLA_QUI_IL_TOKEN_DI_BOTFATHER"
GEMINI_API_KEY = "INCOLLA_QUI_LA_CHIAVE_DI_GOOGLE_AI_STUDIO"
TELEGRAM_CHAT_ID = 0          # il tuo ID numerico Telegram: solo tu puoi usare il bot

# --- Preferenze ---
USER_NAME = ""                # es. "Mario": Jarvis ti chiamera' per nome
CHECK_MINUTES = 30            # ogni quanti minuti controlla le nuove mail
GEMINI_MODEL = "gemini-3.5-flash-lite"
DIRE_NESSUNA_NOVITA = False   # True = a voce dice anche "nessuna novita' dalla posta"

# --- Microfono ---
MIN_PEAK = 0.06               # piu' BASSO = piu' sensibile al battito di mani
SPIKE_FACTOR = 4
LISTEN_SECONDS = 5            # secondi di ascolto dopo il doppio battito
DEVICE = None                 # None = microfono predefinito, oppure il numero da --devices

# --- Schermo ---
HUD_PORT = 8765               # cambia solo se un altro programma usa gia' questa porta

# --- Facoltativi ---
# Calendario Apple (iCloud): serve una password SPECIFICA per le app (appleid.apple.com)
# APPLE_ID = "tua@email.com"
# APPLE_APP_PASSWORD = "abcd-efgh-ijkl-mnop"
# Cartella dei documenti e delle foto (vuoto = cartella "Documenti" accanto a Jarvis)
# CARTELLA_DOCUMENTI = ""
# Modello Gemini per modificare le foto con l'AI (richiede fatturazione attiva su AI Studio)
# MODELLO_IMMAGINI = "gemini-2.5-flash-image"
