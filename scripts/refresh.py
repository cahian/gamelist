#!/usr/bin/env python3
"""Refresh metadata without API keys or runtime dependencies. Python 3.11+."""
import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, quote, urlparse
from urllib.request import Request, urlopen

from game_metadata import match_game, normalize, parse_hltb, parse_metacritic, parse_proton, parse_ign, parse_steam_price, recommend, nintendo_console, PC_PLATFORMS

ROOT = Path(__file__).resolve().parents[1]
UA = 'Mozilla/5.0 (compatible; GameList/1.0; +https://github.com/cahian/gamelist)'
# Public application identifier used by Metacritic's own web client, not a user credential.
MC_KEY = '7e3d2d4f75ed45de84d9e2acbe31af52'
DAY = 86400
# Leave margin for the daily workflow to finish earlier than its preceding run.
STEAM_PRICE_TTL = 23 * 3600


def valid_price_snapshot(data, appid):
    """Only reuse this exact application's normalized Brazilian price snapshot."""
    if not isinstance(data, dict) or str(data.get('appid')) != str(appid):
        return False
    if data.get('country') != 'BR' or data.get('currency') != 'BRL':
        return False
    status = data.get('status')
    if status in {'available', 'free'}:
        initial, final = data.get('initial'), data.get('final')
        return (type(initial) is int and type(final) is int and 0 <= final <= initial
                and (status != 'free' or data.get('isFree') is True and final == 0))
    return status in {'unavailable', 'coming_soon'} and data.get('final') is None


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


class Cache:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.values = json.loads(path.read_text()) if path.exists() else {}

    def seed(self, games):
        """A fresh committed snapshot also works as cache on a clean CI runner."""
        for game in games:
            for provider, source in game.get('sources', {}).items():
                if source.get('status') != 'ok' or not source.get('updatedAt'):
                    continue
                if provider == 'steamPrice':
                    appid = (game.get('steam') or {}).get('appid') or (source.get('data') or {}).get('appid')
                    if not valid_price_snapshot(source.get('data'), appid):
                        continue
                    key = f'{appid}:br'
                elif provider in {'steam', 'proton', 'deck'}:
                    steam = game.get('steam') or {}
                    key = str((steam.get('appid') if provider == 'steam' else steam.get('compatAppid') or steam.get('appid')) or '')
                elif provider == 'metacritic':
                    key = game.get('mslug') or game['name']
                else:
                    key = game['name']
                if not key:
                    continue
                stamp = datetime.fromisoformat(source['updatedAt']).timestamp()
                cache_key = provider + ':' + key
                if stamp > self.values.get(cache_key, {}).get('time', 0):
                    self.values[cache_key] = {'data': source['data'], 'updatedAt': source['updatedAt'], 'time': stamp}

    def get(self, provider, key, loader, ttl=DAY):
        cache_key = f'{provider}:{key}'
        with self.lock:
            old = self.values.get(cache_key)
        if old and time.time() - old['time'] < ttl:
            return {'data': old['data'], 'updatedAt': old['updatedAt'], 'status': 'ok'}
        try:
            data = loader()
            stamp = now()
            with self.lock:
                self.values[cache_key] = {'data': data, 'updatedAt': stamp, 'time': time.time()}
            return {'data': data, 'updatedAt': stamp, 'status': 'ok'}
        except Exception as error:
            return {'data': old['data'] if old else None, 'updatedAt': old['updatedAt'] if old else None,
                    'status': 'stale' if old else 'error', 'error': str(error)[:200], 'attemptedAt': now()}

    def save(self):
        with self.lock:
            atomic_json(self.path, self.values)


class Providers:
    def __init__(self, cache, force=False):
        self.cache = cache
        self.force = force
        self.rate_lock = threading.Lock()
        self.host_next = {}
        self.hltb_lock = threading.Lock()
        self.hltb_endpoint = '/api/search/site'
        self.hltb_token = None
        self.token_at = 0
        self.rpcs3_data = None
        self.rpcs3_source = None

    def request(self, url, payload=None, headers=None, missing=False, raw=False):
        host = urlparse(url).netloc
        interval = .85 if 'steampowered' in host else 1.05 if 'howlongtobeat' in host else .25
        if '/search/issues' in url:
            host += '/search'
            interval = 6.5
        for attempt in range(3):
            with self.rate_lock:
                start = max(time.monotonic(), self.host_next.get(host, 0))
                self.host_next[host] = start + interval
            time.sleep(max(0, start - time.monotonic()))
            request_headers = {'User-Agent': UA, 'Accept': 'application/json'}
            request_headers.update(headers or {})
            if 'api.github.com' in url:
                token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
                if token:
                    request_headers['Authorization'] = 'Bearer ' + token
            data = json.dumps(payload).encode() if payload is not None else None
            if data is not None:
                request_headers['Content-Type'] = 'application/json'
            try:
                with urlopen(Request(url, data=data, headers=request_headers), timeout=25) as response:
                    text = response.read().decode('utf-8')
                return text if raw else json.loads(text)
            except HTTPError as error:
                if error.code == 404 and missing:
                    return None
                if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise
                delay = min(30, max(2 ** (attempt + 1), int(error.headers.get('Retry-After', '10'))))
                time.sleep(delay)

    def fetch(self, provider, key, loader, ttl=DAY):
        return self.cache.get(provider, key, loader, ttl=-1 if self.force else ttl)

    def discover_hltb(self):
        html = self.request('https://howlongtobeat.com/', raw=True)
        scripts = re.findall(r'<script[^>]+src="([^"]+\.js[^" ]*)', html)
        for script in scripts:
            if not script.startswith('/_next/'):
                continue
            code = self.request('https://howlongtobeat.com' + script, raw=True)
            if 'searchTerms' not in code or 'x-auth-token' not in code:
                continue
            match = re.search(r'fetch\(["\'](/api/[\w/]+)["\'],\{method:["\']POST', code)
            if match:
                self.hltb_endpoint = match[1]
                return
        raise ValueError('HLTB: endpoint de busca não encontrado no cliente atual')

    def token(self, renew=False):
        with self.hltb_lock:
            if renew or not self.hltb_token or time.monotonic() - self.token_at > 600:
                headers = {'Referer': 'https://howlongtobeat.com/', 'Origin': 'https://howlongtobeat.com'}
                try:
                    auth = self.request('https://howlongtobeat.com' + self.hltb_endpoint + '/init?t=' + str(int(time.time() * 1000)), headers=headers)
                except HTTPError as error:
                    if error.code != 404:
                        raise
                    self.discover_hltb()
                    auth = self.request('https://howlongtobeat.com' + self.hltb_endpoint + '/init?t=' + str(int(time.time() * 1000)), headers=headers)
                if not auth.get('token'):
                    raise ValueError('HLTB: token de sessão ausente')
                self.hltb_token = auth
                self.token_at = time.monotonic()
            return self.hltb_token

    def hltb(self, game):
        query = re.sub(r'\[[^]]+\]', '', game['name']).strip()
        payload = {'searchType': 'games', 'searchTerms': query.split(), 'searchPage': 1, 'size': 20,
                   'searchOptions': {'games': {'userId': 0, 'platform': '', 'sortCategory': 'popular',
                      'rangeCategory': 'main', 'rangeTime': {'min': 0, 'max': 0},
                      'gameplay': {'perspective': '', 'flow': '', 'genre': ''},
                      'rangeYear': {'min': '', 'max': ''}, 'modifier': ''},
                      'users': {'sortCategory': 'postcount'}, 'lists': {'sortCategory': 'follows'},
                      'filter': '', 'sort': 0, 'randomizer': 0}, 'useCache': True}
        for attempt in range(2):
            auth = self.token(renew=attempt == 1)
            headers = {'Referer': 'https://howlongtobeat.com/', 'Origin': 'https://howlongtobeat.com',
                       'x-auth-token': auth['token']}
            if auth.get('hpKey') and auth.get('hpVal'):
                headers.update({'x-hp-key': auth['hpKey'], 'x-hp-val': auth['hpVal']})
                payload[auth['hpKey']] = auth['hpVal']
            try:
                result = self.request('https://howlongtobeat.com' + self.hltb_endpoint, payload, headers)
                break
            except HTTPError as error:
                if error.code not in {403, 404} or attempt == 1:
                    raise
                if error.code == 404:
                    with self.hltb_lock:
                        self.discover_hltb()
        if not isinstance(result.get('data'), list):
            raise ValueError('HLTB: lista de resultados ausente')
        candidate = match_game(game['name'], result['data'], 'game_name', year=game.get('year'))
        return parse_hltb(candidate) if candidate else None

    def metacritic(self, game):
        slug = game.get('mslug')
        if not slug:
            return None
        payload = self.request('https://backend.metacritic.com/composer/metacritic/pages/games/'
                               + quote(slug, safe='') + '/web?' + urlencode({'apiKey': MC_KEY}), missing=True)
        if payload is None:
            return None
        result = parse_metacritic(payload)
        if result['slug'] != slug:
            raise ValueError('Metacritic: slug retornado difere do solicitado')
        if not match_game(game.get('found') or game['name'], [{'name': result['name']}], 'name'):
            raise ValueError('Metacritic: título retornado não corresponde ao catálogo')
        return result

    def steam_search(self, game):
        query = re.sub(r'\[[^]]+\]', '', game['name']).strip()
        payload = self.request('https://store.steampowered.com/api/storesearch/?' + urlencode({'term': query, 'l': 'english', 'cc': 'us'}))
        if not isinstance(payload.get('items'), list):
            raise ValueError('Steam: resultados de busca ausentes')
        candidates = [item for item in payload['items'] if item.get('type') == 'app']
        candidate = match_game(game['name'], candidates, 'name', editions=True)
        return candidate['id'] if candidate else None

    def ign(self, game):
        query = ('query GameListMetadata($slug:String!) {'
                 'objectSelectByTypeAndSlug(type:Game,slug:$slug,state:Published){'
                 'id slug metadata{names{name alt}} hl2bData '
                 'objectRegions{releases{date platformAttributes{name}}}}}')
        title_slug = re.sub(r'[^a-z0-9]+', '-', game['name'].lower().replace("'", '')).strip('-')
        slugs = list(dict.fromkeys([game.get('mslug'), title_slug]))
        slugs = [slug for slug in slugs if slug]
        for slug in slugs:
            arguments = {'query': query, 'operationName': 'GameListMetadata', 'variables': json.dumps({'slug': slug})}
            payload = self.request('https://mollusk.apis.ign.com/graphql?' + urlencode(arguments),
                                   headers={'Referer': 'https://www.ign.com/', 'x-apollo-operation-name': 'GameListMetadata',
                                            'apollographql-client-name': 'kraken'})
            errors = payload.get('errors') or []
            if errors:
                error = errors[0]
                if error.get('extensions', {}).get('code') == 'REDIRECT':
                    redirect = re.search(r'/games/([a-z0-9-]+)', error.get('message', ''))
                    if redirect and redirect[1] not in slugs and len(slugs) < 6:
                        slugs.append(redirect[1])
                    continue
                if error.get('extensions', {}).get('code') in {'NOT_FOUND', 'NOTFOUND'}:
                    continue
                raise ValueError('IGN: ' + error.get('message', 'consulta GraphQL indisponível')[:160])
            if 'data' not in payload:
                raise ValueError('IGN: resposta GraphQL inválida')
            item = payload['data'].get('objectSelectByTypeAndSlug')
            if item is None:
                continue
            result = parse_ign(item)
            candidate = match_game(game['name'], [result], 'name', year=game.get('year'))
            if candidate:
                return result
        return None

    def steam_details(self, appid):
        payload = self.request('https://store.steampowered.com/api/appdetails?' + urlencode({'appids': appid, 'l': 'english', 'cc': 'us'}))
        result = payload.get(str(appid))
        if not isinstance(result, dict) or 'success' not in result:
            raise ValueError('Steam: detalhes inválidos')
        if not result['success']:
            raise ValueError('Steam: aplicativo indisponível (conservando dados anteriores)')
        item = result['data']
        if item.get('type') not in {'game', 'dlc'}:
            return None
        return {'appid': appid, 'name': item['name'], 'url': f'https://store.steampowered.com/app/{appid}/',
                'isDlc': item.get('type') == 'dlc',
                'compatAppid': int(item.get('fullgame', {}).get('appid') or appid),
                'linux': item.get('platforms', {}).get('linux', False),
                'comingSoon': item.get('release_date', {}).get('coming_soon', False),
                'releaseDate': item.get('release_date', {}).get('date'),
                'metacritic': item.get('metacritic'),
                'vrOnly': any(c.get('id') == 54 for c in item.get('categories', []))}

    def steam_price(self, appid):
        # Store API is called in CI, never cross-origin from the visitor's browser.
        payload = self.request('https://store.steampowered.com/api/appdetails?' +
                               urlencode({'appids': appid, 'l': 'brazilian', 'cc': 'br'}))
        return parse_steam_price(payload, appid)

    def proton(self, appid):
        payload = self.request(f'https://www.protondb.com/api/v1/reports/summaries/{appid}.json', missing=True)
        return parse_proton(payload) if payload is not None else None

    def deck(self, appid):
        payload = self.request(f'https://store.steampowered.com/saleaction/ajaxgetdeckappcompatibilityreport?nAppID={appid}')
        if payload.get('success') != 1 or not isinstance(payload.get('results'), dict):
            raise ValueError('Valve: relatório indisponível')
        item = payload['results']
        category = item.get('resolved_category')
        if category not in {0, 1, 2, 3}:
            raise ValueError('Valve: categoria desconhecida')
        return {'category': category, 'steamOSCategory': item.get('steamos_resolved_category'),
                'notes': [note.get('loc_token') for note in item.get('resolved_items', [])]}

    def rpcs3(self):
        payload = self.request('https://rpcs3.net/compatibility?api=v1')
        if payload.get('return_code') != 0 or not isinstance(payload.get('results'), dict):
            raise ValueError('RPCS3: lista de compatibilidade inválida')
        return [{'serial': serial, **{k: item.get(k) for k in ['title', 'status', 'date']}}
                for serial, item in payload['results'].items()]

    def emulation(self, game, platforms):
        # Explicit prior routes distinguish the edition from an unrelated original.
        reference = ' '.join(game.get(k, '') for k in ['dset', 'how'])
        options = [('RPCS3', 'PS3', 'https://rpcs3.net/compatibility'),
                   ('PCSX2', 'PS2', 'https://pcsx2.net/compat/'),
                   ('Dolphin', 'GameCube/Wii', 'https://dolphin-emu.org/compat/'),
                   ('Cemu', 'Wii U', 'https://compat.cemu.info/'),
                   ('Azahar', '3DS', 'https://azahar-emu.org/'),
                   ('PPSSPP', 'PSP', 'https://www.ppsspp.org/'),
                   ('shadPS4', 'PS4', 'https://github.com/shadps4-compatibility/shadps4-game-compatibility'),
                   ('Xenia', 'Xbox 360', 'https://github.com/xenia-canary/game-compatibility')]
        emulator = next((option for option in options if option[0].lower() in reference.lower()), None)
        if emulator is None and re.search(r'Yuzu|Eden|Citron|Suyu|Emulador Switch|Switch via', reference, re.I):
            emulator = ('Eden', 'Switch', 'https://eden-emu.dev/')
        if emulator is None:
            if 'PlayStation 3' in platforms and not any(p in platforms for p in ['PC', 'PlayStation 5']):
                emulator = options[0]
            elif 'Nintendo Switch' in platforms and 'PC' not in platforms and 'Nintendo Switch 2' not in platforms:
                emulator = ('Eden', 'Switch', 'https://eden-emu.dev/')
            elif 'PC' not in platforms:
                for platform, candidate in [('PlayStation 2', options[1]), ('Nintendo GameCube', options[2]),
                     ('GameCube', options[2]), ('Wii', options[2]), ('Wii U', options[3]),
                     ('Nintendo 3DS', options[4]), ('PlayStation Portable', options[5]), ('PSP', options[5]),
                     ('PlayStation', ('DuckStation', 'PS1', 'https://www.duckstation.org/')),
                     ('Nintendo 64', ('Mupen64Plus', 'N64', 'https://mupen64plus.org/'))]:
                    if platform in platforms:
                        emulator = candidate
                        break
        if not emulator:
            return None
        name, console, url = emulator
        result = {'emulator': name, 'console': console, 'status': 'A confirmar', 'verified': False, 'url': url}
        if name == 'RPCS3' and self.rpcs3_data:
            matches = [item for item in self.rpcs3_data if normalize(item['title']) == normalize(game['name'])]
            order = {'Playable': 5, 'Ingame': 4, 'Intro': 3, 'Loadable': 2, 'Nothing': 1}
            if matches:
                best = max(matches, key=lambda item: order.get(item['status'], 0))
                result.update(status=best['status'], verified=True, serial=best['serial'],
                              testedAt=best['date'], url='https://rpcs3.net/compatibility?' + urlencode({'g': best['serial']}))
                if self.rpcs3_source:
                    result.update(databaseUpdatedAt=self.rpcs3_source['updatedAt'], databaseStatus=self.rpcs3_source['status'])
        elif name in {'shadPS4', 'Xenia'}:
            repo = 'shadps4-compatibility/shadps4-game-compatibility' if name == 'shadPS4' else 'xenia-canary/game-compatibility'
            query = f'repo:{repo} "{re.sub(chr(34), "", game["name"])}" in:title'
            payload = self.request('https://api.github.com/search/issues?' + urlencode({'q': query, 'per_page': 30}))
            if not isinstance(payload.get('items'), list):
                raise ValueError(f'{name}: relatórios ausentes')
            matches = []
            for issue in payload['items']:
                title = re.sub(r'^(?:CUSA\d+|[A-Fa-f0-9]{8})\s*[-:]\s*', '', issue['title'])
                title = re.sub(r'\s*\[(?:Linux|Windows|macOS)\]\s*', '', title, flags=re.I)
                if normalize(title) != normalize(game['name']):
                    continue
                labels = [label['name'].lower() for label in issue['labels']]
                body = issue.get('body') or ''
                linux = any('linux' in label for label in labels) or bool(re.search(r'### Operating System\s+Linux\b', body, re.I))
                status = next((s for s in ['Playable', 'Ingame', 'Intro', 'Boots', 'Nothing']
                               if any(s.lower() == label.replace('status-', '').replace('state-', '') for label in labels)), None)
                if name == 'shadPS4' and not linux:
                    continue
                if status:
                    matches.append({'status': status, 'verified': name == 'shadPS4' and linux,
                                    'url': issue['html_url'], 'testedAt': issue['updated_at'],
                                    'reportOS': 'Linux' if linux else 'Windows'})
            if matches:
                best = max(matches, key=lambda item: (item['status'] == 'Playable', item['testedAt']))
                result.update(best)
            if name == 'Xenia':
                result['emulator'] = 'Xenia Canary'
        if result['status'] == 'A confirmar' and game.get('dsrc'):
            result['referenceUrl'] = game['dsrc']
        return result


def add_steam_price(game, previous, providers, appid):
    """The price has its own cache and timestamp; DLC keeps its own app ID."""
    game['price'] = None
    if not appid:
        game['sources'].pop('steamPrice', None)
        return game
    envelope = providers.fetch('steamPrice', f'{appid}:br', lambda: providers.steam_price(appid), STEAM_PRICE_TTL)
    old = previous.get('sources', {}).get('steamPrice', {})
    if envelope['status'] == 'error' and valid_price_snapshot(old.get('data'), appid):
        envelope.update(data=old['data'], updatedAt=old.get('updatedAt'), status='stale')
    game['sources']['steamPrice'] = envelope
    game['price'] = envelope['data']
    return game


def enrich_prices(game, previous, providers):
    """Refresh prices without querying or changing other metadata providers."""
    result = {**game, **previous, 'sources': dict(previous.get('sources', {}))}
    appid = (result.get('steam') or {}).get('appid')
    return add_steam_price(result, previous, providers, appid)


def enrich(game, previous, providers):
    sources = {}
    def fetch(field, key, loader, ttl=DAY):
        envelope = providers.fetch(field, key, loader, ttl)
        old = previous.get('sources', {}).get(field, {})
        if envelope['status'] == 'error' and old.get('data') is not None:
            envelope.update(data=old['data'], updatedAt=old.get('updatedAt'), status='stale')
        sources[field] = envelope
        return envelope['data']
    hltb = fetch('hltb', game['name'], lambda: providers.hltb(game), 7 * DAY)
    mc = fetch('metacritic', game.get('mslug') or game['name'], lambda: providers.metacritic(game))
    appid = fetch('steamSearch', game['name'], lambda: providers.steam_search(game), 7 * DAY)
    ign = None
    if not hltb or not appid:
        ign = fetch('ign', game['name'], lambda: providers.ign(game), 7 * DAY)
        if ign:
            appid = appid or ign.get('appid')
            if not hltb and ign.get('hltb'):
                hltb = ign['hltb']
                sources['hltb'] = {**sources['ign'], 'data': hltb, 'via': 'IGN GraphQL'}
    steam = proton = deck = emulation = None
    if appid:
        steam = fetch('steam', str(appid), lambda: providers.steam_details(appid), DAY if previous.get('steam') else 0)
        if not steam and sources['steam']['status'] != 'ok':
            replacement = fetch('steamSearch', game['name'], lambda: providers.steam_search(game), 0)
            if replacement and replacement != appid:
                appid = replacement
                steam = fetch('steam', str(appid), lambda: providers.steam_details(appid))
        if steam:
            compatibility_appid = steam.get('compatAppid') or appid
            proton = fetch('proton', str(compatibility_appid), lambda: providers.proton(compatibility_appid))
            deck = fetch('deck', str(compatibility_appid), lambda: providers.deck(compatibility_appid))
    platforms = list(dict.fromkeys((hltb or {}).get('platforms', []) + (mc or {}).get('platforms', []) + (ign or {}).get('platforms', [])))
    if not steam and not any(p in PC_PLATFORMS for p in platforms) and not nintendo_console(game, platforms):
        emulation = fetch('emulation', game['name'], lambda: providers.emulation(game, platforms))
        if emulation and emulation.get('databaseStatus') in {'stale', 'error'}:
            sources['emulation'].update(status='stale', updatedAt=emulation.get('databaseUpdatedAt'), error='Base RPCS3 indisponível; usando última consulta válida')
    play = recommend(game, steam, proton, deck, emulation, platforms, release_date=(mc or {}).get('releaseDate'))
    result = {**game, 'sources': sources, 'play': play, 'hltb': hltb, 'steam': steam,
              'proton': proton, 'deck': deck, 'emulation': emulation, 'metacritic': mc}
    if mc:
        result.update(critic=mc['critic'], user=mc['user'])
    else:
        result.update(critic=previous.get('critic', game.get('critic')),
                      user=previous.get('user', game.get('user')))
    return add_steam_price(result, previous, providers, (steam or {}).get('appid') or appid)


def read_snapshot(path):
    if not path.exists():
        return {}
    text = path.read_text()
    match = re.search(r'const GAMES\s*=\s*(\[.*\]);?\s*$', text, re.S)
    return {game['name']: game for game in json.loads(match[1])} if match else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, help='Refresh only the first N games (smoke test)')
    parser.add_argument('--force', action='store_true', help='Ignore cache TTLs')
    parser.add_argument('--prices-only', action='store_true', help='Refresh only Brazilian Steam prices for linked apps')
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    catalog = json.loads((ROOT / 'catalog.json').read_text())
    previous = read_snapshot(ROOT / 'data.js')
    cache = Cache(ROOT / '.cache/providers.json')
    cache.seed(previous.values())
    providers = Providers(cache, args.force)
    if not args.prices_only:
        rpc = providers.fetch('rpcs3', 'all', providers.rpcs3)
        providers.rpcs3_data = rpc['data']
        providers.rpcs3_source = rpc
    selected = catalog[:args.limit] if args.limit else catalog
    completed = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        refresh_game = enrich_prices if args.prices_only else enrich
        futures = {pool.submit(refresh_game, game, previous.get(game['name'], {}), providers): game for game in selected}
        for future in as_completed(futures):
            game = future.result()
            completed[game['name']] = game
            if len(completed) % 20 == 0 or len(completed) == len(selected):
                print(f'Atualizados {len(completed)}/{len(selected)} jogos', flush=True)
                cache.save()
    games = [completed.get(game['name']) or previous.get(game['name']) or game for game in catalog]
    refreshed = list(completed.values())
    errors = [{'name': game['name'], 'provider': key, 'error': item.get('error'),
               'status': item['status']} for game in refreshed for key, item in game['sources'].items()
              if item['status'] != 'ok' and (not args.prices_only or key == 'steamPrice')]
    report = {'generatedAt': now(), 'games': len(games), 'refreshed': len(refreshed),
              'coverage': {key: sum(bool(game.get(key)) for game in games) for key in
                           ['hltb', 'metacritic', 'steam', 'proton', 'deck', 'emulation']},
              'errors': errors}
    report['coverage']['steamPrice'] = sum((game.get('price') or {}).get('status') in {'available', 'free'} for game in games)
    atomic_json(ROOT / 'refresh-report.json', report)
    if not any(source['status'] == 'ok' for game in refreshed for key, source in game['sources'].items()
               if not args.prices_only or key == 'steamPrice'):
        raise RuntimeError('Nenhuma fonte respondeu; snapshot anterior preservado')
    text = 'const GENERATED=' + json.dumps(report['generatedAt']) + ';\n'
    text += 'const UPDATE_INFO=' + json.dumps({k: v for k, v in report.items() if k != 'errors'}, ensure_ascii=False) + ';\n'
    text += 'const GAMES=' + json.dumps(games, ensure_ascii=False, separators=(',', ':')) + ';\n'
    temporary = ROOT / 'data.js.tmp'
    temporary.write_text(text)
    temporary.replace(ROOT / 'data.js')
    index = ROOT / 'index.html'
    version = hashlib.sha256(text.encode()).hexdigest()[:12]
    index_text = re.sub(r'data\.js\?v=[^"\s]+', 'data.js?v=' + version, index.read_text())
    index.write_text(index_text)
    cache.save()
    print(json.dumps({key: value for key, value in report.items() if key != 'errors'}, ensure_ascii=False), flush=True)
    print(f'{len(errors)} consultas com falha; último dado válido preservado quando disponível.', flush=True)


if __name__ == '__main__':
    main()
