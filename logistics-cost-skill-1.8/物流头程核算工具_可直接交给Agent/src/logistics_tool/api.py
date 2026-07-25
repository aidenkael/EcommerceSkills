from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .service import EstimatorService


class ApiHandler(BaseHTTPRequestHandler):
    service: EstimatorService

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path == "/health":
            self._json(200, {"ok": True, "service": "logistics-estimator", "calibration_records": len(self.service.calibration.records)})
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._body()
            if path == "/v1/estimate":
                analysis = body.get("analysis", body)
                result = self.service.estimate_analysis(
                    analysis,
                    tail_cost_rmb=body.get("tail_cost_rmb"),
                    other_fixed_cost_rmb=body.get("other_fixed_cost_rmb"),
                )
                self._json(200, result)
                return
            if path == "/v1/estimate-image":
                image_path = Path(body["image_path"])
                if not image_path.is_absolute():
                    image_path = self.service.root / image_path
                result = self.service.estimate_image(image_path, provider=body.get("provider", "auto"))
                self._json(200, result)
                return
            if path == "/v1/feedback":
                self.service.add_feedback(body)
                self._json(201, {"ok": True})
                return
            self._json(404, {"error": "not_found"})
        except Exception as exc:
            self._json(400, {"error": type(exc).__name__, "message": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        print("API", self.address_string(), fmt % args)


def serve(root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    service = EstimatorService(root)
    handler = type("BoundApiHandler", (ApiHandler,), {"service": service})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"物流核算 API 已启动: http://{host}:{port}")
    print("健康检查: GET /health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
