#!/usr/bin/env python3
"""Refresh an independent Brazilian Steam price snapshot. Python 3.11+, no keys."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
from pathlib import Path
import time
from urllib.parse import urlencode

from game_metadata import parse_steam_price_overview
from refresh import ROOT, STEAM_PRICE_TTL, Providers, atomic_json, now, read_snapshot, valid_price_snapshot


def timestamp(source):
    try:
        return datetime.fromisoformat(source.get('updatedAt') or '').timestamp()
    except (TypeError, ValueError):
        return 0


def recent(source, max_age):
    age = time.time() - timestamp(source)
    return source.get('status') == 'ok' and 0 <= age < max_age


def known_appids(games):
    return sorted({int(appid) for game in games
                   if (appid := (game.get('steam') or {}).get('appid'))
                   and str(appid).isdigit() and int(appid) > 0})


def seed_prices(games, snapshot):
    """A committed data.js is the bootstrap; the newest valid per-app source wins."""
    result = {}
    for game in games:
        appid = (game.get('steam') or {}).get('appid')
        source = game.get('sources', {}).get('steamPrice') or {}
        if valid_price_snapshot(source.get('data'), appid) and timestamp(source):
            key = str(appid)
            if timestamp(source) > timestamp(result.get(key, {})):
                result[key] = dict(source)
    for appid, source in snapshot.get('prices', {}).items():
        if (str(appid).isdigit() and int(appid) > 0 and isinstance(source, dict)
                and valid_price_snapshot(source.get('data'), appid)
                and timestamp(source) >= timestamp(result.get(appid, {}))):
            result[appid] = dict(source)
    return result


def batch_price(payload, appid):
    """Empty filtered data is ambiguous; only full details can classify it."""
    item = payload.get(str(appid))
    if item is None:
        return None
    if not isinstance(item, dict) or not isinstance(item.get('success'), bool):
        raise ValueError('Steam BR: resposta em lote inválida')
    if not item['success']:
        return None
    data = item.get('data')
    if data == [] or data == {}:
        return None
    if not isinstance(data, dict):
        raise ValueError('Steam BR: dados de preço em lote ausentes')
    if 'price_overview' not in data:
        return None
    return parse_steam_price_overview(data['price_overview'], appid)


def failed_source(previous, error):
    return {'data': previous.get('data'), 'updatedAt': previous.get('updatedAt'),
            'status': 'stale' if previous.get('data') is not None else 'error',
            'attemptedAt': now(), 'error': str(error)[:200]}


def refresh_batch(appids, previous, provider, classification_max_age):
    sources = {}
    counts = {'refreshed': 0, 'reused': 0, 'resolved': 0, 'batchRequests': 1, 'detailRequests': 0}
    url = 'https://store.steampowered.com/api/appdetails?' + urlencode({
        'appids': ','.join(map(str, appids)), 'cc': 'br', 'filters': 'price_overview'})
    try:
        payload = provider.request(url)
        if not isinstance(payload, dict):
            raise ValueError('Steam BR: lote de preços inválido')
    except Exception as error:
        return {str(appid): failed_source(previous.get(str(appid), {}), error) for appid in appids}, counts
    for appid in appids:
        key = str(appid)
        old = previous.get(key, {})
        try:
            data = batch_price(payload, appid)
            if data is None:
                # A free/unreleased/delisted app may become paid: every run still
                # queries its batch price. Only its ambiguous classification is cached.
                if ((old.get('data') or {}).get('status') in {'free', 'unavailable', 'coming_soon'}
                        and recent(old, classification_max_age)):
                    sources[key] = dict(old)
                    counts['reused'] += 1
                    counts['resolved'] += 1
                    continue
                counts['detailRequests'] += 1
                data = provider.steam_price(appid)
            sources[key] = {'data': data, 'updatedAt': now(), 'status': 'ok'}
            counts['refreshed'] += 1
            counts['resolved'] += 1
        except Exception as error:
            sources[key] = failed_source(old, error)
    return sources, counts


def refresh_prices(games, previous=None, provider=None, *, batch_size=20, workers=4,
                   max_age=0, classification_max_age=STEAM_PRICE_TTL, limit=None):
    previous = previous or {}
    provider = provider or Providers(None)
    games = list(games)
    appids = known_appids(games)
    sources = {key: value for key, value in seed_prices(games, previous).items() if int(key) in appids}
    selected = appids[:limit] if limit is not None else appids
    due = [appid for appid in selected if not recent(sources.get(str(appid), {}), max_age)]
    counts = {'apps': len(appids), 'selected': len(selected), 'requested': len(due),
              'refreshed': 0, 'reused': len(selected) - len(due),
              'resolved': 0, 'batchRequests': 0, 'detailRequests': 0}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(refresh_batch, due[start:start + batch_size], sources,
                               provider, classification_max_age)
                   for start in range(0, len(due), batch_size)]
        for future in as_completed(futures):
            updated, batch_counts = future.result()
            sources.update(updated)
            for key, count in batch_counts.items():
                counts[key] += count
    resolved = counts.pop('resolved')
    all_failed = bool(due) and resolved == 0
    for status in ('available', 'free', 'unavailable', 'coming_soon'):
        counts[status] = sum((source.get('data') or {}).get('status') == status for source in sources.values())
    for status in ('stale', 'error'):
        counts[status] = sum(source.get('status') == status for source in sources.values())
    generated = now() if due or not previous.get('generatedAt') else previous['generatedAt']
    snapshot = {'version': 1, 'generatedAt': generated, 'country': 'BR', 'currency': 'BRL',
                'prices': dict(sorted(sources.items(), key=lambda item: int(item[0]))), 'stats': counts}
    report = {'attemptedAt': now(), 'allFailed': all_failed, 'skipped': not due, 'stats': counts,
              'errors': [{'appid': int(appid), 'status': source['status'], 'error': source.get('error')}
                         for appid, source in sources.items() if source['status'] != 'ok']}
    return snapshot, report


def load_prices(path):
    if not path.exists():
        return {}
    result = json.loads(path.read_text())
    if (not isinstance(result, dict) or result.get('version') != 1 or result.get('country') != 'BR'
            or result.get('currency') != 'BRL' or not isinstance(result.get('prices'), dict)):
        raise ValueError('Snapshot de preços inválido; arquivo anterior preservado')
    return result


def save_prices(snapshot, report, output_path, report_path):
    atomic_json(report_path, report)
    if report['allFailed']:
        return False
    atomic_json(output_path, snapshot)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true', help='Refresh batch prices and all full classifications')
    parser.add_argument('--max-age', type=int, default=0, metavar='SECONDS',
                        help='Reuse successful prices younger than this age; default 0 fetches every run')
    parser.add_argument('--classification-max-age', type=int, default=STEAM_PRICE_TTL, metavar='SECONDS',
                        help='Cache full free/upcoming/unavailable classifications; default 23h')
    parser.add_argument('--batch-size', type=int, default=20)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--limit', type=int, help='Refresh only the first N distinct Steam apps (smoke test)')
    parser.add_argument('--output', type=Path, default=ROOT / 'prices.json')
    parser.add_argument('--report', type=Path, default=ROOT / 'prices-report.json')
    args = parser.parse_args()
    if (args.max_age < 0 or args.classification_max_age < 0 or not 1 <= args.batch_size <= 20
            or not 1 <= args.workers <= 8 or args.limit is not None and args.limit < 1):
        parser.error('Invalid age, batch size (1–20), workers (1–8), or limit')
    snapshot, report = refresh_prices(read_snapshot(ROOT / 'data.js').values(), load_prices(args.output),
        batch_size=args.batch_size, workers=args.workers, max_age=0 if args.force else args.max_age,
        classification_max_age=0 if args.force else args.classification_max_age, limit=args.limit)
    saved = save_prices(snapshot, report, args.output, args.report)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if not saved:
        raise SystemExit('Nenhum preço pôde ser consultado; snapshot anterior preservado')


if __name__ == '__main__':
    main()
