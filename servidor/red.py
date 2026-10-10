"""El cerebro de red de M-Jarvis: sabe en qué situación de red está y se acomoda solo, en este orden:

  1. NUBE    — hay una Wi-Fi conocida con internet de verdad. Lo mejor: todo disponible (también la nube, si algún día se usa).
  2. PUENTE  — no hay Wi-Fi, pero el cable da internet (otra laptop compartiendo, un router…).
  3. LOCAL   — no hay nada de eso: M-Jarvis crea su propia Wi-Fi («M-Jarvis») y ofrece su interfaz por cable.
               Cualquier equipo que se conecte (Wi-Fi o cable) cae en el portal cautivo y se abre el chat.

Además cuenta lo que hace (un registro de eventos que se ve en la pantalla de conexión) y deja que el dueño
fuerce un modo. Todo con NetworkManager (nmcli, con sudo sin contraseña: el servicio corre como el dueño).
"""
import json
import re
import subprocess
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / "red.json"
PERFIL_WIFI_PROPIA = "mjarvis-wifi"
PERFILES_CABLE = {"puente-internet": "cliente", "ofrecer-interfaz": "servidor", "mjarvis-cable": "enlace-local"}
REDES_PORTAL = ("10.42.0.", "10.44.0.")      # la de la Wi-Fi propia y la del cable que ofrece la interfaz
GRACIA_ARRANQUE = 90        # segundos tras encender el equipo antes de dar por perdida la red
GRACIA_PERDIDA = 75         # segundos sin Wi-Fi ni puente antes de pasar a modo local
CADA = 15                   # cada cuánto se revisa
REINTENTO_ARRIBA = 300      # en modo local, cada cuánto se intenta volver a una red mejor (si no hay nadie conectado)

TEXTO_MODO = {
    "nube": "Hay internet por Wi-Fi: todo disponible.",
    "puente": "Sin Wi-Fi, pero hay internet por el cable (puente).",
    "lan": "Hay red pero sin internet: M-Jarvis funciona, solo para esa red.",
    "local": "Sin redes: M-Jarvis creó la suya y ofrece su interfaz.",
    "buscando": "Buscando redes…",
}


def _ejecutar(orden, tiempo=12, sudo=False):
    try:
        r = subprocess.run((["sudo", "-n"] if sudo else []) + orden, capture_output=True, text=True, timeout=tiempo)
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def _nm(*args, tiempo=20):
    return _ejecutar(["nmcli", *args], tiempo=tiempo, sudo=True)


class Red:
    def __init__(self):
        self.candado = threading.Lock()
        datos = {}
        try:
            datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        self.modo = datos.get("modo", "buscando")
        self.desde = time.time()
        self.eventos = datos.get("eventos", [])[-40:]
        self.sin_red_desde = None          # cuándo dejó de haber Wi-Fi o puente con internet
        self.manual = None                 # modo forzado por el dueño: ("local"|"nube"…, hasta cuándo)
        self.ultimo_intento_arriba = time.time()
        self.hotspot_pedido = 0.0          # cuándo la encendió el dueño a propósito: no se apaga sola durante un buen rato
        self.tarjeta = None
        self.cable = None
        self.cache = (0, None)

    # ---------- registro ----------
    def anotar(self, texto):
        self.eventos.append({"hora": time.strftime("%H:%M:%S"), "texto": texto})
        self.eventos = self.eventos[-40:]
        self._guardar()

    def _guardar(self):
        try:
            ARCHIVO.write_text(json.dumps({"modo": self.modo, "eventos": self.eventos}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    # ---------- lectura del entorno ----------
    def _dispositivos(self):
        _, salida = _ejecutar(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev"])
        filas = [l.split(":") for l in salida.splitlines()]
        wifi = next((f for f in filas if len(f) >= 4 and f[1] == "wifi"), None)
        eth = next((f for f in filas if len(f) >= 4 and f[1] == "ethernet"), None)
        self.tarjeta = wifi[0] if wifi else None
        self.cable = eth[0] if eth else None
        return wifi, eth

    @staticmethod
    def _ip(interfaz):
        if not interfaz:
            return ""
        _, s = _ejecutar(["ip", "-4", "-o", "addr", "show", "dev", interfaz])
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", s)
        return m.group(1) if m else ""

    @staticmethod
    def internet(interfaz):
        """'si' (internet de verdad), 'portal' (la red pide iniciar sesión) o 'no'."""
        if not interfaz:
            return "no"
        codigo, s = _ejecutar(["curl", "-s", "-m", "4", "--interface", interfaz, "-o", "/dev/null", "-w", "%{http_code}",
                               "http://clients3.google.com/generate_204"], tiempo=7)
        if s == "204":
            return "si"
        if s in ("200", "301", "302", "303", "307"):
            return "portal"
        codigo, _ = _ejecutar(["ping", "-I", interfaz, "-c", "1", "-W", "2", "1.1.1.1"], tiempo=5)
        return "si" if codigo == 0 else "no"

    def _perfil_activo(self, interfaz):
        _, s = _ejecutar(["nmcli", "-t", "-f", "GENERAL.CONNECTION", "dev", "show", interfaz]) if interfaz else (1, "")
        return s.split(":", 1)[1].strip() if ":" in s else ""

    def _clientes(self):
        """Equipos conectados a la red de M-Jarvis (Wi-Fi propia o cable), con su nombre si lo dieron al pedir dirección."""
        nombres = {}
        _, leases = _ejecutar(["sh", "-c", "cat /var/lib/NetworkManager/dnsmasq-*.leases 2>/dev/null"], sudo=True)
        for linea in leases.splitlines():
            p = linea.split()
            if len(p) >= 4:
                nombres[p[2]] = "" if p[3] == "*" else p[3]
        _, vecinos = _ejecutar(["ip", "-4", "neigh", "show"])
        salida = []
        for l in vecinos.splitlines():
            p = l.split()
            if not p or not p[0].startswith(REDES_PORTAL) or p[-1] not in ("REACHABLE", "STALE", "DELAY", "PROBE"):
                continue
            via = "Wi-Fi de M-Jarvis" if p[0].startswith("10.42.0.") else "cable"
            salida.append({"ip": p[0], "mac": p[4] if len(p) > 4 else "", "nombre": nombres.get(p[0], ""), "via": via})
        return salida

    # ---------- foto completa (para la pantalla de conexión) ----------
    def estado(self, fresco=False):
        if not fresco and time.time() - self.cache[0] < 4 and self.cache[1]:
            return self.cache[1]
        wifi, eth = self._dispositivos()
        perfil_wifi = self._perfil_activo(self.tarjeta)
        hotspot_activo = perfil_wifi == PERFIL_WIFI_PROPIA
        wifi_conectado = bool(wifi) and wifi[2] == "connected" and not hotspot_activo
        ip_wifi = self._ip(self.tarjeta)
        _, existe = _ejecutar(["nmcli", "-t", "-f", "NAME", "con", "show"])
        hotspot_existe = PERFIL_WIFI_PROPIA in existe.splitlines()
        perfil_cable = self._perfil_activo(self.cable)
        rol = PERFILES_CABLE.get(perfil_cable, "ninguno")
        enchufado = False
        try:
            enchufado = Path(f"/sys/class/net/{self.cable}/carrier").read_text().strip() == "1"
        except OSError:
            pass
        ip_cable = self._ip(self.cable) if rol != "ninguno" else ""
        # Solo hay clientes si esta máquina reparte red (Wi-Fi propia o cable ofrecido): si no, no se lee nada (cada lectura lanza un sudo).
        clientes = self._clientes() if (hotspot_activo or rol in ("servidor", "enlace-local")) else []
        direcciones = []
        if hotspot_activo and ip_wifi:
            direcciones.append({"para": "Celulares y computadoras conectados a la Wi-Fi «M-Jarvis»", "url": f"http://{ip_wifi}:8080/"})
        elif wifi_conectado and ip_wifi:
            direcciones.append({"para": "Equipos en la misma Wi-Fi", "url": f"http://{ip_wifi}:8080/"})
        if ip_cable and rol in ("servidor", "cliente", "enlace-local"):
            direcciones.append({"para": {"servidor": "Computadora conectada por cable", "cliente": "Computadora del puente", "enlace-local": "Cable directo"}[rol],
                                "url": f"http://{ip_cable}:8080/"})
        e = {
            "modo": self.modo, "modo_texto": TEXTO_MODO.get(self.modo, ""), "desde": int(self.desde),
            "wifi": {"hay_tarjeta": bool(self.tarjeta), "conectado": wifi_conectado, "red": perfil_wifi if wifi_conectado else "", "ip": ip_wifi if wifi_conectado else ""},
            "hotspot": {"existe": hotspot_existe, "activa": hotspot_activo, "nombre": "M-Jarvis", "ip": ip_wifi if hotspot_activo else ""},
            "cable": {"enchufado": enchufado, "rol": rol, "perfil": perfil_cable, "ip": ip_cable},
            "clientes": clientes, "direcciones": direcciones, "manual": bool(self.manual and self.manual[1] > time.time()),
            "eventos": self.eventos[-14:][::-1],
        }
        self.cache = (time.time(), e)
        return e

    # ---------- acciones ----------
    def volver_a_wifi(self):
        """Apaga la Wi-Fi propia y se une a la última Wi-Fi conocida. Se nombra el perfil: `nmcli device connect`
        elegía otra vez la propia, porque mientras hace de punto de acceso la lista de redes visibles está vieja."""
        _nm("con", "down", PERFIL_WIFI_PROPIA)
        if self.tarjeta:
            _nm("dev", "wifi", "rescan", "ifname", self.tarjeta, tiempo=15)
        time.sleep(4)
        _, lista = _nm("-t", "-f", "NAME,TYPE,TIMESTAMP", "con", "show")
        conocidas = sorted((l.rsplit(":", 2) for l in lista.splitlines() if ":802-11-wireless:" in l), key=lambda x: -int(x[2] or 0))
        for nombre, _, _ in conocidas:
            if nombre != PERFIL_WIFI_PROPIA and _nm("con", "up", nombre, tiempo=30)[0] == 0:
                return nombre
        return None

    def hotspot(self, encender, a_proposito=True):
        if encender:
            if a_proposito:
                self.hotspot_pedido = time.time()
            codigo, _ = _nm("con", "up", PERFIL_WIFI_PROPIA, tiempo=40)
            self.anotar("Encendí la Wi-Fi «M-Jarvis»." if codigo == 0 else "No pude encender la Wi-Fi «M-Jarvis» (¿está creada con su contraseña?).")
        else:
            red_unida = self.volver_a_wifi()
            self.anotar(f"Apagué la Wi-Fi «M-Jarvis» y me uní a {red_unida}." if red_unida else "Apagué la Wi-Fi «M-Jarvis»; no encontré ninguna Wi-Fi conocida a la vista.")
        self.cache = (0, None)

    def cable_modo(self, modo):
        if not self.cable:
            return
        destino = {"cliente": "puente-internet", "servidor": "ofrecer-interfaz", "auto": None}.get(modo)
        if destino:
            _nm("con", "up", destino, "ifname", self.cable, tiempo=30)
            self.anotar(f"Puse el cable en modo «{modo}».")
        else:
            _nm("dev", "disconnect", self.cable)
            _nm("dev", "connect", self.cable, tiempo=60)
            self.anotar("Dejé el cable en automático: primero intenta el puente y, si nadie le da red, ofrece su interfaz.")
        self.cache = (0, None)

    def forzar(self, modo, minutos=30):
        """El dueño manda: 'nube'/'puente' no se pueden forzar (dependen de lo que haya); 'local' sí; 'auto' devuelve el control."""
        if modo == "auto":
            self.manual = None
            self.anotar("Volví al modo automático.")
        elif modo == "local":
            self.manual = ("local", time.time() + minutos * 60)
            self.anotar("Modo local forzado: M-Jarvis usa solo su propia red.")
            self.hotspot(True)
        self.cache = (0, None)

    # ---------- el ciclo de decisión ----------
    def _cambiar(self, modo, motivo):
        if modo != self.modo:
            self.anotar(f"{TEXTO_MODO[modo]} {motivo}".strip())
            self.modo, self.desde = modo, time.time()
            self._guardar()

    def evaluar(self):
        with self.candado:
            e = self.estado(fresco=True)
            ahora = time.time()
            if self.manual and self.manual[1] > ahora:
                return
            self.manual = None
            hotspot_activa = e["hotspot"]["activa"]
            # 1. Wi-Fi con internet
            if e["wifi"]["conectado"]:
                net = self.internet(self.tarjeta)
                if net == "si":
                    self.sin_red_desde = None
                    self._cambiar("nube", f"Red: {e['wifi']['red']}.")
                    return
                lan_con_wifi = True
            else:
                lan_con_wifi = False
            # 2. Puente por cable (cliente) con internet
            if e["cable"]["rol"] == "cliente" and e["cable"]["ip"]:
                if self.internet(self.cable) == "si":
                    self.sin_red_desde = None
                    self._cambiar("puente", f"Por el cable ({e['cable']['ip']}).")
                    self._volver_arriba(e)
                    return
            # Ni Wi-Fi ni puente con internet
            if self.sin_red_desde is None:
                self.sin_red_desde = ahora
            arranque = _segundos_encendida()
            gracia = max(GRACIA_PERDIDA - (ahora - self.sin_red_desde), 0)
            if arranque < GRACIA_ARRANQUE:
                gracia = max(gracia, GRACIA_ARRANQUE - arranque)
            if lan_con_wifi:
                self._cambiar("lan", f"Conectada a {e['wifi']['red']} pero sin internet.")
                return
            if gracia > 0:
                if self.modo not in ("local", "lan"):
                    self._cambiar("buscando", "")
                return
            # 3. Local: su propia red
            if e["hotspot"]["existe"] and not hotspot_activa:
                self.hotspot(True, a_proposito=False)
            self._cambiar("local", "" if e["hotspot"]["existe"] else "La Wi-Fi propia aún no está creada (falta su contraseña).")
            self._volver_arriba(e)

    def _volver_arriba(self, e):
        """Con la Wi-Fi propia encendida y nadie conectado, cada tanto mira si ya volvió una red mejor.
        No lo hace si el cable da internet (modo puente): ahí la Wi-Fi propia y el internet conviven, que es lo que
        se quiere en una exhibición con celulares, y apagarla para buscar otra Wi-Fi solo los dejaría sin red."""
        ahora = time.time()
        if not e["hotspot"]["activa"] or e["clientes"] or ahora - self.ultimo_intento_arriba < REINTENTO_ARRIBA:
            return
        if self.modo == "puente":                   # el cable da internet: la Wi-Fi propia se queda mientras tanto
            return
        if ahora - self.hotspot_pedido < 3600:      # la encendió el dueño: se respeta una hora
            return
        self.ultimo_intento_arriba = ahora
        self.anotar("Nadie está conectado: miro si volvió alguna Wi-Fi conocida…")
        self.volver_a_wifi()
        time.sleep(8)
        if self.estado(fresco=True)["wifi"]["conectado"] and self.internet(self.tarjeta) == "si":
            self.sin_red_desde = None
            self._cambiar("nube", "Volvió una Wi-Fi con internet.")
        else:
            self.anotar("Sigue sin haber una Wi-Fi: vuelvo a mi propia red.")
            _nm("con", "up", PERFIL_WIFI_PROPIA, tiempo=40)

    def bucle(self):
        time.sleep(20)
        while True:
            try:
                self.evaluar()
            except Exception as error:   # el cerebro de red nunca debe tumbar el servidor
                self.anotar(f"Error al revisar la red: {type(error).__name__}")
            time.sleep(CADA)


def _segundos_encendida():
    try:
        return float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError):
        return 9999.0


RED = Red()


def iniciar():
    threading.Thread(target=RED.bucle, daemon=True).start()
