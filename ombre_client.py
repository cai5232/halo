from __future__ import annotations
import os
from typing import Any
import httpx


class OmbreClient:
    def __init__(self) -> None:
        self.enabled = os.getenv('OMBRE_ENABLED', 'true').lower() not in {'0', 'false', 'no'}
        self.url = os.getenv('OMBRE_MCP_URL', 'https://caiovo.zeabur.app/mcp').strip().rstrip('/')
        if not self.url.endswith('/mcp'):
            self.url += '/mcp'
        self.token = os.getenv('OMBRE_MCP_TOKEN', '').strip()

    def _call(self, tool: str, arguments: dict[str, Any]) -> Any:
        if not self.enabled:
            return None
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': tool, 'arguments': arguments}}
        try:
            response = httpx.post(self.url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            return response.json().get('result')
        except Exception:
            return None

    @staticmethod
    def _text(result: Any) -> str:
        if isinstance(result, dict):
            content = result.get('content')
            if isinstance(content, list):
                return '\n'.join(str(item.get('text', '')) for item in content if isinstance(item, dict))
            return str(result.get('result', result.get('text', '')))
        return str(result or '')

    def breath(self, query: str, limit: int = 8) -> dict[str, Any]:
        result = self._call('breath_search', {'query': query or '', 'max_results': max(1, min(limit, 50))})
        text = self._text(result)
        memories = [{'id': i + 1, 'content': v, 'tags': ['ombre']} for i, v in enumerate(filter(None, [text]))]
        return {'ok': result is not None, 'query': query, 'memories': memories}
