# ============================================================
#  JARVIS WAKE - doppio battito di mani + "Jarvis sveglia"
#  -> apre lo schermo animato, ti saluta e ti dice le mail importanti
#  Le preferenze sono nel file impostazioni.py
# ============================================================
import os
import sys
import json
import time
import subprocess
import webbrowser
import winsound
import datetime
import secrets
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import numpy as np
import sounddevice as sd
import speech_recognition as sr

import impostazioni as cfg
import jarvis_voice as voice
import jarvis_mail as mail
import jarvis_chat as chat
import jarvis_tools as tools
import jarvis_desk as desk
import jarvis_images as images
import jarvis            # riusa il collegamento a Gmail e a Gemini

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
HUD_FILE = os.path.join(BASE, "hud.html")
RATE = 16000
BLOCK = 800                # blocchi da 50 millisecondi

WAKE_NAMES = ["jarvis", "jarvi", "giarvis", "garvis", "gervais", "jervis", "giarvi"]
STATE = {"checking": False, "server": False, "last_poll": 0.0}
# Chiave segreta: solo lo schermo di Jarvis (che la riceve insieme alla pagina) puo' dare
# comandi; una pagina web qualsiasi aperta nel browser no.
TOKEN = secrets.token_urlsafe(9)


# ---------------------------- SERVER PER LO SCHERMO ----------------------------
def public_mail(m):
    return {
        "id": m["id"],
        "from": mail.short_sender(m["from"]),
        "subject": m["subject"],
        "date": m.get("date", ""),
        "why": m.get("why", ""),
        "announced": m.get("announced", ""),
        "read": bool(m.get("read")),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, ctype, data):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, "application/json; charset=utf-8", data)

    def do_GET(self):
        # accetta solo richieste dirette al tuo PC (protezione extra)
        host = self.headers.get("Host", "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            self._send(403, "text/plain", b"no")
            return
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path in ("/", "/hud.html"):
                with open(HUD_FILE, "rb") as f:
                    page = f.read().replace(b"__TOKEN__", TOKEN.encode())
                self._send(200, "text/html; charset=utf-8", page)
            elif u.path == "/api/mails":
                self._json({
                    "name": cfg.USER_NAME,
                    "checking": STATE["checking"],
                    "mails": [public_mail(m) for m in mail.get_important()],
                })
            elif u.path == "/api/chat":
                STATE["last_poll"] = time.time()          # lo schermo e' aperto e ascolta
                d = chat.snapshot()
                d["panel"] = tools.panel_snapshot()
                d["desk"] = desk.snapshot()
                self._json(d)
            elif u.path == "/api/img":
                if q.get("t", [""])[0] != TOKEN:
                    self._json({"error": "non autorizzato"}, 403)
                    return
                path = images.safe_path(q.get("f", [""])[0])
                if not path or not images.is_image(path):
                    self._send(404, "text/plain", b"?")
                    return
                with open(path, "rb") as f:
                    self._send(200, images.MIME.get(os.path.splitext(path)[1].lower(), "image/jpeg"), f.read())
            elif u.path == "/api/desk":                   # l'utente chiude una finestra con la X
                if q.get("t", [""])[0] != TOKEN:
                    self._json({"error": "non autorizzato"}, 403)
                    return
                if q.get("cmd", [""])[0] == "close":
                    desk.close_window(q.get("id", [""])[0])
                self._json({"ok": True})
            elif u.path == "/api/remote":                 # comandi dallo schermo di Telegram
                if q.get("t", [""])[0] != TOKEN:
                    self._json({"error": "non autorizzato"}, 403)
                    return
                try:
                    args = json.loads(q.get("args", ["{}"])[0])
                except Exception:
                    args = {}
                self._json({"result": desk.run_remote(q.get("fn", [""])[0], args)})
            elif u.path in ("/api/action", "/api/open"):
                if q.get("t", [""])[0] != TOKEN:
                    self._json({"error": "non autorizzato"}, 403)
                    return
                if u.path == "/api/action":          # pulsanti dello schermo
                    threading.Thread(target=tools.run_action, args=(q.get("name", [""])[0],),
                                     daemon=True).start()
                    self._json({"ok": True})
                else:                                # apri un documento o la cartella
                    if q.get("folder"):
                        ok = tools.open_docs_folder()
                    elif images.is_image(q.get("file", [""])[0]):
                        desk._open_file(q["file"][0], "center")         # le foto si aprono sullo schermo
                        ok = True
                    else:
                        ok = tools.open_document_file(q.get("file", [""])[0])
                    self._json({"ok": bool(ok)})
            elif u.path == "/api/mail":
                mid = q.get("id", [""])[0]
                m = next((x for x in mail.get_important() if x["id"] == mid), None)
                if not m:
                    self._json({"error": "mail non trovata"}, 404)
                    return
                body = mail.get_body(mid)
                mail.mark_read(mid)
                self._json({
                    "id": mid, "from": m["from"], "subject": m["subject"],
                    "date": m.get("date", ""), "why": m.get("why", ""), "body": body,
                })
            else:
                self._send(404, "text/plain", b"?")
        except Exception as e:
            try:
                self._json({"error": str(e)[:200]}, 500)
            except Exception:
                pass


def ensure_hud():
    """Se lo schermo e' chiuso (es. comando da Telegram) lo apre e aspetta che sia pronto."""
    if time.time() - STATE["last_poll"] < 4:
        return
    t0 = time.time()
    open_hud()
    while time.time() - t0 < 25 and STATE["last_poll"] < t0 + 3:
        time.sleep(0.4)
    time.sleep(0.8)


def start_server():
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", cfg.HUD_PORT), Handler)
    except OSError as e:
        print("Impossibile avviare il server dello schermo (porta occupata?):", e)
        return False
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    STATE["server"] = True
    desk.set_hud_opener(ensure_hud)
    try:                                         # Telegram legge qui la chiave per comandare lo schermo
        with open(os.path.join(BASE, "hud_token.json"), "w", encoding="utf-8") as f:
            json.dump({"token": TOKEN, "port": cfg.HUD_PORT}, f)
    except Exception as e:
        print("hud_token.json non scritto:", e)
    return True


# ---------------------------- SCHERMO E VOCE ----------------------------
def open_hud():
    if STATE["server"]:
        url = f"http://127.0.0.1:{cfg.HUD_PORT}/"
    else:
        url = "file:///" + os.path.join(BASE, "hud.html").replace("\\", "/")
    # Profilo separato: Edge si apre SEMPRE come finestra nuova a schermo intero,
    # anche se Edge e' gia' aperto con altre finestre.
    profile = os.path.join(BASE, "edge_profile")
    try:
        subprocess.Popen(
            f'start msedge --user-data-dir="{profile}" --no-first-run '
            f'--app="{url}" --start-fullscreen', shell=True)
    except Exception:
        webbrowser.open(url)


def is_wake_phrase(text):
    text = text.lower()
    return any(n in text for n in WAKE_NAMES) and "svegli" in text


def greeting_text():
    h = datetime.datetime.now().hour
    sal = ("Buonanotte" if h < 5 else "Buongiorno" if h < 12
           else "Buon pomeriggio" if h < 18 else "Buonasera")
    nome = f", {cfg.USER_NAME}" if cfg.USER_NAME else ""
    return f"{sal}{nome}. Tutti i sistemi sono online."


def mail_announcement(claimed):
    n = len(claimed)
    if n == 0:
        return "Nessuna novità dalla posta." if cfg.DIRE_NESSUNA_NOVITA else ""
    nomi = [mail.short_sender(m["from"]) for m in claimed[:3]]
    if n == 1:
        return f"Hai una nuova mail importante, da {nomi[0]}. La trovi sullo schermo."
    if n <= 3:
        elenco = ", ".join(nomi[:-1]) + " e " + nomi[-1]
        return f"Hai {n} nuove mail importanti, da {elenco}. Le trovi sullo schermo."
    return f"Hai {n} nuove mail importanti. Le trovi sullo schermo."


def on_wake(stream):
    """Apre lo schermo, saluta, dice SOLO le mail che nessuno ha ancora comunicato,
    poi resta in ascolto per una conversazione a voce."""
    result = {"claimed": []}

    def work():
        STATE["checking"] = True
        try:
            claimed, _ = mail.check_and_claim("voice")
            result["claimed"] = claimed
        except Exception as e:
            print("Errore controllo posta:", e)
        finally:
            STATE["checking"] = False

    tools.panel_close()             # schermo pulito a ogni risveglio
    desk.close_all()
    t = threading.Thread(target=work, daemon=True)
    t.start()                       # intanto controlla la posta...
    open_hud()
    chat.set_state("speaking")
    voice.speak(greeting_text())    # ...mentre ti saluta
    t.join(timeout=60)
    frase = mail_announcement(result["claimed"])
    if frase:
        voice.speak(frase)
    try:
        chat.run(stream, opening="Come posso aiutarti?")
    except Exception as e:
        print("Errore nella conversazione:", e)
    finally:
        chat.set_state("idle")


def list_devices():
    print("MICROFONI DISPONIBILI (quelli con ingressi > 0):\n")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"  numero {i}: {d['name']}")
    print("\nPer usarne uno, scrivi il numero in DEVICE = ... dentro impostazioni.py")


# ---------------------------- ASCOLTO ----------------------------
def main():
    if "--devices" in sys.argv:
        list_devices()
        return

    test_mode = "--test" in sys.argv
    recognizer = sr.Recognizer()

    try:
        info = sd.query_devices(cfg.DEVICE, kind="input")
        print("Microfono in uso:", info["name"])
    except Exception as e:
        print("Non trovo nessun microfono:", e)
        return

    if "--test-interruzione" in sys.argv:
        with sd.InputStream(samplerate=RATE, channels=1, blocksize=BLOCK,
                            dtype="float32", device=cfg.DEVICE) as stream:
            chat.test_interruption(stream)
        return

    if test_mode:
        print("\nMODALITA' TEST: batti le mani e guarda i numeri.")
        print("(CTRL+C per uscire)\n")
    else:
        mail.init(jarvis.gmail_service, jarvis.ask_gemini)
        if start_server():
            print("Schermo pronto su http://127.0.0.1:%d/" % cfg.HUD_PORT)
        print("\nJarvis Wake attivo. Batti DUE volte le mani, aspetta il 'bip',")
        print("poi di' 'Jarvis sveglia'. (CTRL+C per fermare)\n")
        threading.Thread(target=voice.preload, daemon=True).start()

    last_clap = 0.0
    prev_loud = False
    blocked_until = 0.0
    background = 0.01

    with sd.InputStream(samplerate=RATE, channels=1, blocksize=BLOCK,
                        dtype="float32", device=cfg.DEVICE) as stream:
        while True:
            data, _ = stream.read(BLOCK)
            peak = float(np.max(np.abs(data)))
            now = time.time()

            limit = max(cfg.MIN_PEAK, background * cfg.SPIKE_FACTOR)
            loud = peak > limit
            if not loud:
                background = 0.95 * background + 0.05 * peak

            if test_mode:
                mark = "  <== BATTITO RILEVATO" if (loud and not prev_loud) else ""
                print(f"volume {peak:0.2f} (soglia {limit:0.2f}) " + "#" * int(peak * 60) + mark)
                prev_loud = loud
                continue

            if loud and not prev_loud and now > blocked_until:
                gap = now - last_clap
                if 0.15 < gap < 0.9:
                    last_clap = 0.0
                    winsound.Beep(1000, 150)            # bip: "ti ascolto"
                    print("Doppio battito! Ascolto...")
                    frames = []
                    for _ in range(int(cfg.LISTEN_SECONDS * RATE / BLOCK)):
                        d, _ = stream.read(BLOCK)
                        frames.append(d)
                    audio = np.concatenate(frames)[:, 0]
                    pcm = (np.clip(audio * 4, -1, 1) * 32767).astype(np.int16)
                    try:
                        text = recognizer.recognize_google(
                            sr.AudioData(pcm.tobytes(), RATE, 2), language="it-IT"
                        )
                        print("Ho sentito:", text)
                        if is_wake_phrase(text):
                            winsound.Beep(1400, 200)
                            print(">>> Attivazione!")
                            on_wake(stream)
                            # dopo la conversazione ignora i rumori per qualche secondo
                            blocked_until = time.time() + (
                                5 if getattr(cfg, "CHAT_ATTIVA", True) else 20)
                        else:
                            blocked_until = time.time() + 2
                    except sr.UnknownValueError:
                        print("Non ho capito nulla, riprova.")
                        blocked_until = time.time() + 2
                    except sr.RequestError as e:
                        print("Errore di connessione al riconoscimento vocale:", e)
                        blocked_until = time.time() + 5
                    prev_loud = False
                    background = 0.01
                    continue
                last_clap = now
            prev_loud = loud


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nFermato.")
