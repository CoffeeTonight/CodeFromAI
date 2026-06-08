#!/usr/bin/env python3
"""
Simple development HTTP server that disables caching for HTML, JS, and JSON.
Usage: python dev_server.py [port] [directory]
"""
import http.server
import socketserver
import os
import sys
from datetime import datetime

# Enable address reuse so the dev server can restart quickly after being killed
# (prevents "OSError: [Errno 98] Address already in use")
socketserver.TCPServer.allow_reuse_address = True

class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Disable caching for development
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        # Add a small version header for debugging
        super().do_GET()

if __name__ == "__main__":
    port = 8000
    directory = "."

    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}")
            sys.exit(1)

    if len(sys.argv) > 2:
        directory = sys.argv[2]

    os.chdir(directory)

    with socketserver.TCPServer(("127.0.0.1", port), NoCacheHTTPRequestHandler) as httpd:
        print(f"Development server running at http://127.0.0.1:{port}/")
        print(f"Serving directory: {os.getcwd()}")
        print("Cache-Control: no-cache enabled for all responses.")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
