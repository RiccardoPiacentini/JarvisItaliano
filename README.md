# Jarvis

Assistente personale per **Windows**, in italiano: lo svegli con un **doppio battito di mani** e dici
«Jarvis sveglia». Parla con voce locale, mostra un'interfaccia a schermo intero in stile HUD e si controlla
anche da **Telegram**.

## Cosa sa fare

- **Conversazione a voce** con memoria, che continua finché dici «basta così»; puoi interromperlo mentre parla.
- **Posta Gmail**: riassunto delle mail importanti e notifiche; risponde alle mail **solo dopo la tua conferma**.
- **Calendario Apple**: legge, aggiunge e toglie eventi (sempre dopo conferma).
- **Internet**: ricerche web, notizie, meteo, lettura di pagine.
- **Documenti**: crea, legge e archivia file nella cartella `Documenti`.
- **Schermo a finestre**: apre foto e documenti, li sposta (sinistra, destra, angoli), zooma, li affianca,
  li chiude, e può *guardare* cosa c'è aperto e descriverlo. Ritocca le foto (ritaglio, rotazione, filtri…)
  creando sempre una copia: l'originale non si tocca. La modifica con l'AI richiede un piano Google con fatturazione.
- **Telegram**: stesse funzioni di quelle sul PC, con messaggi, vocali, pulsanti, elenco e download dei
  documenti, invio di foto, e controllo dello schermo del PC.

## Installazione

1. Installa **Python 3.10+** (Windows) e scarica questa cartella.
2. Dentro la cartella: `pip install -r requirements.txt`
3. Copia `impostazioni.example.py` in `impostazioni.py` e inserisci:
   - il token del bot Telegram (da @BotFather) e il tuo `TELEGRAM_CHAT_ID`;
   - la chiave Gemini (gratuita su Google AI Studio).
4. **Gmail**: crea in Google Cloud un client OAuth "Desktop", salva il file come `credentials.json` nella
   cartella e fai doppio clic su `autorizza_gmail.bat` (concedi lettura e invio).
5. **Voce**: al primo avvio scarica i file del modello Kokoro (`kokoro-v1.0.onnx`, `voices-v1.0.bin`);
   se non riesce, scaricali dalle release di [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx/releases)
   e mettili nella cartella.
6. **Calendario Apple** (facoltativo): imposta `APPLE_ID` e `APPLE_APP_PASSWORD` in `impostazioni.py`.

## Uso

- Doppio clic su `avvia_jarvis.vbs` (parte in background). Per fermarlo: `ferma_jarvis.bat`.
- Partenza automatica all'accensione: `installa_avvio_automatico.bat` (si toglie con `rimuovi_avvio_automatico.bat`).
- Errori e messaggi: `jarvis.log` (Telegram) e `wake.log` (ascolto e schermo).

## Struttura

| File | Ruolo |
|---|---|
| `jarvis.py` | Programma Telegram |
| `jarvis_wake.py` | Battito di mani, ascolto vocale e server dello schermo |
| `jarvis_chat.py` | Conversazione a voce |
| `jarvis_telegram.py` | Bot Telegram |
| `jarvis_tools.py` | Strumenti: web, meteo, calendario, documenti |
| `jarvis_actions.py` | Azioni con conferma (rispondi mail, eventi) |
| `jarvis_desk.py`, `jarvis_images.py` | Finestre sullo schermo e foto |
| `jarvis_mail.py`, `jarvis_voice.py` | Gmail e sintesi vocale |
| `hud.html` | Interfaccia HUD |

## Sicurezza

- `impostazioni.py`, `token.json`, `credentials.json` e i dati personali sono nel `.gitignore`: **non caricarli**.
  Se per sbaglio pubblichi una chiave, revocala subito e creane una nuova.
- Il bot risponde solo al `TELEGRAM_CHAT_ID` configurato.
- Mail e calendario vengono modificati solo dopo una conferma esplicita.
- Il server dello schermo ascolta solo su `127.0.0.1`.
