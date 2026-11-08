"""No automatic retries: a failed response does not mean a write failed."""

import json
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class PulseError(Exception):
    """HTTP failure without response bodies or credentials in the message."""

    def __init__(self, status: int, request_id: str | None = None):
        self.status = status
        self.request_id = request_id
        super().__init__(f"Pulse API returned HTTP {status}")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _segment(value: str) -> str:
    if not value or value in (".", ".."):
        raise ValueError("An identifier is required")
    return quote(value, safe="")


def _ai(project_id: str) -> str:
    return f"/api/v1/projects/{_segment(project_id)}/ai"


class PulseClient:
    """Synchronous server client; timeout is the socket-operation limit in seconds."""

    def __init__(self, base_url: str, token: str = "", *, timeout: float = 60):
        url = urlsplit(base_url)
        if (
            not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in ("", "/")
        ):
            raise ValueError("base_url must be an origin without credentials or path")
        if url.scheme != "https" and not (
            url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1")
        ):
            raise ValueError("HTTPS is required except for loopback development")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._base = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._opener = build_opener(_NoRedirect())

    def set_token(self, token: str) -> None:
        self._token = token

    def request(self, method: str, path: str, body: Any = None) -> Any:
        if (
            not path.startswith("/api/v1/")
            or "\\" in path
            or any(p in (".", "..") for p in urlsplit(path).path.split("/"))
        ):
            raise ValueError("Only same-origin /api/v1/ paths are allowed")
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(self._base + path, data=data, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                raw = response.read()
                try:
                    return json.loads(raw) if raw else None
                except (ValueError, UnicodeError):
                    raise ValueError("Pulse API returned invalid JSON") from None
        except HTTPError as error:
            status, request_id = error.code, error.headers.get("X-Request-ID")
            error.close()
            raise PulseError(status, request_id) from None

    def login(self, email: str, password: str) -> dict[str, int]:
        result = self.request(
            "POST", "/api/v1/auth/login", {"email": email, "password": password}
        )
        self.set_token(result["access_token"])
        return {"expires_in": result["expires_in"]}

    def me(self) -> dict[str, Any]:
        return self.request("GET", "/api/v1/auth/me")

    def logout(self) -> None:
        self.request("POST", "/api/v1/auth/logout")
        self._token = ""

    def list_tasks(
        self,
        project_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
        search: str = "",
        archived: bool = False,
    ) -> dict[str, Any]:
        query = urlencode(
            {
                "project_id": project_id,
                "limit": limit,
                "offset": offset,
                "search": search,
                "archived": str(archived).lower(),
            }
        )
        return self.request("GET", f"/api/v1/work/tasks?{query}")

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/v1/work/tasks/{_segment(task_id)}")

    def create_task(self, project_id: str, title: str, **fields: Any) -> dict[str, Any]:
        return self.request(
            "POST",
            "/api/v1/work/tasks",
            {**fields, "project_id": project_id, "title": title},
        )

    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        return self.request("PATCH", f"/api/v1/work/tasks/{_segment(task_id)}", fields)

    def archive_task(self, task_id: str) -> Any:
        return self.request("DELETE", f"/api/v1/work/tasks/{_segment(task_id)}")

    def restore_task(self, task_id: str) -> dict[str, Any]:
        return self.request(
            "POST", f"/api/v1/work/tasks/{_segment(task_id)}/restore", {}
        )

    def create_session(self, project_id: str) -> dict[str, Any]:
        return self.request(
            "POST",
            f"{_ai(project_id)}/employee/sessions",
            {
                "screen_scope": "project",
                "screen_entity_type": "project",
                "screen_entity_id": project_id,
                "page_context_json": {"projectId": project_id},
            },
        )

    def get_session(self, project_id: str, session_id: str) -> dict[str, Any]:
        return self.request(
            "GET", f"{_ai(project_id)}/employee/sessions/{_segment(session_id)}"
        )

    def send_message(
        self, project_id: str, session_id: str, body: str, **context: Any
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            f"{_ai(project_id)}/employee/sessions/{_segment(session_id)}/messages",
            {**context, "body": body},
        )

    def edit_proposal(
        self,
        project_id: str,
        tool_call_id: str,
        input_json: dict[str, Any],
        reason: str = "Изменено пользователем через SDK",
    ) -> dict[str, Any]:
        return self.request(
            "PATCH",
            f"{_ai(project_id)}/tool-calls/{_segment(tool_call_id)}",
            {"input_json": input_json, "edit_reason": reason},
        )

    def approve_proposal(self, project_id: str, tool_call_id: str) -> dict[str, Any]:
        return self.request(
            "POST", f"{_ai(project_id)}/tool-calls/{_segment(tool_call_id)}/approve", {}
        )

    def reject_proposal(
        self,
        project_id: str,
        tool_call_id: str,
        reason: str = "Отклонено пользователем",
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            f"{_ai(project_id)}/tool-calls/{_segment(tool_call_id)}/reject",
            {"reason": reason},
        )
