import copy
import json
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ComfyUIError(RuntimeError):
    pass


class ComfyUIClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 5.0,
        max_wait_seconds: float = 900.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.max_wait_seconds = max_wait_seconds

    def healthcheck(self) -> Dict[str, Any]:
        return self._json_request("GET", "/system_stats")

    def upload_input(self, file_path: Path) -> str:
        if not file_path.exists():
            raise ComfyUIError(f"Reference file does not exist: {file_path}")
        boundary = f"----flashcutter-{uuid.uuid4().hex}"
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        body = self._multipart_body(
            boundary,
            fields={"overwrite": "true", "type": "input"},
            file_field="image",
            file_path=file_path,
            content_type=content_type,
        )
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        response = self._json_request("POST", "/upload/image", body=body, headers=headers)
        return str(response.get("name") or file_path.name)

    def submit_prompt(self, workflow_api_json: Dict[str, Any]) -> str:
        payload = {
            "client_id": f"flashcutter-{uuid.uuid4().hex}",
            "prompt": workflow_api_json,
        }
        response = self._json_request("POST", "/prompt", json_payload=payload)
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"ComfyUI did not return prompt_id: {response}")
        return str(prompt_id)

    def history(self, prompt_id: str) -> Dict[str, Any]:
        return self._json_request("GET", f"/history/{prompt_id}")

    def wait_for_output(self, prompt_id: str) -> Dict[str, str]:
        deadline = time.monotonic() + self.max_wait_seconds
        while time.monotonic() < deadline:
            history = self.history(prompt_id)
            prompt_history = history.get(prompt_id) or {}
            status = prompt_history.get("status") or {}
            if status.get("status_str") == "error":
                raise ComfyUIError(f"ComfyUI generation failed: {status}")
            output = first_video_output(prompt_history) or first_image_output(prompt_history)
            if output:
                return output
            time.sleep(self.poll_interval_seconds)
        raise ComfyUIError(f"ComfyUI generation timed out after {self.max_wait_seconds:.0f}s")

    def download_output(self, output: Dict[str, str], destination: Path) -> None:
        query = urlencode(
            {
                "filename": output["filename"],
                "subfolder": output.get("subfolder", ""),
                "type": output.get("type", "output"),
            }
        )
        data = self._bytes_request("GET", f"/view?{query}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)

    def _json_request(
        self,
        method: str,
        path: str,
        json_payload: Optional[Dict[str, Any]] = None,
        body: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        data = body
        request_headers = dict(headers or {})
        if json_payload is not None:
            data = json.dumps(json_payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        response_bytes = self._bytes_request(method, path, data=data, headers=request_headers)
        if not response_bytes:
            return {}
        return json.loads(response_bytes.decode("utf-8"))

    def _bytes_request(
        self,
        method: str,
        path: str,
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> bytes:
        request_headers = dict(headers or {})
        if self.api_key:
            request_headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read()
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise ComfyUIError(f"ComfyUI HTTP {exc.code}: {error_body}") from exc
        except URLError as exc:
            raise ComfyUIError(f"Cannot connect to ComfyUI: {exc.reason}") from exc

    def _multipart_body(
        self,
        boundary: str,
        fields: Dict[str, str],
        file_field: str,
        file_path: Path,
        content_type: str,
    ) -> bytes:
        chunks = []
        for name, value in fields.items():
            chunks.append(f"--{boundary}\r\n".encode("utf-8"))
            chunks.append(
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode(
                    "utf-8"
                )
            )
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{file_path.name}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
        )
        chunks.append(file_path.read_bytes())
        chunks.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
        return b"".join(chunks)


def workflow_with_bindings(
    workflow_api_json: Dict[str, Any],
    bindings: Dict[str, Iterable[Any]],
    values: Dict[str, Any],
) -> Dict[str, Any]:
    workflow = copy.deepcopy(workflow_api_json)
    for value_name, path in bindings.items():
        if value_name not in values:
            continue
        set_nested_value(workflow, list(path), values[value_name])
    return workflow


def set_nested_value(payload: Dict[str, Any], path: list[Any], value: Any) -> None:
    cursor: Any = payload
    for key in path[:-1]:
        cursor = cursor[str(key)] if isinstance(cursor, dict) else cursor[int(key)]
    last_key = path[-1]
    if isinstance(cursor, dict):
        cursor[str(last_key)] = value
    else:
        cursor[int(last_key)] = value


def first_video_output(prompt_history: Dict[str, Any]) -> Optional[Dict[str, str]]:
    for output in iter_outputs(prompt_history):
        videos = output.get("videos") or output.get("gifs") or []
        if videos:
            return normalize_output(videos[0])
    return None


def first_image_output(prompt_history: Dict[str, Any]) -> Optional[Dict[str, str]]:
    for output in iter_outputs(prompt_history):
        images = output.get("images") or []
        if images:
            return normalize_output(images[0])
    return None


def iter_outputs(prompt_history: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    outputs = prompt_history.get("outputs") or {}
    if isinstance(outputs, dict):
        return outputs.values()
    if isinstance(outputs, list):
        return outputs
    return []


def normalize_output(output: Dict[str, Any]) -> Dict[str, str]:
    return {
        "filename": str(output.get("filename") or ""),
        "subfolder": str(output.get("subfolder") or ""),
        "type": str(output.get("type") or "output"),
    }
