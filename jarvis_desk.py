# ============================================================
#  JARVIS DESK - lo schermo di Jarvis come "scrivania" di finestre
#  Jarvis apre foto e documenti, li sposta a destra o a sinistra,
#  zooma, li affianca, li modifica e te li mostra a confronto:
#  tutto a voce (e anche da Telegram, vedi il ponte in fondo).
#  Vive nel programma dello schermo (jarvis_wake.py).
# ============================================================
import os
import re
import time
import threading

import jarvis_tools as tools
import jarvis_images as images

_lock = threading.RLock()
S = {"rev": 0, "windows": [], "n": 0}
HOOKS = {"ensure_hud": None}
POSITIONS = ("left", "right", "center", "full", "bl", "br", "tl", "tr")


def set_hud_opener(fn):
    """jarvis_wake registra qui la funzione che apre lo schermo se e' chiuso."""
    HOOKS["ensure_hud"] = fn


def _ensure_hud():
    fn = HOOKS["ensure_hud"]
    if fn:
        try:
            fn()
        except Exception as e:
            print("[scrivania] non riesco ad aprire lo schermo:", e)


def _pos(p, default="center"):
    s = (p or "").lower().strip()
    if not s:
        return default
    vert = "b" if any(x in s for x in ("bass", "giu", "giù", "sotto", "bottom")) else \
           "t" if any(x in s for x in ("alto", "sopra", "top")) else ""
    if (vert or "angol" in s) and ("sinistr" in s or "destr" in s):
        return (vert or "b") + ("l" if "sinistr" in s else "r")
    if "sinistr" in s or s in ("left", "sx"):
        return "left"
    if "destr" in s or s in ("right", "dx"):
        return "right"
    if "interno" in s or "intero" in s or "tutto" in s or "full" in s or "grande" in s or "massim" in s:
        return "full"
    if "centr" in s or "mezzo" in s or s == "center":
        return "center"
    return default


_POS_IT = {"left": "a sinistra", "right": "a destra", "center": "al centro", "full": "a schermo intero",
           "bl": "in basso a sinistra (piccola)", "br": "in basso a destra (piccola)",
           "tl": "in alto a sinistra (piccola)", "tr": "in alto a destra (piccola)"}


# ---------------------------- STATO ----------------------------
def snapshot():
    with _lock:
        return {"rev": S["rev"], "windows": [dict(w) for w in S["windows"]]}


def _bump():
    S["rev"] += 1


def has_windows():
    with _lock:
        return bool(S["windows"])


def close_all():
    with _lock:
        if S["windows"]:
            S["windows"] = []
            _bump()


def close_window(wid):
    with _lock:
        n = len(S["windows"])
        S["windows"] = [w for w in S["windows"] if w["id"] != wid]
        if len(S["windows"]) != n:
            _bump()


def _fdate(ts):
    return time.strftime("%d/%m %H:%M", time.localtime(ts))


def describe():
    """Il quadro per Gemini: cosa c'e' sullo schermo (e cosa mostra), e quali foto ci sono nella cartella."""
    with _lock:
        ws = [dict(w) for w in S["windows"]]
    lines = []
    if ws:
        lines.append("FINESTRE APERTE SULLO SCHERMO (in ordine di apertura, l'ultima e' in primo piano):")
        for i, w in enumerate(ws, 1):
            kind = "foto" if w["type"] == "image" else "documento"
            tag = f", {w['tag']}" if w.get("tag") else ""
            orig = images.original_of(w.get("file", ""))
            rel = f", e' la versione modificata di '{orig}'" if orig and w["type"] == "image" else ""
            what = f" - mostra: {w['desc']}" if w.get("desc") else ""
            lines.append(f"  {i}) '{w['title']}' ({kind}{tag}{rel}) {_POS_IT[w['pos']]}, zoom {w['zoom']:.1f}x{what}")
    else:
        lines.append("Sullo schermo non c'e' nessuna finestra aperta.")
    try:
        imgs = images.list_images()[:8]
    except Exception:
        imgs = []
    if imgs:
        lines.append("FOTO NELLA CARTELLA DOCUMENTI (dalla piu' recente alla piu' vecchia): "
                     + "; ".join(f"{n} ({_fdate(t)})" for _p, n, t in imgs))
    return "\n".join(lines) + "\n" if (ws or imgs) else ""


def _new_window(kind, title, pos, **extra):
    S["n"] += 1
    w = {"id": f"w{S['n']}", "type": kind, "title": title, "pos": pos, "zoom": 1.0, "cx": 0.5,
         "cy": 0.5, "tag": "", "file": "", "text": "", "v": int(time.time())}
    w.update(extra)
    return w


def _clear_panel_if_needed(pos):
    """A destra o al centro non c'e' posto per la finestra dei pulsanti: la chiude."""
    if pos in ("right", "center", "full", "br", "tr"):
        try:
            if tools.panel_snapshot()["type"]:
                tools.panel_close()
        except Exception:
            pass


def _on_panel_open():
    """Quando si apre una finestra dei pulsanti (calendario, meteo...) le foto lasciano la destra."""
    with _lock:
        moved = False
        for w in S["windows"]:
            if w["pos"] in ("right", "center", "full", "br", "tr"):
                w["pos"] = "left" if w["pos"] in ("right", "center", "full") else "bl"
                moved = True
        if moved:
            _bump()


tools.PANEL_OPEN_HOOKS.append(_on_panel_open)


def _open_file(name, pos, tag=""):
    """Apre (o sposta, se e' gia' aperto) un file della cartella Documenti. Ritorna la finestra."""
    path = images.safe_path(name)
    if not path:
        raise ValueError(f"non trovo il file {name}")
    base = os.path.basename(path)
    _ensure_hud()
    _clear_panel_if_needed(pos)
    with _lock:
        # chi occupa gia' quel posto viene chiuso (una finestra per posto, niente sovrapposizioni)
        S["windows"] = [x for x in S["windows"] if x["pos"] != pos or x.get("file") == base]
        for w in S["windows"]:
            if w.get("file") == base:                      # gia' aperto: lo porta in primo piano
                w.update(pos=pos, tag=tag or w["tag"], v=int(os.path.getmtime(path)))
                S["windows"].remove(w)
                S["windows"].append(w)
                _bump()
                return w
        if images.is_image(base):
            w = _new_window("image", os.path.splitext(base)[0], pos, file=base, tag=tag,
                            v=int(os.path.getmtime(path)))
        else:
            text = tools._read_doc_text(path)                # solo docx/txt/md/csv
            w = _new_window("text", os.path.splitext(base)[0], pos, file=base, tag=tag, text=text[:20000])
        S["windows"].append(w)
        _bump()
    if w["type"] == "image":
        threading.Thread(target=_caption_async, args=(w["id"], path), daemon=True).start()
    return w


def _caption_async(wid, path):
    """In background: Gemini guarda la foto e ne annota cosa mostra, cosi' Jarvis 'sa' cosa c'e' aperto."""
    try:
        d = images.caption(path)
    except Exception as e:
        print("[scrivania] non riesco a descrivere la foto:", str(e)[:120])
        return
    with _lock:
        for w in S["windows"]:
            if w["id"] == wid:
                w["desc"] = d


def _select(quale):
    """Capisce a quale finestra ci si riferisce: 'ultima', 'sinistra', 'l'originale', 'quella vecchia', 'mare'..."""
    q = (quale or "").lower().strip()
    with _lock:
        ws = list(S["windows"])
    if not ws:
        return []
    imgs = [w for w in ws if w["type"] == "image"]
    if q in ("", "ultima", "ultimo", "questa", "questo", "quella", "quello", "corrente", "attuale", "la foto",
             "foto", "primo piano", "in primo piano"):
        return [ws[-1]]
    if q in ("tutte", "tutto", "tutti", "entrambe", "entrambi", "le due", "tutte e due"):
        return ws
    if "sinistr" in q:
        return [w for w in ws if w["pos"] == "left"][-1:]
    if "destr" in q:
        return [w for w in ws if w["pos"] == "right"][-1:]
    if "central" in q or "mezzo" in q:
        return [w for w in ws if w["pos"] == "center"][-1:]
    if q in ("prima", "la prima", "primo", "1", "uno"):
        return [ws[0]]
    if q in ("seconda", "la seconda", "secondo", "2", "due"):
        return [ws[1]] if len(ws) > 1 else []
    if q in ("terza", "la terza", "terzo", "3", "tre"):
        return [ws[2]] if len(ws) > 2 else []
    if "original" in q or "vecchi" in q or "precedent" in q or "inizial" in q or "prima della" in q:
        hit = [w for w in imgs if w["tag"] == "ORIGINALE"] \
            or [w for w in imgs if not images.original_of(w.get("file", ""))]
        if "vecchi" in q and len(imgs) > 1:                 # la piu' vecchia per data del file
            hit = sorted(imgs, key=lambda w: w["v"])[:1]
        if hit:
            return hit[-1:]
    if "modificat" in q or "ritoccat" in q or "nuova" in q or "nuovo" in q or "recente" in q or "dopo" in q:
        hit = [w for w in imgs if images.original_of(w.get("file", "")) or w["tag"] == "MODIFICATA"]
        if hit:
            return hit[-1:]
        if imgs:
            return sorted(imgs, key=lambda w: w["v"])[-1:]
    hits = [w for w in ws if q in w["title"].lower() or q in (w.get("desc") or "").lower()]
    if not hits:
        words = [x for x in re.findall(r"\w+", q) if len(x) > 2]
        hits = [w for w in ws if words and any(x in w["title"].lower() or x in (w.get("desc") or "").lower()
                                               for x in words)]
    return hits[-1:]


def _not_found(quale):
    if not has_windows():
        return "Non c'è nessuna finestra aperta sullo schermo."
    return f"Non trovo una finestra che corrisponda a '{quale}'. " + describe()


# ---------------------------- STRUMENTI PER GEMINI ----------------------------
@tools._tool("Apro il file.")
def apri_file(nome: str, posizione: str = "centro") -> str:
    """Apre sullo schermo una foto o un documento della cartella Documenti, in una finestra. Se è già aperto lo porta in primo piano.

    Args:
        nome: parte del nome del file (esempio: "mare" o "lettera"). "ultima" = la foto più recente.
        posizione: "sinistra", "destra", "centro", "schermo intero" o un angolo piccolo ("in basso a sinistra", "in alto a destra"...).
    """
    pos = _pos(posizione)
    path, fname, altre = images.find_image(nome)
    if not path:                                           # non e' una foto: forse un documento
        key = (nome or "").lower().strip()
        match = [n for _t, n, _s in tools._list_docs() if key and key in n.lower()]
        if not match:
            nomi = ", ".join(n for _p, n, _t in images.list_images()[:5]) or "nessuna foto"
            return f"Non trovo nessun file con '{nome}' nel nome. Foto disponibili: {nomi}."
        fname, altre = match[0], match[1:4]
    w = _open_file(fname, pos)
    extra = f" Ci sono anche: {', '.join(altre)}." if altre else ""
    return f"Aperto «{w['title']}» {_POS_IT[pos]} (se c'era già una finestra in quel posto è stata chiusa).{extra}"


@tools._tool("Sposto la finestra.")
def sposta_finestra(quale: str, posizione: str) -> str:
    """Sposta una finestra aperta sullo schermo (foto o documento).

    Args:
        quale: quale finestra: "ultima", "sinistra", "destra", "centro", "tutte" oppure parte del nome (esempio: "mare").
        posizione: dove metterla: "sinistra", "destra", "centro", "schermo intero" oppure un angolo in piccolo: "in basso a sinistra", "in basso a destra", "in alto a sinistra", "in alto a destra". Per 'rimpicciolisci e mettila nell'angolo' usa un angolo (NON modifica_immagine, che cambierebbe la foto).
    """
    pos = _pos(posizione, "")
    if not pos:
        return "Posizione non valida: usa sinistra, destra, centro o schermo intero."
    ws = _select(quale)
    if not ws:
        return _not_found(quale)
    _clear_panel_if_needed(pos)
    with _lock:
        ids = {w["id"] for w in ws}
        S["windows"] = [x for x in S["windows"] if x["pos"] != pos or x["id"] in ids]   # libera il posto
        for w in ws:
            w["pos"] = pos
            if w in S["windows"]:
                S["windows"].remove(w)
                S["windows"].append(w)
        _bump()
    return f"Spostato «{ws[-1]['title']}» {_POS_IT[pos]}."


@tools._tool("Zoom.")
def zoom_finestra(quale: str = "", livello: float = 2.0, centro_x: float = 0.5, centro_y: float = 0.5) -> str:
    """Cambia SOLO la vista (ingrandisce o riduce) di una foto aperta, senza modificare il file. Per ritagliare o cambiare davvero la foto usa modifica_immagine.

    Args:
        quale: quale finestra: "ultima", "sinistra", "destra", "tutte" o parte del nome.
        livello: ingrandimento: 1 = foto intera, 2 = il doppio, 4 = quadruplo (da 1 a 8). Per "ingrandisci ancora" parti dallo zoom attuale.
        centro_x: punto da mettere al centro, da 0 (sinistra) a 1 (destra). Esempio: "in alto a sinistra" = 0.25.
        centro_y: punto da mettere al centro, da 0 (alto) a 1 (basso). Esempio: "in alto a sinistra" = 0.25.
    """
    ws = [w for w in _select(quale) if w["type"] == "image"]
    if not ws:
        return _not_found(quale) if not _select(quale) else "Lo zoom funziona solo sulle foto."
    z = min(max(float(livello), 1.0), 8.0)
    cx, cy = min(max(float(centro_x), 0.0), 1.0), min(max(float(centro_y), 0.0), 1.0)
    with _lock:
        for w in ws:
            w.update(zoom=z, cx=cx, cy=cy)
        _bump()
    return f"Zoom {z:.1f} volte su «{ws[-1]['title']}»."


@tools._tool("Chiudo.")
def chiudi_finestra(quale: str = "ultima") -> str:
    """Chiude una o più finestre aperte sullo schermo (foto o documenti).

    Args:
        quale: "ultima", "sinistra", "destra", "centro", "tutte" oppure parte del nome.
    """
    ws = _select(quale)
    if not ws:
        return _not_found(quale)
    for w in ws:
        close_window(w["id"])
    return "Chiuso: " + ", ".join(f"«{w['title']}»" for w in ws) + "."


@tools._tool("Le affianco.")
def affianca(prima: str = "", seconda: str = "") -> str:
    """Mette due finestre affiancate: la prima a sinistra e la seconda a destra. Senza argomenti usa le due finestre più recenti.

    Args:
        prima: finestra da mettere a sinistra (parte del nome, "originale"...). Vuoto = la penultima aperta.
        seconda: finestra da mettere a destra (parte del nome, "modificata"...). Vuoto = l'ultima aperta.
    """
    with _lock:
        ws = list(S["windows"])
    if len(ws) < 2 and not (prima and seconda):
        return "Servono due finestre aperte per affiancarle."
    a = _select(prima)[0] if prima else ws[-2]
    b = _select(seconda)[0] if seconda else ws[-1]
    if a is None or b is None or a["id"] == b["id"]:
        return "Non riesco a capire quali due finestre affiancare. " + describe()
    _clear_panel_if_needed("right")
    with _lock:
        a["pos"], b["pos"] = "left", "right"
        for w in (a, b):
            S["windows"].remove(w)
            S["windows"].append(w)
        _bump()
    return f"Affiancate: «{a['title']}» a sinistra e «{b['title']}» a destra."


@tools._tool("Confronto le foto.")
def confronta_immagini(prima: str, seconda: str) -> str:
    """Apre due foto una accanto all'altra (la prima a sinistra, la seconda a destra) per confrontarle.

    Args:
        prima: nome (o parte) della prima foto.
        seconda: nome (o parte) della seconda foto.
    """
    p1, n1, _a = images.find_image(prima)
    p2, n2, _b = images.find_image(seconda)
    if not p1 or not p2:
        return "Non trovo una delle due foto. Foto disponibili: " + ", ".join(n for _p, n, _t in images.list_images()[:6])
    _open_file(n1, "left")
    _open_file(n2, "right")
    return f"Aperte affiancate: «{os.path.splitext(n1)[0]}» a sinistra e «{os.path.splitext(n2)[0]}» a destra."


@tools._tool("Modifico la foto.")
def modifica_immagine(nome: str = "ultima", ritaglia: str = "", ruota_gradi: int = 0, specchia: str = "",
                      ridimensiona_percento: int = 100, luminosita: float = 1.0, contrasto: float = 1.0,
                      saturazione: float = 1.0, nitidezza: float = 1.0, sfoca: float = 0.0,
                      filtro: str = "", migliora: bool = False, mostra_affiancata: bool = False) -> str:
    """Modifica una foto: crea una COPIA modificata (l'originale non viene mai toccato) e la mostra sullo schermo. Per solo guardare più da vicino usa zoom_finestra.

    Args:
        nome: parte del nome della foto; "ultima" = la foto in primo piano sullo schermo.
        ritaglia: ritaglia/ingrandisce una zona: quattro numeri in percentuale "sinistra,alto,destra,basso" (esempio: "0,0,50,50" = quarto in alto a sinistra; "25,25,75,75" = la parte centrale).
        ruota_gradi: gradi in senso orario (90 = un quarto di giro a destra, -90 = a sinistra).
        specchia: "orizzontale" (destra<->sinistra) o "verticale" (sopra<->sotto).
        ridimensiona_percento: 100 = invariata, 50 = metà, 200 = doppia.
        luminosita: 1 = invariata, 1.3 = più luminosa, 0.7 = più scura.
        contrasto: 1 = invariato, 1.3 = più contrasto.
        saturazione: 1 = invariata, 1.4 = colori più vivi, 0 = nessun colore.
        nitidezza: 1 = invariata, 2 = più nitida.
        sfoca: 0 = niente, 2-8 = sfocatura.
        filtro: "bianco e nero", "seppia", "negativo" o "contorni". Vuoto = nessuno.
        migliora: True per un miglioramento automatico (contrasto, colori, nitidezza).
        mostra_affiancata: True se l'utente vuole vedere l'originale e la modificata una accanto all'altra (originale a sinistra, modificata a destra).
    """
    path, fname = _source(nome)
    if not path:
        nomi = ", ".join(n for _p, n, _t in images.list_images()[:5]) or "nessuna foto"
        return f"Non trovo la foto '{nome}'. Foto disponibili: {nomi}."
    out, done = images.edit(path, ritaglia, ruota_gradi, specchia, ridimensiona_percento, luminosita,
                            contrasto, saturazione, nitidezza, sfoca, filtro, migliora)
    where = _show_result(fname, os.path.basename(out), mostra_affiancata)
    return (f"Fatto: foto {', '.join(done)}. Salvata come «{os.path.basename(out)}» (l'originale non è stato "
            f"toccato). Sullo schermo: {where}.")


@tools._tool("Modifico la foto con l'intelligenza artificiale.")
def modifica_con_ai(istruzioni: str, nome: str = "ultima", aggiungi_foto: str = "",
                    mostra_affiancata: bool = False) -> str:
    """Modifica una foto con l'intelligenza artificiale, come se fosse mandata a Gemini o ChatGPT: aggiungere o togliere oggetti o persone, cambiare lo sfondo, il vestito, l'ora del giorno, lo stile (cartone, quadro), ritoccare il viso, fondere due foto... Crea una COPIA (l'originale non viene mai toccato) e la mostra sullo schermo. Per semplici ritocchi (ritaglio, rotazione, luminosità, bianco e nero) usa invece modifica_immagine, che è istantanea. Ci vogliono alcuni secondi.

    Args:
        istruzioni: cosa fare, in modo chiaro e dettagliato (esempio: "aggiungi un cappello da cowboy al cane", "cambia lo sfondo con un tramonto sul mare", "togli la persona a destra"). Scrivi tu l'istruzione completa a partire da ciò che ha detto l'utente.
        nome: la foto da modificare: "ultima" = quella in primo piano; anche "originale", "sinistra", "destra" o parte del nome.
        aggiungi_foto: facoltativo, un'altra foto da usare come riferimento (esempio: "metti nella prima foto il cappello della seconda"): nome o parte del nome.
        mostra_affiancata: True se l'utente vuole vedere originale e modificata una accanto all'altra.
    """
    path, fname = _source(nome)
    if not path:
        nomi = ", ".join(n for _p, n, _t in images.list_images()[:5]) or "nessuna foto"
        return f"Non trovo la foto '{nome}'. Foto disponibili: {nomi}."
    extra = []
    if (aggiungi_foto or "").strip():
        ep, _en = _source(aggiungi_foto)
        if not ep or ep == path:
            return f"Non trovo la foto di riferimento '{aggiungi_foto}'."
        extra.append(ep)
    out = images.ai_edit(path, istruzioni, extra)          # se fallisce, _tool riporta l'errore a Jarvis
    where = _show_result(fname, os.path.basename(out), mostra_affiancata)
    return (f"Fatto con l'intelligenza artificiale: «{os.path.basename(out)}» (l'originale non è stato "
            f"toccato). Sullo schermo: {where}. Se il risultato non è come voleva, può chiedere un altro tentativo.")


def _source(nome):
    """La foto a cui ci si riferisce: prima tra le finestre aperte ('originale', 'sinistra'...), poi in cartella."""
    q = (nome or "").lower().strip()
    ws = [w for w in _select(q) if w["type"] == "image"]
    if ws:
        path = images.safe_path(ws[-1]["file"])
        if path:
            return path, ws[-1]["file"]
    path, fname, _o = images.find_image(q)
    return path, fname


def _show_result(fname, out_name, affiancata):
    with _lock:
        old = next((w for w in S["windows"] if w.get("file") == fname), None)
        pos_old = old["pos"] if old else "center"
    if affiancata:
        _open_file(fname, "left", "ORIGINALE")
        _open_file(out_name, "right", "MODIFICATA")
        return "originale a sinistra, modificata a destra"
    if old:
        close_window(old["id"])
    _open_file(out_name, pos_old, "MODIFICATA")
    return f"modificata {_POS_IT[pos_old]}"


@tools._tool("Guardo lo schermo.")
def guarda_schermo(domanda: str = "") -> str:
    """Guarda DAVVERO le foto e i documenti aperti sullo schermo e risponde: descrive cosa c'è, trova dettagli, confronta due foto (cosa è cambiato tra originale e modificata), legge testi. Usalo ogni volta che l'utente chiede 'cosa vedi', 'cosa c'è nella foto', 'che differenza c'è', 'c'è un ... nella foto?'.

    Args:
        domanda: cosa vuole sapere l'utente; vuoto = descrizione generale di tutto ciò che è aperto.
    """
    ws = snapshot()["windows"]
    if not ws:
        return "Non c'è nessuna finestra aperta sullo schermo."
    items, testi = [], []
    for i, w in enumerate(ws, 1):
        if w["type"] == "image":
            p = images.safe_path(w["file"])
            if p:
                items.append((p, f"Finestra {i}: {w['title']}" + (f" ({w['tag']})" if w.get("tag") else "")
                              + f", {_POS_IT[w['pos']]}"))
        else:
            testi.append(f"[Documento {i}: {w['title']}]\n{w['text'][:3000]}")
    q = (domanda or "").strip() or "Descrivi cosa vedi in ciascuna finestra."
    full = ("Rispondi in italiano, in modo chiaro e breve (massimo 4 frasi), alla richiesta dell'utente sulle "
            "finestre aperte sul suo schermo. Se ci sono più foto, di' a quale ti riferisci. Richiesta: " + q
            + ("\n\n" + "\n\n".join(testi) if testi else ""))
    if items:
        return images.ask_about(items, full)
    return images._client().models.generate_content(model=images._cfg().GEMINI_MODEL, contents=full).text.strip()


@tools._tool("Chiudo tutto.")
def chiudi_tutto_lo_schermo() -> str:
    """Chiude tutte le finestre aperte sullo schermo (foto, documenti e pannelli)."""
    close_all()
    tools.panel_close()
    return "Schermo pulito."


DESK_TOOLS = [apri_file, sposta_finestra, zoom_finestra, chiudi_finestra, affianca,
              confronta_immagini, guarda_schermo, modifica_immagine, modifica_con_ai, chiudi_tutto_lo_schermo]


# ---------------------------- PONTE PER TELEGRAM ----------------------------
# Telegram gira in un altro programma: manda i comandi allo schermo del PC tramite jarvis_wake.
REMOTE = {f.__name__: f for f in DESK_TOOLS}


def run_remote(name, kwargs):
    """Esegue un comando arrivato da Telegram (senza far parlare il PC)."""
    import inspect
    fn = REMOTE.get(name)
    if not fn:
        return "Comando sconosciuto."
    allowed = set(inspect.signature(fn.__wrapped__).parameters)
    clean = {k: v for k, v in (kwargs or {}).items() if k in allowed}
    with tools.quiet():
        return fn(**clean)
