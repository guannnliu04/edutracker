"""本機開發/測試:同一支 api/index.py 加上 public/ 靜態檔。用法:python dev_server.py 8765"""
import sys
from http.server import ThreadingHTTPServer
from api.index import handler as api_handler


class Dev(api_handler):
    def do_GET(self):
        if self.path.startswith("/api/"): return super().do_GET()
        import mimetypes, pathlib
        p = self.path.split("?")[0]; p = "/index.html" if p == "/" else p
        f = pathlib.Path("public") / p.lstrip("/")
        if not f.is_file(): self.send_response(404); self.end_headers(); return
        b = f.read_bytes(); self.send_response(200); self.send_header("Content-Type", mimetypes.guess_type(str(f))[0] or "application/octet-stream"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"http://localhost:{port}", flush=True); ThreadingHTTPServer(("0.0.0.0", port), Dev).serve_forever()
