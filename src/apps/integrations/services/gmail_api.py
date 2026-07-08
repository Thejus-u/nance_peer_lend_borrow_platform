from __future__ import annotations

import base64
import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib import parse, request

from django.conf import settings


class GmailAPIError(Exception):
    """Raised when Gmail API communication fails."""


class GmailAPIService:
    @classmethod
    def list_messages(cls, *, access_token: str, max_results: int, query: str | None) -> list[dict[str, str]]:
        params = {"maxResults": str(max(1, min(max_results, 200)))}
        if query:
            params["q"] = query

        endpoint = f"{settings.GMAIL_MESSAGES_LIST_URL}?{parse.urlencode(params)}"
        response = cls._http_get_json(endpoint, access_token=access_token)
        return response.get("messages", [])

    @classmethod
    def fetch_message(cls, *, access_token: str, message_id: str) -> dict:
        endpoint = (
            f"{settings.GMAIL_MESSAGES_GET_URL}/{message_id}"
            "?format=full&metadataHeaders=Subject&metadataHeaders=From&metadataHeaders=Date"
        )
        return cls._http_get_json(endpoint, access_token=access_token)

    @classmethod
    def decode_mime_body(cls, payload: dict) -> str:
        body = cls._decode_message_part(payload.get("payload", {}).get("body", {}))
        if body:
            return body

        for part in payload.get("payload", {}).get("parts", []) or []:
            text = cls._extract_text_from_part(part)
            if text:
                return text
        return payload.get("snippet", "") or ""

    @classmethod
    def extract_metadata(cls, message_payload: dict) -> dict[str, datetime | str | None]:
        headers = message_payload.get("payload", {}).get("headers", [])
        data: dict[str, datetime | str | None] = {"subject": "", "sender": "", "received_at": None}
        for header in headers:
            name = str(header.get("name", "")).lower()
            value = str(header.get("value", "")).strip()
            if name == "subject":
                data["subject"] = value
            elif name == "from":
                data["sender"] = value
            elif name == "date":
                try:
                    data["received_at"] = parsedate_to_datetime(value)
                except (TypeError, ValueError):
                    data["received_at"] = None
        return data

    @classmethod
    def _extract_text_from_part(cls, part: dict) -> str:
        mime_type = str(part.get("mimeType", "")).lower()
        if mime_type.startswith("text/plain"):
            return cls._decode_message_part(part.get("body", {}))

        for nested in part.get("parts", []) or []:
            nested_text = cls._extract_text_from_part(nested)
            if nested_text:
                return nested_text
        return ""

    @staticmethod
    def _decode_message_part(body: dict) -> str:
        data = body.get("data")
        if not data:
            return ""
        padding = "=" * (-len(data) % 4)
        try:
            decoded = base64.urlsafe_b64decode(f"{data}{padding}".encode("utf-8"))
            return decoded.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    @staticmethod
    def _http_get_json(url: str, *, access_token: str) -> dict:
        req = request.Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {access_token}")

        try:
            with request.urlopen(req, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover
            raise GmailAPIError("Failed to call Gmail API.") from exc