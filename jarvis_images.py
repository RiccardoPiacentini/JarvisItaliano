# ============================================================
#  JARVIS IMAGES - ritocco foto (condiviso da PC e Telegram)
#  Usa Pillow:  pip install pillow
#  Le foto vivono nella cartella Documenti. L'ORIGINALE non viene mai
#  toccato: ogni modifica crea un file nuovo "... (modificata).jpg".
# ============================================================
import os
import re

import jarvis_tools as tools

IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif", ".bmp": "image/bmp"}


def _pil():
    try:
        from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw, ImageFont
        return Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw, ImageFont
    except ImportError:
        raise RuntimeError("manca Pillow: apri il terminale e scrivi  pip install pillow")


def is_image(name):
    return (name or "").lower().endswith(IMG_EXT)


def list_images():
    """[(percorso, nome, data)] dalla piu' recente."""
    folder = tools._docs_dir()
    out = []
    for t, n, _sz in tools._list_docs():
        if is_image(n):
            out.append((os.path.join(folder, n), n, t))
    return out


def safe_path(name):
    """Percorso di un file della cartella Documenti (solo li'), altrimenti None."""
    folder = os.path.realpath(tools._docs_dir())
    path = os.path.realpath(os.path.join(folder, os.path.basename(name or "")))
    if os.path.dirname(path) != folder or not os.path.isfile(path):
        return None
    return path


def find_image(query):
    """Trova una foto dal nome (anche solo una parte). Ritorna (percorso, nome, altre_corrispondenze)."""
    imgs = list_images()
    q = (query or "").lower().strip()
    q = re.sub(r"\.(jpe?g|png|webp|gif|bmp)$", "", q)
    if not imgs:
        return None, None, []
    if not q or q in ("ultima", "ultimo", "ultima foto", "la foto", "foto", "immagine"):
        p, n, _t = imgs[0]
        return p, n, [x[1] for x in imgs[1:4]]
    if re.search(r"vecchi|primissim|meno recente", q):
        p, n, _t = imgs[-1]
        return p, n, [x[1] for x in imgs[-4:-1]]
    if "penultim" in q and len(imgs) > 1:
        p, n, _t = imgs[1]
        return p, n, []
    words = [w for w in re.findall(r"\w+", q) if len(w) > 1]
    exact = [x for x in imgs if os.path.splitext(x[1])[0].lower() == q]      # nome preciso: vince su "(modificata)"
    if exact:
        p, n, _t = exact[0]
        return p, n, [x[1] for x in imgs if x[1] != n and q in x[1].lower()][:3]
    hits = [x for x in imgs if q in x[1].lower()]
    if not hits and words:
        scored = [(sum(1 for w in words if w in x[1].lower()), x) for x in imgs]
        best = max((s for s, _ in scored), default=0)
        hits = [x for s, x in scored if s == best and s > 0]
    if not hits:
        return None, None, [x[1] for x in imgs[:5]]
    p, n, _t = hits[0]
    return p, n, [x[1] for x in hits[1:4]]


def unique_path(stem, ext=".jpg"):
    folder = tools._docs_dir()
    path = os.path.join(folder, stem + ext)
    n = 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{stem} {n}{ext}")
        n += 1
    return path


def edited_path(path, ext=".jpg"):
    """Nome libero per la copia modificata: 'Nome (modificata).jpg' (mai sopra un file esistente)."""
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r"\s*\(modificata\)(\s*\d*)$", "", stem)
    return unique_path(f"{stem} (modificata)", ext)


def original_of(name):
    """'Mare (modificata) 2.jpg' -> 'Mare' (nome senza estensione) se e' una copia modificata, altrimenti None."""
    stem = os.path.splitext(os.path.basename(name or ""))[0]
    m = re.match(r"^(.*?)\s*\(modificata\)(\s*\d*)$", stem)
    return m.group(1) if m else None


def _parse_box(s, w, h):
    """'10,10,60,60' (percentuali: sinistra, alto, destra, basso) -> riquadro in pixel."""
    nums = [float(x) for x in re.findall(r"-?\d+(?:[.,]\d+)?", (s or "").replace(",", " ").replace(";", " "))]
    if len(nums) != 4:
        raise ValueError("il ritaglio vuole 4 numeri: sinistra, alto, destra, basso (in percentuale)")
    l, t, r, b = [min(max(v, 0.0), 100.0) for v in nums]
    if r <= l or b <= t:
        raise ValueError("ritaglio non valido: destra e basso devono superare sinistra e alto")
    return (int(w * l / 100), int(h * t / 100), int(w * r / 100), int(h * b / 100))


def edit(path, ritaglia="", ruota_gradi=0, specchia="", ridimensiona_percento=100, luminosita=1.0,
         contrasto=1.0, saturazione=1.0, nitidezza=1.0, sfoca=0.0, filtro="", migliora=False):
    """Applica le modifiche e salva una COPIA. Ritorna (nuovo_percorso, elenco_di_cosa_ho_fatto)."""
    Image, ImageOps, ImageEnhance, ImageFilter, _d, _f = _pil()
    done = []
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    im = im.convert("RGBA" if has_alpha else "RGB")
    if ritaglia and str(ritaglia).strip():
        im = im.crop(_parse_box(ritaglia, *im.size))
        done.append("ritagliata")
    if ruota_gradi and int(ruota_gradi) % 360:
        im = im.rotate(-int(ruota_gradi), expand=True)          # positivo = senso orario
        done.append(f"ruotata di {int(ruota_gradi)} gradi")
    sp = (specchia or "").lower()
    if "orizz" in sp or sp in ("destra", "sinistra", "specchio"):
        im = ImageOps.mirror(im)
        done.append("specchiata in orizzontale")
    elif "vert" in sp or sp in ("sopra", "sotto"):
        im = ImageOps.flip(im)
        done.append("capovolta")
    pct = int(ridimensiona_percento or 100)
    if pct != 100:
        pct = min(max(pct, 5), 400)
        im = im.resize((max(1, im.width * pct // 100), max(1, im.height * pct // 100)), Image.LANCZOS)
        done.append(f"ridimensionata al {pct} per cento")
    if migliora:
        base = im.convert("RGB")
        base = ImageOps.autocontrast(base, cutoff=1)
        base = ImageEnhance.Color(base).enhance(1.12)
        base = ImageEnhance.Sharpness(base).enhance(1.25)
        if has_alpha:
            a = im.split()[-1]
            im = base.convert("RGBA")
            im.putalpha(a)
        else:
            im = base
        done.append("migliorata (contrasto, colore, nitidezza)")

    def enh(cls, val, label):
        nonlocal im
        v = float(val)
        if abs(v - 1.0) > 0.01:
            v = min(max(v, 0.0), 4.0)
            if has_alpha:
                a = im.split()[-1]
                im = cls(im.convert("RGB")).enhance(v).convert("RGBA")
                im.putalpha(a)
            else:
                im = cls(im).enhance(v)
            done.append(label)

    enh(ImageEnhance.Brightness, luminosita, "luminosità " + ("aumentata" if float(luminosita) > 1 else "ridotta"))
    enh(ImageEnhance.Contrast, contrasto, "contrasto " + ("aumentato" if float(contrasto) > 1 else "ridotto"))
    enh(ImageEnhance.Color, saturazione, "colori " + ("più vivi" if float(saturazione) > 1 else "più spenti"))
    enh(ImageEnhance.Sharpness, nitidezza, "nitidezza " + ("aumentata" if float(nitidezza) > 1 else "ridotta"))
    if float(sfoca or 0) > 0:
        im = im.filter(ImageFilter.GaussianBlur(min(float(sfoca), 40)))
        done.append("sfocata")
    f = (filtro or "").lower().strip()
    if f:
        rgb = im.convert("RGB")
        if "bianco" in f or "nero" in f or "grigi" in f:
            rgb = ImageOps.grayscale(rgb).convert("RGB")
            done.append("in bianco e nero")
        elif "seppia" in f:
            rgb = ImageOps.colorize(ImageOps.grayscale(rgb), "#2b1a0a", "#f3e2bd")
            done.append("effetto seppia")
        elif "negativo" in f or "inver" in f:
            rgb = ImageOps.invert(rgb)
            done.append("negativo")
        elif "contorn" in f or "bordi" in f:
            rgb = ImageOps.autocontrast(rgb.filter(ImageFilter.FIND_EDGES))
            done.append("solo contorni")
        else:
            raise ValueError("filtro sconosciuto: usa 'bianco e nero', 'seppia', 'negativo' o 'contorni'")
        if has_alpha:
            a = im.split()[-1]
            im = rgb.convert("RGBA")
            im.putalpha(a)
        else:
            im = rgb
    if not done:
        raise ValueError("nessuna modifica richiesta")
    ext = ".png" if has_alpha else ".jpg"
    out = edited_path(path, ext)
    if ext == ".jpg":
        im.convert("RGB").save(out, quality=92, optimize=True)
    else:
        im.save(out)
    return out, done


def side_by_side(path_a, path_b, label_a="ORIGINALE", label_b="MODIFICATA"):
    """Una sola immagine con le due foto affiancate (per Telegram). Ritorna il percorso."""
    Image, ImageOps, _e, _f, ImageDraw, ImageFont = _pil()
    a = ImageOps.exif_transpose(Image.open(path_a)).convert("RGB")
    b = ImageOps.exif_transpose(Image.open(path_b)).convert("RGB")
    h = min(max(a.height, b.height), 1100)
    a = a.resize((max(1, int(a.width * h / a.height)), h), Image.LANCZOS)
    b = b.resize((max(1, int(b.width * h / b.height)), h), Image.LANCZOS)
    gap, top = 24, 46
    canvas = Image.new("RGB", (a.width + b.width + gap * 3, h + top + gap), "#06202e")
    canvas.paste(a, (gap, top))
    canvas.paste(b, (a.width + gap * 2, top))
    d = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.load_default(size=22)
    except TypeError:
        font = ImageFont.load_default()
    d.text((gap, 12), label_a, fill="#00e5ff", font=font)
    d.text((a.width + gap * 2, 12), label_b, fill="#7dffb0", font=font)
    import tempfile                      # fuori da Documenti: non e' una foto dell'utente
    fd, out = tempfile.mkstemp(prefix="jarvis_confronto_", suffix=".jpg")
    os.close(fd)
    canvas.save(out, quality=90)
    return out


def describe_edit(done):
    return ", ".join(done)


# ====================== OCCHI E MODIFICHE CON L'AI (Gemini) ======================
CAPS = {}                       # descrizioni gia' fatte: (percorso, data) -> testo


def _client():
    import jarvis                  # riusa il client Gemini gia' configurato
    return jarvis.client


def _cfg():
    import impostazioni as cfg
    return cfg


def _jpeg(path, maxside=1280):
    """La foto ridotta e in JPEG, pronta da mandare a Gemini."""
    import io
    Image, ImageOps, *_r = _pil()
    im = ImageOps.exif_transpose(Image.open(path))
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, "white")
        im = im.convert("RGBA")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    im.thumbnail((maxside, maxside))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def ask_about(items, question):
    """Mostra a Gemini una o piu' foto e fa una domanda.  items = [(percorso, etichetta)]."""
    from google.genai import types
    parts = []
    for path, label in items:
        parts.append(f"[{label}]")
        parts.append(types.Part.from_bytes(data=_jpeg(path), mime_type="image/jpeg"))
    parts.append(question)
    r = _client().models.generate_content(model=_cfg().GEMINI_MODEL, contents=parts)
    return (r.text or "").strip()


def caption(path):
    """Una frase che dice cosa c'e' nella foto (con cache)."""
    key = (path, os.path.getmtime(path))
    if key not in CAPS:
        CAPS[key] = ask_about([(path, os.path.basename(path))],
                              "Descrivi in italiano, in una sola frase di massimo 25 parole, cosa si vede "
                              "in questa foto (soggetti, luogo, colori, azione). Solo la descrizione.")
    return CAPS[key]


def _img_model():
    return getattr(_cfg(), "MODELLO_IMMAGINI", "gemini-2.5-flash-image")


def ai_edit(path, instruction, extra_paths=()):
    """Modifica la foto con l'AI (come mandarla a Gemini/ChatGPT) e salva una COPIA. Ritorna il nuovo percorso."""
    import base64
    from google.genai import types
    contents = [types.Part.from_bytes(data=_jpeg(path, 1600), mime_type="image/jpeg")]
    for ep in extra_paths:
        contents.append(types.Part.from_bytes(data=_jpeg(ep, 1200), mime_type="image/jpeg"))
    contents.append("Modifica la foto seguendo questa richiesta, mantenendo il resto identico e restituisci "
                    "l'immagine modificata. Richiesta: " + instruction
                    + ("  (Le foto successive alla prima sono immagini di riferimento da usare.)" if extra_paths else ""))
    try:
        r = _client().models.generate_content(
            model=_img_model(), contents=contents,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]))
    except Exception as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            raise RuntimeError("il modello di modifica immagini ha finito la quota gratuita o non è incluso "
                               "nel tuo piano Google (serve eventualmente attivare la fatturazione su AI Studio)")
        if "404" in msg or "NOT_FOUND" in msg:
            raise RuntimeError(f"il modello immagini '{_img_model()}' non esiste per la tua chiave: "
                               "scrivi in impostazioni.py MODELLO_IMMAGINI = \"nome-del-modello\"")
        raise RuntimeError("la modifica con l'AI non è riuscita: " + msg[:160])
    data, said, n_parts = None, "", 0
    for c in (r.candidates or []):
        for part in (c.content.parts if c.content else []) or []:
            n_parts += 1
            if getattr(part, "inline_data", None) and part.inline_data.data:
                data = part.inline_data.data
            elif getattr(part, "text", None):
                said += part.text
    print(f"[immagini] modello {_img_model()}: {n_parts} parti, immagine={'si' if data else 'NO'}, testo={said[:120]!r}")
    if data is None:
        why = ""
        try:
            why = f" (motivo: {r.candidates[0].finish_reason})" if r.candidates else f" (motivo: {r.prompt_feedback})"
        except Exception:
            pass
        raise RuntimeError("l'AI non ha restituito nessuna immagine" + (f": ha risposto «{said[:150]}»" if said else "") + why)
    if isinstance(data, str):
        data = base64.b64decode(data)
    elif not (data[:3] == b"\xff\xd8\xff" or data[:4] == b"\x89PNG"):
        try:
            data = base64.b64decode(data, validate=True)
        except Exception:
            pass
    try:                                       # controllo che sia davvero un'immagine leggibile
        import io
        Image = _pil()[0]
        Image.open(io.BytesIO(data)).verify()
    except Exception:
        raise RuntimeError("l'AI ha restituito un'immagine che non riesco a leggere")
    ext = ".png" if data[:4] == b"\x89PNG" else ".jpg"
    out = edited_path(path, ext)
    with open(out, "wb") as f:
        f.write(data)
    print(f"[immagini] salvata {out} ({len(data)//1024} KB)")
    return out
