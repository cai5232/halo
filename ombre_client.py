import os
import httpx

OMBRE_URL = os.environ.get('OMBRE_MCP_URL', 'https://caiovo.zeabur.app/mcp')
OMBRE_TOKEN = os.environ.get('OMBRE_MCP_TOKEN', '')


class OmbreClient:
    async def breath(self, query: str, limit: int = 5) -> list:
        headers = {'Content-Type': 'application/json'}
        if OMBRE_TOKEN:
            headers['Authorization'] = f'Bearer {OMBRE_TOKEN}'

        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {
                'name': 'breath_search',
                'arguments': {'query': query, 'max_results': limit},
            },
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(OMBRE_URL, json=payload, headers=headers)
            data = resp.json()

        content = data.get('result', {}).get('content', [])
        return [c['text'] for c in content if c.get('type') == 'text']
