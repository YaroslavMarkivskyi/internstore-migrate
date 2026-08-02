import http.server
import socketserver

VIDEO_PATH = "/app/video.mp4"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        # Same fixed .mp4 on any path — Security builds distinct
        # /video/{visit_log_id}.mp4 URLs, but there's only ever one file
        # behind them in dev. A real ESP32-CAM replaces this whole
        # container in prod.
        with open(VIDEO_PATH, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}", flush=True)


if __name__ == "__main__":
    with socketserver.TCPServer(("0.0.0.0", 8001), Handler) as httpd:
        httpd.serve_forever()
