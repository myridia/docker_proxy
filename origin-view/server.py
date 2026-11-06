#!/usr/bin/env python3
import argparse
import hashlib
import ipaddress
import json
import socket
import ssl
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 65536
PREVIEW = 200


def normalize_ip(value):
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return value
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        return str(addr.ipv4_mapped)
    return str(addr)


def is_private(value):
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return False
    return addr.is_private or addr.is_loopback or addr.is_link_local


def reverse_name(value):
    try:
        return socket.gethostbyaddr(value)[0]
    except OSError:
        return None


def tls_details(conn):
    if not isinstance(conn, ssl.SSLSocket):
        return None
    cipher = conn.cipher() or ("", "", 0)
    return {
        "version": conn.version(),
        "cipher": cipher[0],
        "bits": cipher[2],
        "alpn": conn.selected_alpn_protocol(),
        "sni": getattr(conn, "_sni", None),
    }


def build_notes(peer_ip, target, headers, tls):
    names = {name.lower(): value for name, value in headers}
    notes = []
    if target.startswith(("http://", "https://")):
        notes.append("absolute-form target: the client has an explicit HTTP proxy configured")
    else:
        notes.append("origin-form target: no HTTP proxy on the client, consistent with a transparent redirect")
    if "proxy-connection" in names or "proxy-authorization" in names:
        notes.append("Proxy-* header present: a client-side proxy is in the chain")
    if "x-forwarded-for" in names:
        notes.append("X-Forwarded-For present: an upstream hop records the client address")
    if "via" in names:
        notes.append("Via present: an explicit proxy identifies itself")
    if "user-agent" not in names:
        notes.append("no User-Agent header")
    if is_private(peer_ip):
        notes.append("peer address is private/loopback: the request did not leave the local network")
    else:
        notes.append("peer address is public: this is the exit IP the target sees")
    if tls:
        notes.append(f"TLS {tls['version']} with {tls['cipher']}")
    return notes


def format_text(record):
    lines = [f"{record['time']} #{record['id']} {record['request_line']}"]
    peer = f"{record['peer_ip']}:{record['peer_port']}"
    if record.get("peer_host"):
        peer += f"  ({record['peer_host']})"
    lines.append(f"  peer      {peer}")
    tls = record.get("tls")
    if tls:
        parts = [tls.get("version"), tls.get("cipher")]
        if tls.get("alpn"):
            parts.append(f"ALPN={tls['alpn']}")
        if tls.get("sni"):
            parts.append(f"SNI={tls['sni']}")
        lines.append("  tls       " + "  ".join(part for part in parts if part))
    lines.append("  headers")
    for name, value in record["headers"]:
        lines.append(f"    {name}: {value}")
    if record["body_bytes"]:
        lines.append(f"  body      {record['body_bytes']} bytes sha256={record['body_sha256']}")
        if record["body_preview"]:
            lines.append(f"    {record['body_preview']}")
    lines.append("  notes")
    for note in record["notes"]:
        lines.append(f"    - {note}")
    return "\n".join(lines)


class Counter:
    def __init__(self):
        self._lock = threading.Lock()
        self._value = 0

    def next(self):
        with self._lock:
            self._value += 1
            return self._value


COUNTER = Counter()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "origin-view"
    sys_version = ""

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        self.respond()

    def do_HEAD(self):
        self.respond()

    def do_POST(self):
        self.respond()

    def do_PUT(self):
        self.respond()

    def do_DELETE(self):
        self.respond()

    def do_PATCH(self):
        self.respond()

    def do_OPTIONS(self):
        self.respond()

    def respond(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self.close_connection = True
        body = self.rfile.read(min(length, MAX_BODY)) if length > 0 else b""
        peer_ip = normalize_ip(self.client_address[0])
        peer_port = self.client_address[1]
        headers = list(self.headers.items())
        tls = tls_details(self.connection)
        record = {
            "id": COUNTER.next(),
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "request_line": self.requestline,
            "method": self.command,
            "target": self.path,
            "http_version": self.request_version,
            "peer_ip": peer_ip,
            "peer_port": peer_port,
            "peer_host": reverse_name(peer_ip) if self.server.ptr else None,
            "headers": headers,
            "tls": tls,
            "body_bytes": len(body),
            "body_sha256": hashlib.sha256(body).hexdigest() if body else None,
            "body_preview": body[:PREVIEW].decode("utf-8", "replace") if body else None,
            "notes": build_notes(peer_ip, self.path, headers, tls),
        }
        print(format_text(record), flush=True)
        wants_json = (
            self.path.split("?", 1)[0].rstrip("/") == "/json"
            or "format=json" in self.path
        )
        if wants_json:
            payload = json.dumps(record, indent=2, ensure_ascii=False).encode()
            content_type = "application/json"
        else:
            payload = format_text(record).encode()
            content_type = "text/plain; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)


def remember_sni(ssl_socket, server_name, ssl_context):
    ssl_socket._sni = server_name
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Print what a target server sees about a proxied client."
    )
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--ptr", action="store_true", help="reverse-resolve the peer address")
    parser.add_argument("--tls-cert")
    parser.add_argument("--tls-key")
    args = parser.parse_args()
    if bool(args.tls_cert) != bool(args.tls_key):
        parser.error("--tls-cert and --tls-key must be given together")

    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.ptr = args.ptr
    scheme = "http"
    if args.tls_cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.tls_cert, args.tls_key)
        context.set_alpn_protocols(["http/1.1"])
        context.sni_callback = remember_sni
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"

    print(f"origin-view listening on {scheme}://{args.bind}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
