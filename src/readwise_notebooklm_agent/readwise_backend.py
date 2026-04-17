"""Backend adapters for Readwise Reader access."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol

API_BASE = "https://readwise.io/api/v3"


class BackendError(RuntimeError):
    """Raised when a Readwise backend cannot complete a requested operation."""


class ReadwiseBackend(Protocol):
    name: str

    def list_documents(
        self,
        *,
        updated_after: str | None,
        location: str | None,
        category: str | None,
        tag: list[str],
        limit_pages: int,
        with_html: bool,
        with_raw: bool,
    ) -> list[dict]:
        """Return Reader documents."""

    def get_document(self, document_id: str) -> dict | None:
        """Return one Reader document by ID, if found."""

    def update_documents(self, updates: list[dict], *, dry_run: bool) -> dict:
        """Apply document updates or return a dry-run payload."""


@dataclass
class ReaderApiBackend:
    token: str
    api_base: str = API_BASE
    name: str = "api"

    def request_json(self, path: str, params: dict[str, str], *, method: str = "GET", body: dict | None = None) -> dict:
        query = ("?" + urllib.parse.urlencode(params, doseq=True)) if params else ""
        data = None
        headers = {"Authorization": f"Token {self.token}", "Content-Type": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.api_base + path + query, data=data, headers=headers, method=method)
        while True:
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    raw = r.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = int(e.headers.get("Retry-After", "5"))
                    print(f"Rate limited; sleeping {wait}s")
                    time.sleep(wait)
                    continue
                detail = e.read().decode("utf-8", "replace")[:500]
                raise BackendError(f"Readwise API error {e.code}: {detail}") from e

    def list_documents(
        self,
        *,
        updated_after: str | None,
        location: str | None,
        category: str | None,
        tag: list[str],
        limit_pages: int,
        with_html: bool,
        with_raw: bool,
    ) -> list[dict]:
        docs: list[dict] = []
        cursor = None
        pages = 0
        while True:
            params: dict[str, str | list[str]] = {"limit": "100"}
            if cursor:
                params["pageCursor"] = cursor
            elif updated_after:
                params["updatedAfter"] = updated_after
            if location:
                params["location"] = location
            if category:
                params["category"] = category
            if tag:
                params["tag"] = tag
            if with_html:
                params["withHtmlContent"] = "true"
            if with_raw:
                params["withRawSourceUrl"] = "true"
            data = self.request_json("/list/", params)
            docs.extend(data.get("results", []))
            cursor = data.get("nextPageCursor")
            pages += 1
            if not cursor or pages >= limit_pages:
                break
        return docs

    def get_document(self, document_id: str) -> dict | None:
        data = self.request_json("/list/", {"id": document_id, "limit": "1"})
        results = data.get("results", [])
        return results[0] if results else None

    def update_documents(self, updates: list[dict], *, dry_run: bool) -> dict:
        payload = {"updates": updates}
        if dry_run:
            return payload
        return self.request_json("/bulk_update/", {}, method="PATCH", body=payload)


@dataclass
class ReadwiseCliBackend:
    command: str = "readwise"
    name: str = "readwise-cli"

    @classmethod
    def is_available(cls, command: str = "readwise") -> bool:
        return shutil.which(command) is not None

    def _run_json(self, args: list[str]) -> dict:
        cmd = [self.command, "--json", *args]
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise BackendError(f"Readwise CLI failed: {' '.join(cmd)}\n{detail}")
        try:
            return json.loads(proc.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise BackendError(f"Readwise CLI returned non-JSON output for {' '.join(cmd)}") from exc

    def list_documents(
        self,
        *,
        updated_after: str | None,
        location: str | None,
        category: str | None,
        tag: list[str],
        limit_pages: int,
        with_html: bool,
        with_raw: bool,
    ) -> list[dict]:
        docs: list[dict] = []
        cursor = None
        pages = 0
        while True:
            args = ["reader-list-documents", "--limit", "100"]
            if cursor:
                args += ["--page-cursor", cursor]
            elif updated_after:
                args += ["--updated-after", updated_after]
            if location:
                args += ["--location", location]
            if category:
                args += ["--category", category]
            for tag_name in tag:
                args += ["--tag", tag_name]
            response_fields = [
                "title", "source_url", "summary", "category", "location", "updated_at",
                "url", "site_name", "notes", "tags", "author", "published_date",
            ]
            if with_html:
                response_fields.append("html_content")
            args += ["--response-fields", ",".join(response_fields)]
            data = self._run_json(args)
            docs.extend(data.get("results", []))
            cursor = data.get("nextPageCursor")
            pages += 1
            if not cursor or pages >= limit_pages:
                break
        return docs

    def get_document(self, document_id: str) -> dict | None:
        data = self._run_json([
            "reader-list-documents",
            "--id", document_id,
            "--limit", "1",
            "--response-fields", "title,source_url,summary,category,location,updated_at,url,site_name,notes,tags,author,published_date",
        ])
        results = data.get("results", [])
        return results[0] if results else None

    def update_documents(self, updates: list[dict], *, dry_run: bool) -> dict:
        payload = {"updates": updates}
        if dry_run:
            return payload
        results = []
        for update in updates:
            if set(update) - {"id", "location"}:
                raise BackendError("Readwise CLI backend currently supports only location updates")
            if "location" not in update:
                continue
            data = self._run_json([
                "reader-move-documents",
                "--document-ids", update["id"],
                "--location", update["location"],
            ])
            results.append(data)
        return {"results": results}


def make_backend(kind: str, *, token_loader, cli_command: str = "readwise") -> ReadwiseBackend:
    if kind == "readwise-cli":
        if not ReadwiseCliBackend.is_available(cli_command):
            raise BackendError("official `readwise` CLI not found on PATH")
        return ReadwiseCliBackend(cli_command)
    if kind == "api":
        return ReaderApiBackend(token_loader())
    if kind == "auto":
        if ReadwiseCliBackend.is_available(cli_command):
            return ReadwiseCliBackend(cli_command)
        return ReaderApiBackend(token_loader())
    raise BackendError(f"unknown Readwise backend: {kind}")
