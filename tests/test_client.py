import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from pulse_sdk import PulseClient, PulseError


class ClientTest(unittest.TestCase):
    def test_wire_protocol_and_failure_boundaries(self):
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                seen.append(
                    (
                        self.command,
                        self.path,
                        self.headers.get("Authorization"),
                        json.loads(raw) if raw else None,
                    )
                )
                if self.path == "/api/v1/error":
                    self.send_response(503)
                    self.send_header("X-Request-ID", "request-123")
                    self.end_headers()
                    self.wfile.write(b"private response body")
                    return
                if self.path == "/api/v1/redirect":
                    self.send_response(307)
                    self.send_header("Location", "/api/v1/leak")
                    self.end_headers()
                    return
                self.send_response(204 if self.command == "DELETE" else 200)
                self.end_headers()
                if self.command != "DELETE":
                    payload = (
                        {"access_token": "test-session", "expires_in": 60}
                        if self.path == "/api/v1/auth/login"
                        else {"status": "pending_approval"}
                    )
                    self.wfile.write(json.dumps(payload).encode())

            do_POST = do_GET
            do_DELETE = do_GET
            do_PATCH = do_GET

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = PulseClient(f"http://127.0.0.1:{server.server_port}")
            self.assertEqual(
                client.login("guest@example.test", "test-only-password"),
                {"expires_in": 60},
            )
            client.list_tasks("project", search="Сайт & чат", archived=True)
            self.assertEqual(
                parse_qs(urlsplit(seen[-1][1]).query)["search"], ["Сайт & чат"]
            )
            self.assertEqual(seen[-1][2], "Bearer test-session")
            client.create_task("project", "Пример", priority="high")
            self.assertEqual(seen[-1][3]["title"], "Пример")
            self.assertIsNone(client.archive_task("a/b?"))
            self.assertEqual(seen[-1][1], "/api/v1/work/tasks/a%2Fb%3F")
            client.restore_task("task-one")
            self.assertEqual(seen[-1][0], "POST")
            count = len(seen)
            client.send_message("project", "session", "Создай задачу")
            self.assertEqual(len(seen), count + 1)
            with self.assertRaises(PulseError) as raised:
                client.request("POST", "/api/v1/error", {})
            self.assertEqual(raised.exception.status, 503)
            self.assertEqual(raised.exception.request_id, "request-123")
            self.assertNotIn("private", str(raised.exception))
            self.assertEqual(sum(r[1] == "/api/v1/error" for r in seen), 1)
            with self.assertRaises(PulseError):
                client.request("POST", "/api/v1/redirect", {})
            self.assertFalse(any(r[1] == "/api/v1/leak" for r in seen))
            for path in (
                "https://example.test/api/v1/me",
                "//example.test/api/v1/me",
                "/api/v1/../other",
            ):
                with self.assertRaises(ValueError):
                    client.request("GET", path)
            client.logout()
            client.me()
            self.assertIsNone(seen[-1][2])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
