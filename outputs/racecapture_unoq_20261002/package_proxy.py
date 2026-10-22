"""Temporary localhost-only package downloader for an offline USB-connected UNO Q."""
import http.server
import urllib.request
import urllib.parse

class Proxy(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        if u.hostname not in ('deb.debian.org', 'security.debian.org', 'apt-repo.arduino.cc'):
            self.send_error(403)
            return
        try:
            with urllib.request.urlopen(self.path, timeout=60) as r:
                self.send_response(r.status)
                for k in ('Content-Length', 'Content-Type', 'Last-Modified'):
                    if r.headers.get(k): self.send_header(k, r.headers[k])
                self.end_headers()
                while data := r.read(262144): self.wfile.write(data)
        except Exception as e:
            self.send_error(502, str(e))

http.server.ThreadingHTTPServer(('127.0.0.1', 18765), Proxy).serve_forever()
