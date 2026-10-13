"""The status page for Winnow Gateways.

Serves one page on port 8480. For each gateway it asks that gateway's
tailscaled, over its socket, for the tailnet state and the serve config (both
read-only LocalAPI calls), and sends a SOCKS5 greeting to the proxy behind it.
Nothing is cached: every load asks again.
"""

import datetime
import html
import http.client
import http.server
import json
import os
import socket

# label, the name Winnow resolves, SOCKS port, tailscaled socket, upstream
GATEWAYS = [
    ("Tor", "winnow-tor-gateway", 9050, "/run/tor/tailscaled.sock",
     os.environ.get("TOR_UPSTREAM", "10.21.21.11:9050")),
    ("I2P", "winnow-i2p-gateway", 4447, "/run/i2p/tailscaled.sock",
     os.environ.get("I2P_UPSTREAM", "winnow-gateways_i2pd_1:4447")),
]
SETTINGS = "App settings → Advanced → Environment variables"


class LocalAPI(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("local-tailscaled.sock", timeout=3)
        self.socket_path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(3)
        self.sock.connect(self.socket_path)


def local_api(path, endpoint):
    connection = LocalAPI(path)
    try:
        connection.request("GET", f"/localapi/v0/{endpoint}")
        response = connection.getresponse()
        body = response.read()
        if response.status != 200:
            raise RuntimeError(f"{endpoint} answered HTTP {response.status}")
        return json.loads(body or b"null")
    finally:
        connection.close()


def answers_socks(address):
    host, _, port = address.rpartition(":")
    try:
        with socket.create_connection((host, int(port)), timeout=3) as sock:
            sock.sendall(b"\x05\x01\x00")
            return sock.recv(2) == b"\x05\x00"
    except OSError:
        return False


def check(label, name, port, path, upstream):
    """Returns (facts, problems) for one gateway."""
    facts, problems = {"Gateway": label}, []
    try:
        status = local_api(path, "status")
    except Exception as error:
        facts["Tailnet"] = "not answering"
        problems.append(f"Its tailscaled does not answer ({error}). See the app's logs.")
        status = None
    if status:
        state = status.get("BackendState", "unknown")
        me = status.get("Self") or {}
        facts["Tailnet"] = state
        if state == "NeedsLogin":
            problems.append(f"Not logged in. Enter a Tailscale auth key as TS_AUTHKEY in {SETTINGS}.")
        for message in status.get("Health") or []:
            problems.append(message)
        if state == "Running":
            joined = (me.get("DNSName") or "").split(".")[0]
            facts["Name"] = joined
            facts["Address"] = next((ip for ip in me.get("TailscaleIPs") or [] if "." in ip), "")
            if joined != name:
                problems.append(
                    f"Joined as {joined}, because another machine holds {name}, so Winnow "
                    "will not find this one. Delete or rename that machine in the Tailscale "
                    "admin console, then restart this app.")
            expiry = me.get("KeyExpiry")
            facts["Key expiry"] = expiry[:10] if expiry else "none"
            if expiry:
                problems.append(
                    f"Its key expires on {expiry[:10]}, and the gateway drops off the tailnet "
                    "then. Use a tagged auth key, or turn off key expiry for this machine in "
                    "the Tailscale admin console.")
            try:
                serve = local_api(path, "serve-config") or {}
                forwarded = str(port) in (serve.get("TCP") or {})
            except Exception:
                forwarded = False
            facts["Port"] = f"{port} {'forwarded' if forwarded else 'not forwarded'}"
            if not forwarded:
                problems.append(f"Port {port} is not forwarded. Restart the app.")
    upstream_ok = answers_socks(upstream)
    facts["Proxy behind it"] = f"{upstream} {'answers' if upstream_ok else 'does not answer'}"
    if not upstream_ok:
        problems.append(f"The proxy behind it, {upstream}, does not answer SOCKS5. "
                        "A router that has just started can take a few minutes.")
    return facts, problems


def page():
    sections = []
    for gateway in GATEWAYS:
        facts, problems = check(*gateway)
        rows = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(str(v))}</td></tr>"
                       for k, v in facts.items())
        notes = "".join(f"<li>{html.escape(p)}</li>" for p in problems)
        verdict = "ready" if not problems else "needs attention"
        sections.append(f"<section><h2>{html.escape(facts['Gateway'])}: {verdict}</h2>"
                        f"<table>{rows}</table>{f'<ul>{notes}</ul>' if notes else ''}</section>")
    checked = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>Winnow Gateways</title>
<style>
:root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
body {{ max-width: 40rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
th {{ text-align: left; padding-right: 1rem; font-weight: 500; opacity: .7; }}
ul {{ padding-left: 1.2rem; }}
section {{ margin-bottom: 2rem; }}
</style></head><body>
<h1>Winnow Gateways</h1>
<p>Winnow on Automatic peer routing looks for winnow-tor-gateway:9050 and
winnow-i2p-gateway:4447 on your tailnet. Checked {checked}; this page reloads
every 30 seconds.</p>
{''.join(sections)}
</body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = page().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(("0.0.0.0", 8480), Handler).serve_forever()
