"""Provider parsing and conservative PC/Steam Deck recommendations."""
import re
import unicodedata
from difflib import SequenceMatcher

ROMAN = {'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6', 'vii': '7',
         'viii': '8', 'ix': '9', 'x': '10', 'xi': '11', 'xii': '12',
         'xiii': '13', 'xiv': '14', 'xv': '15', 'xvi': '16'}
EDITION = r'\b(?:the )?(ultimate edition|complete edition|game of the year edition|goty edition|directors cut|definitive edition|enhanced edition|special edition|scholarship edition|royal edition|windows edition)\b'


def normalize(title, editions=False):
    title = re.sub(r'\[(?:\d{4}|remake)\]', '', title, flags=re.I)
    title = title.replace('™', '').replace('®', '').replace('©', '')
    title = title.replace('&', ' and ').replace('·', ' ').replace('•', ' ')
    title = title.replace('Δ', ' Delta ').replace('δ', ' delta ')
    title = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode().lower()
    title = re.sub(r"['’]", '', title)
    title = re.sub(r'[^a-z0-9]+', ' ', title).strip()
    title = re.sub(r'^marvels\s+', '', title)
    if editions:
        title = re.sub(EDITION, '', title).strip()
    return ' '.join(ROMAN.get(word, word) for word in title.split())


def match_game(title, candidates, field, year=None, editions=False):
    """Prefer exact identities; never match a different sequel or release year."""
    target = normalize(title, editions)
    ranked = []
    for candidate in candidates:
        name = candidate.get(field, '')
        if not name:
            continue
        identity = normalize(name, editions)
        if identity != target:
            # Only tolerate minor spelling changes with the same words and numerals.
            if set(identity.split()) != set(target.split()):
                continue
            if SequenceMatcher(None, identity, target).ratio() < .93:
                continue
        release = candidate.get('release_world') or candidate.get('year')
        if year and release and abs(int(year) - int(release)) > 2:
            continue
        distance = abs(int(year) - int(release)) if year and release else 0
        ranked.append((identity == target, -distance, candidate))
    return max(ranked, key=lambda row: row[:2])[2] if ranked else None


def number(value, maximum=None):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        return None
    if maximum is not None and value > maximum:
        return None
    return value


def parse_hltb(item):
    if not item.get('game_id') or not item.get('game_name'):
        raise ValueError('HLTB: identidade ausente')
    def hours(field):
        seconds = number(item.get(field))
        return round(seconds / 3600, 1) if seconds else None
    return {'id': item['game_id'], 'name': item['game_name'],
            'url': f"https://howlongtobeat.com/game/{item['game_id']}",
            'main': hours('comp_main'), 'extras': hours('comp_plus'),
            'complete': hours('comp_100'),
            'samples': {key: item.get(field + '_count', 0) for key, field in
                        [('main', 'comp_main'), ('extras', 'comp_plus'), ('complete', 'comp_100')]},
            'platforms': [p.strip() for p in item.get('profile_platform', '').split(',') if p.strip()],
            'year': item.get('release_world')}


def parse_metacritic(payload):
    components = payload.get('components')
    if not isinstance(components, list):
        raise ValueError('Metacritic: resposta inválida')
    product = next((c.get('data', {}).get('item') for c in components
                    if c.get('data', {}).get('item', {}).get('title')), None)
    if not product or not product.get('slug'):
        raise ValueError('Metacritic: produto ausente')
    user = next((c['data']['item'].get('score') for c in components
                 if c.get('meta', {}).get('componentName') == 'user-score-summary'), None)
    platforms = product.get('platforms', [])
    pc = next((p for p in platforms if p.get('name') == 'PC'), {})
    return {'name': product['title'], 'slug': product['slug'],
            'url': f"https://www.metacritic.com/game/{product['slug']}/",
            'platform': product.get('platform'),
            'critic': number(product.get('criticScoreSummary', {}).get('score'), 100),
            'user': number(user, 10),
            'pcCritic': number(pc.get('criticScoreSummary', {}).get('score'), 100),
            'platforms': [p['name'] for p in platforms],
            'genres': [g['name'] for g in product.get('genres', [])],
            'releaseDate': product.get('releaseDate'), 'year': product.get('premiereYear')}


def parse_proton(payload):
    if payload.get('tier') not in {'platinum', 'gold', 'silver', 'bronze', 'borked', 'pending'}:
        raise ValueError('ProtonDB: classificação ausente')
    return {key: payload.get(key) for key in ['tier', 'trendingTier', 'confidence', 'total', 'score']}


def empty_steam_price(appid):
    return {'appid': int(appid), 'country': 'BR', 'currency': 'BRL',
            'initial': None, 'final': None, 'discountPercent': None,
            'isFree': False, 'status': 'unavailable',
            'url': f'https://store.steampowered.com/app/{appid}/?cc=br'}


def parse_steam_price_overview(price, appid):
    """The same price_overview schema is returned by single and batch requests."""
    if not isinstance(price, dict) or price.get('currency') != 'BRL':
        raise ValueError('Steam BR: preço retornado não está em BRL')
    initial, final, discount = (price.get(key) for key in ('initial', 'final', 'discount_percent'))
    if (any(not isinstance(value, int) or isinstance(value, bool) for value in (initial, final, discount))
            or initial < 0 or final < 0 or final > initial or not 0 <= discount <= 100):
        raise ValueError('Steam BR: valores de preço inválidos')
    return {**empty_steam_price(appid), 'initial': initial, 'final': final,
            'discountPercent': discount, 'status': 'available'}


def parse_steam_price(payload, appid):
    """Normalize the Brazilian Store price, keeping absent prices distinct from free."""
    entry = payload.get(str(appid)) if isinstance(payload, dict) else None
    if not isinstance(entry, dict) or not isinstance(entry.get('success'), bool):
        raise ValueError('Steam BR: resposta de preço inválida')
    result = empty_steam_price(appid)
    # A valid negative answer can mean a removed or region-unavailable listing.
    if not entry['success']:
        return result
    item = entry.get('data')
    if not isinstance(item, dict) or item.get('type') not in {'game', 'dlc'} or not item.get('name'):
        raise ValueError('Steam BR: dados do aplicativo ausentes')
    if item.get('steam_appid') is not None and str(item['steam_appid']) != str(appid):
        raise ValueError('Steam BR: aplicativo retornado difere do solicitado')
    if item.get('is_free') is True:
        return {**result, 'initial': 0, 'final': 0, 'discountPercent': 0,
                'isFree': True, 'status': 'free'}
    price = item.get('price_overview')
    if price is not None:
        return parse_steam_price_overview(price, appid)
    if item.get('release_date', {}).get('coming_soon') is True:
        result['status'] = 'coming_soon'
    return result


def parse_ign(item):
    names = item.get('metadata', {}).get('names', {})
    if not item.get('id') or not names.get('name'):
        raise ValueError('IGN: identidade ausente')
    releases = [release for region in item.get('objectRegions', []) for release in region.get('releases', [])]
    years = [int(release['date'][:4]) for release in releases if re.match(r'^\d{4}-', release.get('date') or '')]
    result = {'id': item['id'], 'slug': item['slug'], 'name': names['name'],
              'aliases': names.get('alt') or [], 'year': min(years) if years else None,
              'platforms': list(dict.fromkeys(p['name'] for release in releases for p in release.get('platformAttributes', []))),
              'url': 'https://www.ign.com/games/' + item['slug'], 'appid': None, 'hltb': None}
    hltb = item.get('hl2bData')
    if isinstance(hltb, dict) and hltb.get('id'):
        timings = hltb.get('time') or {}
        result['appid'] = int(hltb['steam_id']) if str(hltb.get('steam_id', '0')).isdigit() and int(hltb['steam_id']) > 0 else None
        result['hltb'] = parse_hltb({'game_id': hltb['id'], 'game_name': names['name'],
            'profile_platform': hltb.get('platforms', ''), 'release_world': result['year'],
            'comp_main': timings.get('main'), 'comp_plus': timings.get('main_plus'), 'comp_100': timings.get('completionist'),
            'comp_main_count': timings.get('main_count', 0), 'comp_plus_count': timings.get('main_plus_count', 0),
            'comp_100_count': timings.get('completionist_count', 0)})
    return result


def recommendation(device, method, status, reason, how):
    return dict(device=device, method=method, status=status, reason=reason, how=how)


def recommend(game, steam=None, proton=None, deck=None, emulation=None, platforms=None):
    steam, proton, deck, emulation = steam or {}, proton or {}, deck or {}, emulation or {}
    platforms = platforms or []
    grade = game.get('dg')
    portable = grade in {'A', 'B', 'C'} or (grade == 'D' and game.get('plat') == 'Steam Deck')
    if steam.get('comingSoon'):
        return recommendation('Aguardando', 'Versão PC anunciada', 'waiting',
                              'A Steam ainda marca esta versão como não lançada.',
                              'A compatibilidade será consultada novamente nas próximas atualizações.')
    if steam:
        native = steam.get('linux', False)
        tier = proton.get('trendingTier') or proton.get('tier')
        supported = deck.get('category') in {2, 3}
        if not native and tier == 'borked':
            return recommendation('PC Windows', 'Windows', 'fallback',
                                  'ProtonDB indica Borked: Linux/SteamOS não é uma rota confirmada.',
                                  'Jogar no PC com Windows. Consultar os relatos para distinguir campanha e online.')
        method = 'Nativo Linux' if native else 'Proton'
        working = native or tier in {'platinum', 'gold', 'silver'} or supported
        if not portable and grade not in {'D', 'F'}:
            portable = supported
        if working:
            device = 'Steam Deck' if portable and (supported or native or tier in {'platinum', 'gold'}) else 'PC Linux'
            evidence = 'versão nativa Linux' if native else f'ProtonDB {tier.title()}' if tier else 'selo da Valve'
            detail = ('Preferência pelo portátil com base na referência anterior de desempenho.'
                      if grade in {'A', 'B', 'C', 'D'} else 'Valve confirma compatibilidade no Deck; conferir os relatos de desempenho.') if device == 'Steam Deck' else 'PC oferece mais margem de desempenho; a API não mede fps.'
            return recommendation(device, method, 'ready', f'{evidence}; {detail}',
                                  'Instalar pela Steam.' if native else
                                  'Instalar pela Steam e habilitar Steam Play. Consultar os relatos do ProtonDB para a versão de Proton e ajustes por dispositivo.')
        return recommendation('PC Linux', method, 'check',
                              f'ProtonDB {tier.title()}: exige conferir os relatos.' if tier else
                              'Versão PC encontrada; compatibilidade Linux ainda sem confirmação.',
                              'Testar pela Steam com Proton e consultar os relatos. Não há garantia de funcionamento ou fps.')
    if emulation:
        emulator = emulation['emulator']
        if emulation.get('verified') and emulation.get('status') != 'Playable':
            return recommendation('Aguardando', f'Emulação · {emulator}', 'waiting',
                                  f"A base do {emulator} informa {emulation.get('status')}; não confirma um jogo completo jogável.",
                                  'Acompanhar a fonte de compatibilidade; o estado será atualizado automaticamente.')
        device = 'Steam Deck' if portable and emulator not in {'RPCS3', 'shadPS4', 'Xenia Canary'} else 'PC Linux'
        verified = emulation.get('verified', False)
        return recommendation(device, f'Emulação · {emulator}', 'ready' if verified else 'check',
                              f'{emulator}: Playable na base de compatibilidade; o desempenho depende do hardware.' if verified else
                              f'{emulator} é uma rota candidata. Falta confirmação atual por jogo e por dispositivo.',
                              f'Configurar {emulator} com resolução nativa e consultar a fonte do jogo antes de aumentar a resolução. '
                              + ('No Linux, Xenia via Proton requer validação adicional.' if emulator == 'Xenia Canary' else
                                 'No Deck, adicionar o emulador ao modo Jogo (EmuDeck quando disponível).'))
    pc = 'PC' in platforms or game.get('plat') in {'PC', 'Steam Deck', 'Windows'}
    if pc:
        blocked = game.get('plat') == 'Windows' or re.search(r'bloqueia Linux|bloqueou Linux|só Windows|anticheat.*Linux', game.get('dset', ''), re.I)
        if blocked:
            return recommendation('PC Windows', 'Windows', 'fallback',
                                  'A referência anterior indica bloqueio de Linux; ainda sem confirmação automática de uma alternativa.',
                                  'Usar a versão PC no Windows e consultar a fonte de compatibilidade.')
        return recommendation('Steam Deck' if portable else 'PC Linux', 'Proton / Lutris', 'check',
                              'Versão PC fora da Steam ou sem correspondência segura; funcionamento no Linux a confirmar.',
                              'Instalar pelo launcher da loja via Lutris, Heroic ou Bottles; consultar os ajustes específicos do jogo.')
    return recommendation('Aguardando', 'Sem rota PC/Deck confirmada', 'waiting',
                          'Não foi encontrada uma versão PC nem emulação jogável confirmada para esta edição.',
                          'Aguardar port ou avanço da emulação. Streaming de console só é alternativa se houver acesso ao console.')
