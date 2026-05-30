"""
Tiny HTTP server that keeps the Render free-tier web service awake.
UptimeRobot pings the / endpoint every 5 minutes to prevent sleep.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import threading


class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"FTSL Bot is alive.")

    # Suppress default request logs cluttering the console
    def log_message(self, format, *args):
        pass


def keep_alive():
    server = HTTPServer(("0.0.0.0", 8080), PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print("[Keep-Alive] HTTP server running on port 8080")
