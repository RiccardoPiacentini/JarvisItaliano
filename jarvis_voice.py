# ============================================================
#  JARVIS VOICE - voce locale con Kokoro (gratis, senza internet)
#  Se Kokoro non e' disponibile usa la voce italiana di Windows.
#
#  Prima volta:  python jarvis_voice.py
#  (scarica i file della voce, circa 340 MB, e fa un test)
# ============================================================
VOICE = "im_nicola"       # voce maschile italiana. Alternativa femminile: "if_sara"
SPEED = 1.05              # 1.0 = normale, piu' alto = piu' veloce e vivace
PITCH = 1.12              # 1.0 = voce originale (cupa), 1.12-1.20 = piu' chiara e giovane
BRIGHT = 0.55             # 0 = nessun effetto, 0.3-0.7 = voce meno "cupa", piu' brillante
ROBOT = 0.25              # 0 = voce naturale, 0.2-0.5 = tocco metallico da robot simpatico
# ============================================================

import os
import sys
import re
import time
import subprocess
import urllib.request
import numpy as np
import sounddevice as sd

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(BASE, "kokoro-v1.0.onnx")
VOICES_FILE = os.path.join(BASE, "voices-v1.0.bin")
RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
RELEASES_PAGE = "https://github.com/thewh1teagle/kokoro-onnx/releases"

_kokoro = None


def download_files():
    for path in (MODEL_FILE, VOICES_FILE):
        if os.path.exists(path):
            continue
        name = os.path.basename(path)
        print(f"Scarico {name} ...")

        def progress(blocks, size, total):
            if total > 0:
                print(f"\r  {min(100, blocks * size * 100 // total)}%", end="", flush=True)

        urllib.request.urlretrieve(RELEASE + name, path + ".tmp", progress)
        os.replace(path + ".tmp", path)
        print()


def _load():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(MODEL_FILE, VOICES_FILE)
    return _kokoro


def preload():
    """Carica il modello in anticipo, cosi' la prima frase parte subito."""
    try:
        _load()
    except Exception:
        pass


def _speak_windows(text):
    t = text.replace("'", "''")
    ps = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "try { $s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSet,"
        "[System.Speech.Synthesis.VoiceAge]::NotSet,0,"
        "[System.Globalization.CultureInfo]'it-IT') } catch {};"
        f"$s.Speak('{t}')"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps])


def process(samples, rate):
    """Rende la voce meno cupa e piu' 'robot simpatico'."""
    x = np.asarray(samples, dtype=np.float32)
    if BRIGHT > 0:                      # schiarisce il suono (taglia i bassi, alza gli alti)
        y = x.copy()
        y[1:] = x[1:] - BRIGHT * x[:-1]
        x = y
    if ROBOT > 0:                       # eco brevissimo = effetto metallico
        d = int(rate * 0.011)
        y = x.copy()
        y[d:] += ROBOT * x[:-d]
        x = y
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak > 0:
        x = x / peak * 0.9
    return x


def _split(text):
    """Divide in frasi (non troppo corte), cosi' parte a parlare dopo la prima."""
    parts = [p for p in re.split(r"(?<=[.!?;:])\s+", text.strip()) if p]
    out, cur = [], ""
    for p in parts:
        cur = (cur + " " + p).strip() if cur else p
        if len(cur) >= 40:
            out.append(cur)
            cur = ""
    if cur:
        if out and len(cur) < 15:
            out[-1] += " " + cur
        else:
            out.append(cur)
    return out


_PIECES = []          # le ultime frasi mandate agli altoparlanti: (istante di inizio, campioni, frequenza)


def playback_rms_at(t, win=0.05):
    """Volume di cio' che usciva dagli altoparlanti all'istante t (serve a prevedere l'eco)."""
    for t0, s, rate in reversed(_PIECES):
        a = int((t - win / 2 - t0) * rate)
        b = int((t + win / 2 - t0) * rate)
        if b <= 0 or a >= len(s):
            continue
        seg = s[max(0, a):min(len(s), b)]
        if len(seg):
            return float(np.sqrt(np.mean(np.square(seg))))
    return 0.0


def _wait(should_stop):
    """Aspetta la fine dell'audio. Se should_stop() diventa vero, ferma subito e ritorna True."""
    if should_stop is None:
        sd.wait()
        return False
    try:
        st = sd.get_stream()
    except Exception:
        return False
    while st.active:
        if should_stop():
            sd.stop()
            return True
        time.sleep(0.02)
    return False


def synth(text):
    """Genera l'audio della frase senza suonarlo. Ritorna (campioni, frequenza)."""
    k = _load()
    out, eff = [], None
    for piece in _split((text or "").strip()):
        samples, rate = k.create(piece, voice=VOICE, speed=SPEED, lang="it")
        out.append(process(samples, rate))
        out.append(np.zeros(int(rate * 0.12), dtype=np.float32))
        eff = int(rate * PITCH)
    if not out:
        raise ValueError("testo vuoto")
    return np.concatenate(out), eff


def speak(text, should_stop=None):
    """Pronuncia il testo e aspetta che finisca.
    Mentre suona una frase prepara la successiva: la risposta parte subito.
    Se passi should_stop (una funzione) e diventa vera, si ferma e ritorna True."""
    text = (text or "").strip()
    if not text:
        return False
    playing = False
    try:
        k = _load()
        for piece in _split(text):
            samples, rate = k.create(piece, voice=VOICE, speed=SPEED, lang="it")
            samples = process(samples, rate)
            if playing and _wait(should_stop):    # aspetta la frase precedente
                return True
            if should_stop is not None and should_stop():
                sd.stop()
                return True
            eff = int(rate * PITCH)
            sd.play(samples, eff)                 # suonare piu' veloce = voce piu' acuta
            _PIECES.append((time.time(), samples, eff))
            del _PIECES[:-3]
            playing = True
        if playing:
            return _wait(should_stop)
        return False
    except Exception as e:
        print("Kokoro non disponibile, uso la voce di Windows. Motivo:", e)
        try:
            sd.stop()
        except Exception:
            pass
        _speak_windows(text)
        return False


if __name__ == "__main__":
    try:
        download_files()
    except Exception as e:
        print("\nDownload non riuscito:", e)
        print("Scarica a mano i file kokoro-v1.0.onnx e voices-v1.0.bin da:")
        print(RELEASES_PAGE)
        print("e mettili nella cartella", BASE)
        sys.exit(1)
    print("Test voce...")
    # Puoi provare una frase tua:  python jarvis_voice.py "Ciao, come stai?"
    frase = " ".join(sys.argv[1:]) or "Buonasera. Sono Jarvis. Tutti i sistemi sono online."
    speak(frase)
