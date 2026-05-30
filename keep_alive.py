"""
Tiny HTTP server that keeps the Render free-tier web service awake.
UptimeRobot pings the / endpoint every 5 minutes to prevent sleep.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import threading


class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"OK"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()

    # Suppress request logs cluttering the console
    def log_message(self, format, *args):
        pass


def keep_alive():
    server = HTTPServer(("0.0.0.0", 8080), PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print("[Keep-Alive] HTTP server running on port 8080", flush=True)
