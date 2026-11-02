from http.client import HTTPConnection
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import sys
from urllib.parse import urlsplit


class VelaHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if urlsplit(self.path).path.startswith("/v1/"):
            self.proxy_tts()
            return
        self.send_error(404)

    def proxy_tts(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        upstream = HTTPConnection("127.0.0.1", 8882, timeout=120)
        try:
            upstream.request("POST", self.path, body=body, headers={
                "Content-Type": self.headers.get("Content-Type", "application/json"),
                "Accept": self.headers.get("Accept", "*/*"),
            })
            response = upstream.getresponse()
            payload = response.read()
            self.send_response(response.status, response.reason)
            self.send_header("Content-Type", response.getheader("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
        except Exception as error:
            message = ("HeadTTS proxy error: " + str(error)).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)
        finally:
            upstream.close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4174
    ThreadingHTTPServer(("0.0.0.0", port), VelaHandler).serve_forever()
