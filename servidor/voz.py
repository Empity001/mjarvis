"""Voz y oído de M-Jarvis. Todo corre en esta máquina, sin internet:

  - VOZ: Piper (síntesis neuronal, voces en `modelos/es/...`). Convierte una frase en audio WAV.
  - OÍDO: faster-whisper (modelo `small`, int8) convierte el audio del micrófono en texto.

Se cargan al primer uso y el oído se descarga solo tras un rato sin usarse, para devolver la memoria
al modelo de lenguaje (la máquina tiene 8 GB). La voz elegida y su velocidad viven en
comportamiento/voz.json y se releen solas.
"""
import io
import json
import re
import threading
import time
import wave
from collections import OrderedDict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELOS = RAIZ / "modelos"
CONFIG = RAIZ / "comportamiento" / "voz.json"
POR_DEFECTO = {
    "voz": "es/es_MX/claude/high/es_MX-claude-high",   # ruta dentro de modelos/ (sin extensión)
    "velocidad": 1.05,                                  # >1 habla más despacio
    "oido": "faster-whisper-small",
    "descargar_oido_tras_s": 600,
    "guia": "Conversación en español dominicano con M-Jarvis, un asistente sobre el universo Marvel: Iron Man, Tony Stark, "
            "Thor, Hulk, Thanos, Loki, Vengadores, Spider-Man, Pantera Negra, Guardianes de la Galaxia, Capitán América.",
}
MAX_TEXTO = 600
MAX_AUDIO = 8 * 1024 * 1024  # ~ minuto y medio de voz comprimida


def configuracion():
    datos = dict(POR_DEFECTO)
    try:
        datos.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return datos


# ---- Preparar el texto para que suene bien ----

SUSTITUCIONES = [
    (r"\bM-Jarvis\b", "Eme Jarvis"), (r"\bJ\.A\.R\.V\.I\.S\.?", "Jarvis"), (r"\bMCU\b", "Eme Ce U"), (r"\bDr\.", "Doctor"),
    (r"\bSr\.", "señor"), (r"\bvs\.?\b", "contra"), (r"\bTV\b", "te uve"), (r"\bIA\b", "inteligencia artificial"),
    (r"\bkg\b", "kilogramos"), (r"\bmm\b", "milímetros"), (r"\bcm\b", "centímetros"), (r"%", " por ciento"),
]


def preparar_texto(texto):
    t = re.sub(r"\(Aviso:.*?\)", " ", texto, flags=re.S)          # los avisos de cifras se leen, no se dicen
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"[☀-➿\U0001F300-\U0001FAFF]", " ", t)    # emojis
    t = t.replace("«", "").replace("»", "").replace("“", "").replace("”", "").replace('"', "")
    t = re.sub(r"\s*[•·*_#]+\s*", " ", t)
    for patron, cambio in SUSTITUCIONES:
        t = re.sub(patron, cambio, t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:MAX_TEXTO]


# ---- Voz ----

class Voz:
    def __init__(self):
        self.candado = threading.Lock()
        self.voz = None
        self.ruta = None
        self.cache = OrderedDict()   # texto -> wav (las frases fijas se repiten mucho)
        self.error = None

    def _cargar(self, cfg):
        ruta = MODELOS / (cfg["voz"] + ".onnx")
        if self.voz is not None and self.ruta == ruta:
            return
        from piper import PiperVoice
        self.voz = PiperVoice.load(str(ruta))
        self.ruta = ruta
        self.cache.clear()

    def disponible(self):
        try:
            return (MODELOS / (configuracion()["voz"] + ".onnx")).exists() and __import__("piper") is not None
        except ImportError:
            return False

    def sintetizar(self, texto):
        """Devuelve los bytes de un WAV con el texto dicho, o None si no hay nada que decir."""
        limpio = preparar_texto(texto)
        if not re.search(r"\w", limpio):
            return None
        cfg = configuracion()
        clave = (cfg["voz"], cfg["velocidad"], limpio)
        with self.candado:
            if clave in self.cache:
                self.cache.move_to_end(clave)
                return self.cache[clave]
            self._cargar(cfg)
            from piper import SynthesisConfig
            ajuste = SynthesisConfig(length_scale=float(cfg["velocidad"]), noise_scale=0.6, noise_w_scale=0.7)
            pcm, tasa = [], 22050
            for trozo in self.voz.synthesize(limpio, syn_config=ajuste):
                pcm.append(trozo.audio_int16_bytes)
                tasa = trozo.sample_rate
            salida = io.BytesIO()
            with wave.open(salida, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(tasa)
                w.writeframes(b"".join(pcm))
            datos = salida.getvalue()
            self.cache[clave] = datos
            while len(self.cache) > 48:
                self.cache.popitem(last=False)
            return datos


# ---- Oído ----

class Oido:
    def __init__(self):
        self.candado = threading.Lock()
        self.modelo = None
        self.ultimo_uso = 0.0
        threading.Thread(target=self._vigilar, daemon=True).start()

    def disponible(self):
        try:
            return (MODELOS / configuracion()["oido"] / "model.bin").exists() and __import__("faster_whisper") is not None
        except ImportError:
            return False

    def _vigilar(self):
        while True:
            time.sleep(60)
            if self.modelo is not None and time.time() - self.ultimo_uso > configuracion()["descargar_oido_tras_s"]:
                with self.candado:
                    self.modelo = None   # devuelve la memoria al modelo de lenguaje

    @staticmethod
    def decodificar(datos):
        """Audio del navegador (webm/ogg/wav…) -> arreglo mono de 16 kHz, que es lo que lee Whisper."""
        import av
        import numpy as np
        trozos = []
        with av.open(io.BytesIO(datos)) as contenedor:
            remuestreo = av.AudioResampler(format="s16", layout="mono", rate=16000)
            for cuadro in contenedor.decode(contenedor.streams.audio[0]):
                trozos += [f.to_ndarray().reshape(-1) for f in remuestreo.resample(cuadro)]
            trozos += [f.to_ndarray().reshape(-1) for f in (remuestreo.resample(None) or [])]
        if not trozos:
            return np.zeros(0, dtype="float32")
        return np.concatenate(trozos).astype("float32") / 32768.0

    def transcribir(self, datos):
        """Texto dicho en el audio. Devuelve (texto, segundos de audio)."""
        audio = self.decodificar(datos)
        segundos = len(audio) / 16000
        if segundos < 0.4:
            return "", segundos
        # Si es casi silencio no se le pide nada a Whisper (inventa frases sobre el ruido).
        if float((audio ** 2).mean() ** 0.5) < 0.004:
            return "", segundos
        cfg = configuracion()
        with self.candado:
            if self.modelo is None:
                from faster_whisper import WhisperModel
                self.modelo = WhisperModel(str(MODELOS / cfg["oido"]), device="cpu", compute_type="int8", cpu_threads=3)
            self.ultimo_uso = time.time()
            trozos, _ = self.modelo.transcribe(
                audio, language="es", beam_size=1, vad_filter=True, condition_on_previous_text=False,
                initial_prompt=cfg["guia"], temperature=0.0, no_speech_threshold=0.6,
                vad_parameters={"min_silence_duration_ms": 400})
            texto = " ".join(t.text.strip() for t in trozos).strip()
            self.ultimo_uso = time.time()
        # Frases típicas que Whisper inventa con ruido o silencio
        if re.fullmatch(r"(gracias( por ver( el video)?)?|subtítulos.*|suscríbete.*|amara\.org.*|\.+)", texto.strip(" .!¡"), re.I):
            return "", segundos
        return texto, segundos


VOZ = Voz()
OIDO = Oido()


def estado():
    return {"voz": VOZ.disponible(), "oido": OIDO.disponible(), "modelo_voz": configuracion()["voz"].split("/")[-1]}
