import socket as _socket
import threading
from time import sleep as _sleep

from ogn.client import AprsClient
from ogn.client.client import create_aprs_login

import db as _db
from core.beacon import parse_ogn_beacon
from core.config import APRS_PASS, APRS_USER
from core.emergency import get_config
from core.notify import notify
from core.state_machine import update_device
from core.terrain import compute_agl


class AuthAprsClient(AprsClient):
    def __init__(self, aprs_user: str, aprs_pass: int, aprs_filter: str = ""):
        super().__init__(aprs_user=aprs_user, aprs_filter=aprs_filter)
        self._aprs_pass = aprs_pass

    def connect(self, retries: int = 1, wait_period: int = 15, socket_timeout: int = 10):
        while retries > 0:
            retries -= 1
            try:
                self.sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                self.sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_KEEPALIVE, 1)
                self.sock.settimeout(socket_timeout)
                port = (self.settings.APRS_SERVER_PORT_CLIENT_DEFINED_FILTERS
                        if self.aprs_filter
                        else self.settings.APRS_SERVER_PORT_FULL_FEED)
                self.sock.connect((self.settings.APRS_SERVER_HOST, port))
                self._sock_peer_ip = self.sock.getpeername()[0]
                login = create_aprs_login(
                    self.aprs_user, self._aprs_pass,
                    self.settings.APRS_APP_NAME, self.settings.APRS_APP_VER,
                    self.aprs_filter,
                )
                self.sock.send(login.encode())
                self.sock_file = self.sock.makefile("rb")
                self.sock.settimeout(None)   # blocking after login
                self._kill = False
                break
            except (_socket.error, ConnectionError) as e:
                print(f"  [OGN] {type(e).__name__}: {e}")
                if retries > 0:
                    print(f"  [OGN] Retry in {wait_period}s ({retries} left)...")
                    _sleep(wait_period)
                else:
                    print("  [OGN] Connection failed.")
                    self._kill = True


def ogn_thread(devices: dict, stop_flag, reconnect_event) -> None:
    _pkt_count = [0]

    def on_raw(raw: str):
        if not raw or raw.startswith("#"):
            return
        _pkt_count[0] += 1
        if _pkt_count[0] % 50 == 0:
            print(f"  [OGN][diag] {_pkt_count[0]} pacchetti ricevuti dal server")
        beacon = parse_ogn_beacon(raw)
        if beacon is None:
            return
        beacon.agl_m = compute_agl(beacon)
        dev = devices.get(beacon.device_id)
        if dev is None:
            return
        _db.write_beacon(beacon)
        events = update_device(dev, beacon, get_config())
        _db.set_device_state(beacon.name, dev.state.name)
        if events:
            notify(events)
        else:
            print(f"[{beacon.ts.strftime('%H:%M:%S')}][OGN] {beacon.name}: "
                  f"alt={beacon.alt_m:.0f}m  speed={beacon.speed_kmh:.0f}km/h  "
                  f"vspeed={beacon.vspeed_ms:+.1f}m/s  {dev.state.name}")

    while not stop_flag.is_set():
        reconnect_event.clear()

        ogn_keys   = sorted(k for k in devices if not k.startswith(("PT_", "GS_")))
        ogn_filter = ("b/" + "/".join(ogn_keys)) if ogn_keys else ""

        client = AuthAprsClient(aprs_user=APRS_USER, aprs_pass=APRS_PASS, aprs_filter=ogn_filter)
        client.connect()

        if client._kill:
            print("  [OGN] connection failed — retry in 60s")
            stop_flag.wait(60)
            continue

        print(f"  [OGN] connected — filter: {ogn_filter}")

        def stopper(c=client):
            while not stop_flag.is_set() and not reconnect_event.is_set():
                stop_flag.wait(2)
            try:
                c.disconnect()
            except Exception:
                pass

        threading.Thread(target=stopper, daemon=True).start()

        try:
            client.run(callback=on_raw, autoreconnect=False)
        except Exception as e:
            print(f"  [OGN] disconnected: {e}")

        if reconnect_event.is_set():
            print("  [OGN] filter aggiornato — riconnessione...")
            continue

        if not stop_flag.is_set():
            print("  [OGN] reconnecting in 10s...")
            stop_flag.wait(10)
