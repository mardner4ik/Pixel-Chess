"""Small HTTP client for the separately deployed multiplayer relay."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class MultiplayerError(Exception):
    pass


class MultiplayerClient:
    def __init__(self, base_url, timeout=8):
        self.base_url = base_url.strip().rstrip('/')
        self.timeout = timeout
        self.country = 'ZZ'

    def request(self, method, path, payload=None, extra_headers=None):
        if not self.base_url or 'YOUR_USERNAME' in self.base_url:
            raise MultiplayerError('Set your PythonAnywhere server URL first')
        data = json.dumps(payload).encode('utf-8') if payload is not None else None
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        headers['X-Detected-Country'] = self.country
        headers.update(extra_headers or {})
        request = Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            try:
                result = json.loads(exc.read().decode('utf-8'))
            except (ValueError, OSError):
                result = {}
            raise MultiplayerError(result.get('error', f'HTTP {exc.code}')) from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise MultiplayerError(f'Could not reach multiplayer server: {exc}') from exc
        if isinstance(result, dict) and result.get('error'):
            raise MultiplayerError(result['error'])
        return result

    def profile(self):
        # Detect from the device's public IP. PythonAnywhere free accounts
        # restrict outbound HTTP, so the lookup must not depend on server egress.
        try:
            req = Request('https://ipapi.co/json/', headers={'User-Agent': 'PixelChess/1.0'})
            with urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode('utf-8'))
            country = str(data.get('country_code') or data.get('country') or '').upper()
            if len(country) == 2 and country.isalpha() and country not in {'UN', 'ZZ'}:
                self.country = country
        except Exception:
            pass
        result = self.request('GET', '/api/profile')
        server_country = str(result.get('country', '')).upper()
        if len(server_country) == 2 and server_country.isalpha() and server_country not in {'UN', 'ZZ'}:
            self.country = server_country
        result['country'] = self.country
        return result

    def rooms(self):
        return self.request('GET', '/api/rooms').get('rooms', [])

    def create_room(self, nickname, private, description, device='mobile'):
        return self.request('POST', '/api/rooms', {
            'nickname': nickname, 'private': bool(private), 'description': description,
            'country': self.country, 'device': device,
        })

    def join_room(self, code, nickname, device='mobile'):
        return self.request('POST', f'/api/rooms/{code.strip().upper()}/join',
                            {'nickname': nickname, 'country': self.country, 'device': device})

    def start_room(self, code, token):
        return self.request('POST', f'/api/rooms/{code}/start', {'token': token})

    def state(self, code, token, after=0):
        return self.request('GET', f'/api/rooms/{code}/state?after={after}',
                            extra_headers={'Authorization': f'Bearer {token}'})

    def update_presence(self, code, token, x, y, drag_square=None, visible=True):
        return self.request('POST', f'/api/rooms/{code}/presence', {
            'token': token, 'x': x, 'y': y, 'drag_square': drag_square, 'visible': visible,
        })

    def send_move(self, code, token, uci):
        return self.request('POST', f'/api/rooms/{code}/moves', {'token': token, 'uci': uci})

    def leave_room(self, code, token):
        return self.request('POST', f'/api/rooms/{code}/leave', {'token': token})

    def resign(self, code, token):
        return self.request('POST', f'/api/rooms/{code}/resign', {'token': token})
