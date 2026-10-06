from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from game_metadata import parse_steam_price, parse_steam_price_overview
from refresh_prices import load_prices, refresh_prices, save_prices


def overview(currency='BRL'):
    return {'currency': currency, 'initial': 10000, 'final': 2500, 'discount_percent': 75}


def source(appid, status='available', age_hours=1):
    data = parse_steam_price_overview(overview(), appid)
    if status != 'available':
        data.update(status=status, initial=0 if status == 'free' else None,
                    final=0 if status == 'free' else None,
                    isFree=status == 'free', discountPercent=0 if status == 'free' else None)
    stamp = (datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat()
    return {'data': data, 'updatedAt': stamp, 'status': 'ok'}


def game(appid, old=None, compat_appid=None):
    return {'name': f'Game {appid}', 'steam': {'appid': appid, 'compatAppid': compat_appid},
            'sources': {'steamPrice': old} if old else {}}


class FakeProvider:
    def __init__(self, entries=None, details=None, failure=None):
        self.entries = entries or {}
        self.details = details or {}
        self.failure = failure
        self.batch_calls = []
        self.detail_calls = []

    def request(self, url):
        query = parse_qs(urlparse(url).query)
        self.batch_calls.append(query)
        if self.failure:
            raise self.failure
        return {appid: self.entries.get(appid, {'success': True, 'data': {'price_overview': overview()}})
                for appid in query['appids'][0].split(',')}

    def steam_price(self, appid):
        self.detail_calls.append(appid)
        response = self.details[appid]
        if isinstance(response, Exception):
            raise response
        return parse_steam_price({str(appid): response}, appid)


class PriceSnapshotTests(unittest.TestCase):
    def test_batches_twenty_apps_deduplicates_and_uses_dlc_identity(self):
        provider = FakeProvider()
        games = [game(appid) for appid in range(1, 22)] + [game(21, compat_appid=999)]
        snapshot, report = refresh_prices(games, provider=provider)
        self.assertEqual(sorted(len(q['appids'][0].split(',')) for q in provider.batch_calls), [1, 20])
        self.assertTrue(all(q['cc'] == ['br'] and q['filters'] == ['price_overview'] for q in provider.batch_calls))
        self.assertEqual(len(snapshot['prices']), 21)
        self.assertNotIn('999', snapshot['prices'])
        self.assertEqual(snapshot['stats']['batchRequests'], 2)
        self.assertEqual(snapshot['stats']['detailRequests'], 0)
        self.assertEqual(snapshot['stats']['refreshed'], 21)
        self.assertFalse(report['allFailed'])

    def test_default_fetches_fresh_paid_price_even_with_recent_snapshot(self):
        old = source(1, age_hours=.01)
        provider = FakeProvider()
        snapshot, _ = refresh_prices([game(1, old)], provider=provider)
        self.assertEqual(len(provider.batch_calls), 1)
        self.assertNotEqual(snapshot['prices']['1']['updatedAt'], old['updatedAt'])

    def test_optional_max_age_skips_requests_without_refreshing_source_timestamp(self):
        old = source(1, age_hours=.1)
        provider = FakeProvider()
        snapshot, report = refresh_prices([game(1, old)], provider=provider, max_age=3600)
        self.assertEqual(provider.batch_calls, [])
        self.assertEqual(snapshot['prices']['1'], old)
        self.assertEqual(snapshot['stats']['reused'], 1)
        self.assertNotIn('resolved', snapshot['stats'])
        self.assertTrue(report['skipped'])
        self.assertFalse(report['allFailed'])

    def test_empty_batch_uses_full_details_to_distinguish_free_upcoming_and_absent(self):
        empty = {'success': True, 'data': []}
        base = {'type': 'game', 'name': 'Example', 'is_free': False}
        provider = FakeProvider(entries={'1': empty, '2': empty, '3': {'success': False}}, details={
            1: {'success': True, 'data': {**base, 'is_free': True}},
            2: {'success': True, 'data': {**base, 'release_date': {'coming_soon': True}}},
            3: {'success': False}})
        snapshot, _ = refresh_prices([game(1), game(2), game(3)], provider=provider)
        self.assertEqual([snapshot['prices'][str(i)]['data']['status'] for i in (1, 2, 3)],
                         ['free', 'coming_soon', 'unavailable'])
        self.assertEqual(provider.detail_calls, [1, 2, 3])
        self.assertEqual(snapshot['stats']['detailRequests'], 3)

    def test_recent_no_price_classification_keeps_original_timestamp(self):
        old = source(1, status='free', age_hours=22)
        provider = FakeProvider(entries={'1': {'success': True, 'data': []}})
        snapshot, report = refresh_prices([game(1, old)], provider=provider)
        self.assertEqual(len(provider.batch_calls), 1)
        self.assertEqual(provider.detail_calls, [])
        self.assertEqual(snapshot['prices']['1'], old)
        self.assertEqual(snapshot['stats']['refreshed'], 0)
        self.assertEqual(snapshot['stats']['reused'], 1)
        self.assertFalse(report['allFailed'])

    def test_price_appearing_overrides_cached_upcoming_classification(self):
        old = source(1, status='coming_soon', age_hours=.1)
        snapshot, _ = refresh_prices([game(1, old)], provider=FakeProvider())
        self.assertEqual(snapshot['prices']['1']['data']['status'], 'available')
        self.assertNotEqual(snapshot['prices']['1']['updatedAt'], old['updatedAt'])

    def test_expired_classification_and_forced_classification_use_full_detail(self):
        for age, maximum in [(23.5, 23 * 3600), (.1, 0)]:
            with self.subTest(age=age, maximum=maximum):
                old = source(1, status='free', age_hours=age)
                provider = FakeProvider(entries={'1': {'success': True, 'data': []}}, details={
                    1: {'success': True, 'data': {'type': 'game', 'name': 'Example', 'is_free': True}}})
                snapshot, _ = refresh_prices([game(1, old)], provider=provider, classification_max_age=maximum)
                self.assertEqual(provider.detail_calls, [1])
                self.assertNotEqual(snapshot['prices']['1']['updatedAt'], old['updatedAt'])

    def test_failed_batch_retains_valid_old_data_and_date_and_does_not_fan_out(self):
        old = source(1)
        provider = FakeProvider(failure=OSError('offline'))
        snapshot, report = refresh_prices([game(1, old), game(2)], provider=provider)
        self.assertEqual(snapshot['prices']['1']['data'], old['data'])
        self.assertEqual(snapshot['prices']['1']['updatedAt'], old['updatedAt'])
        self.assertEqual(snapshot['prices']['1']['status'], 'stale')
        self.assertEqual(snapshot['prices']['2']['status'], 'error')
        self.assertIsNone(snapshot['prices']['2']['updatedAt'])
        self.assertEqual(provider.detail_calls, [])
        self.assertTrue(report['allFailed'])

    def test_currency_mismatch_is_stale_and_partial_success_can_be_saved(self):
        old = source(1)
        provider = FakeProvider(entries={'1': {'success': True, 'data': {'price_overview': overview('USD')}}})
        snapshot, report = refresh_prices([game(1, old), game(2)], provider=provider)
        self.assertEqual(snapshot['prices']['1']['status'], 'stale')
        self.assertEqual(snapshot['prices']['1']['updatedAt'], old['updatedAt'])
        self.assertEqual(snapshot['prices']['2']['status'], 'ok')
        self.assertFalse(report['allFailed'])
        self.assertEqual(snapshot['stats']['stale'], 1)

    def test_failed_full_fallback_does_not_assume_free_or_refresh_old_timestamp(self):
        old = source(1, status='available')
        provider = FakeProvider(entries={'1': {'success': True, 'data': []}}, details={1: OSError('offline')})
        snapshot, report = refresh_prices([game(1, old)], provider=provider)
        self.assertEqual(snapshot['prices']['1']['data']['status'], 'available')
        self.assertFalse(snapshot['prices']['1']['data']['isFree'])
        self.assertEqual(snapshot['prices']['1']['updatedAt'], old['updatedAt'])
        self.assertTrue(report['allFailed'])

    def test_dedicated_snapshot_beats_older_data_js_seed(self):
        older = source(1, age_hours=5)
        newer = source(1, age_hours=.2)
        newer['data'] = {**newer['data'], 'final': 1000, 'discountPercent': 90}
        snapshot, _ = refresh_prices([game(1, older)], {'prices': {'1': newer}},
                                     provider=FakeProvider(), max_age=3600)
        self.assertEqual(snapshot['prices']['1'], newer)

    def test_all_failed_preserves_file_bytes_but_reports_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'prices.json'
            diagnostic = Path(directory) / 'prices-report.json'
            original = '{"prior":"unchanged"}\n'
            output.write_text(original)
            snapshot, report = refresh_prices([game(1, source(1))], provider=FakeProvider(failure=OSError('offline')))
            self.assertFalse(save_prices(snapshot, report, output, diagnostic))
            self.assertEqual(output.read_text(), original)
            self.assertTrue(json.loads(diagnostic.read_text())['allFailed'])

    def test_partial_snapshot_roundtrips_and_contains_independent_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'prices.json'
            diagnostic = Path(directory) / 'prices-report.json'
            provider = FakeProvider(entries={'2': {'success': True, 'data': {'price_overview': overview('USD')}}})
            snapshot, report = refresh_prices([game(1), game(2, source(2))], provider=provider)
            self.assertTrue(save_prices(snapshot, report, output, diagnostic))
            self.assertEqual(load_prices(output), snapshot)
            self.assertEqual((snapshot['version'], snapshot['country'], snapshot['currency']), (1, 'BR', 'BRL'))


if __name__ == '__main__':
    unittest.main()
