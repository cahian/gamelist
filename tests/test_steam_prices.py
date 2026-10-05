import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from game_metadata import parse_steam_price
from refresh import Cache, Providers, enrich_prices


def store_response(appid=123, **fields):
    return {str(appid): {'success': True, 'data': {
        'type': 'game', 'name': 'Example', 'steam_appid': appid, 'is_free': False,
        'release_date': {'coming_soon': False}, **fields}}}


def paid_price(currency='BRL'):
    return {'currency': currency, 'initial': 9990, 'final': 2497, 'discount_percent': 75}


class SteamPriceParsingTests(unittest.TestCase):
    def test_discount_is_preserved_in_integer_cents(self):
        result = parse_steam_price(store_response(price_overview=paid_price()), 123)
        self.assertEqual((result['initial'], result['final'], result['discountPercent']), (9990, 2497, 75))
        self.assertEqual((result['status'], result['currency'], result['country']), ('available', 'BRL', 'BR'))
        self.assertFalse(result['isFree'])

    def test_only_explicitly_free_games_are_free(self):
        free = parse_steam_price(store_response(is_free=True), 123)
        missing = parse_steam_price(store_response(), 123)
        self.assertEqual((free['status'], free['initial'], free['final'], free['isFree']), ('free', 0, 0, True))
        self.assertEqual(missing['status'], 'unavailable')
        self.assertIsNone(missing['final'])
        self.assertFalse(missing['isFree'])

    def test_free_promotion_does_not_reclassify_a_paid_game(self):
        result = parse_steam_price(store_response(price_overview={
            'currency': 'BRL', 'initial': 990, 'final': 0, 'discount_percent': 100}), 123)
        self.assertEqual((result['status'], result['final'], result['isFree']), ('available', 0, False))

    def test_region_unavailable_and_unreleased_are_distinct(self):
        unavailable = parse_steam_price({'123': {'success': False}}, 123)
        upcoming = parse_steam_price(store_response(release_date={'coming_soon': True}), 123)
        self.assertEqual(unavailable['status'], 'unavailable')
        self.assertEqual(upcoming['status'], 'coming_soon')
        self.assertIsNone(upcoming['final'])

    def test_preorder_with_price_remains_available(self):
        result = parse_steam_price(store_response(release_date={'coming_soon': True},
                                                 price_overview=paid_price()), 123)
        self.assertEqual(result['status'], 'available')

    def test_wrong_currency_identity_and_malformed_prices_raise(self):
        for response in [store_response(price_overview=paid_price('USD')),
                         store_response(steam_appid=456), {}, {'123': {'success': True}},
                         store_response(price_overview={'currency': 'BRL', 'final': 999}),
                         store_response(price_overview={**paid_price(), 'final': -1}),
                         store_response(price_overview={**paid_price(), 'final': 9.99})]:
            with self.subTest(response=response), self.assertRaises(ValueError):
                parse_steam_price(response, 123)


class SteamPriceRefreshTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cache = Cache(Path(self.directory.name) / 'providers.json')
        self.providers = Providers(self.cache)
        self.calls = []

    def response(self, url, **kwargs):
        self.calls.append(url)
        query = parse_qs(urlparse(url).query)
        return store_response(int(query['appids'][0]), price_overview=paid_price())

    def test_dlc_requests_its_own_brazilian_price_and_no_other_provider(self):
        self.providers.request = self.response
        previous = {'name': 'Expansion', 'steam': {'appid': 123, 'compatAppid': 456},
                    'critic': 90, 'sources': {'steam': {'data': {'appid': 123}, 'status': 'ok',
                                                     'updatedAt': '2020-01-01T00:00:00+00:00'}}}
        result = enrich_prices({'name': 'Expansion', 'critic': 80}, previous, self.providers)
        self.assertEqual(len(self.calls), 1)
        self.assertIn('appids=123', self.calls[0])
        self.assertIn('cc=br', self.calls[0])
        self.assertEqual(result['price']['appid'], 123)
        self.assertIn('steamPrice:123:br', self.cache.values)
        self.assertEqual(result['sources']['steam'], previous['sources']['steam'])
        self.assertNotIn('steamPrice', previous['sources'])
        self.assertEqual(result['critic'], 90)

    def test_no_steam_mapping_does_not_invent_a_price_or_call_api(self):
        self.providers.request = self.response
        result = enrich_prices({'name': 'Console exclusive'}, {}, self.providers)
        self.assertIsNone(result['price'])
        self.assertNotIn('steamPrice', result['sources'])
        self.assertEqual(self.calls, [])

    def test_old_metadata_snapshot_without_price_must_fetch(self):
        self.providers.request = self.response
        stamp = datetime.now(timezone.utc).isoformat()
        previous = {'name': 'Example', 'steam': {'appid': 123}, 'sources': {
            'steam': {'status': 'ok', 'data': {'appid': 123}, 'updatedAt': stamp}}}
        self.cache.seed([previous])
        result = enrich_prices({'name': 'Example'}, previous, self.providers)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result['sources']['steamPrice']['status'], 'ok')

    def test_fresh_price_snapshot_seeds_the_region_cache(self):
        stamp = datetime.now(timezone.utc).isoformat()
        data = parse_steam_price(store_response(price_overview=paid_price()), 123)
        previous = {'name': 'Example', 'steam': {'appid': 123}, 'sources': {
            'steamPrice': {'status': 'ok', 'data': data, 'updatedAt': stamp}}}
        self.cache.seed([previous])
        self.providers.request = lambda *args, **kwargs: self.fail('Fresh price should be cached')
        result = enrich_prices({'name': 'Example'}, previous, self.providers)
        self.assertEqual(result['sources']['steamPrice']['updatedAt'], stamp)
        self.assertEqual(result['price'], data)

    def test_currency_error_retains_price_and_original_timestamp(self):
        stamp = '2020-01-01T00:00:00+00:00'
        data = parse_steam_price(store_response(price_overview=paid_price()), 123)
        previous = {'name': 'Example', 'steam': {'appid': 123}, 'sources': {
            'steamPrice': {'status': 'ok', 'data': data, 'updatedAt': stamp}}}
        self.cache.seed([previous])
        self.providers.request = lambda *args, **kwargs: store_response(price_overview=paid_price('USD'))
        result = enrich_prices({'name': 'Example'}, previous, self.providers)
        self.assertEqual(result['price'], data)
        self.assertEqual(result['sources']['steamPrice']['status'], 'stale')
        self.assertEqual(result['sources']['steamPrice']['updatedAt'], stamp)
        self.assertIn('attemptedAt', result['sources']['steamPrice'])
        self.cache.save()
        saved = json.loads(self.cache.path.read_text())['steamPrice:123:br']
        self.assertEqual(saved['updatedAt'], stamp)

    def test_daily_price_refresh_has_margin_below_twenty_four_hours(self):
        stamp = (datetime.now(timezone.utc) - timedelta(hours=23, minutes=30)).isoformat()
        data = parse_steam_price(store_response(price_overview=paid_price()), 123)
        previous = {'name': 'Example', 'steam': {'appid': 123}, 'sources': {
            'steamPrice': {'status': 'ok', 'data': data, 'updatedAt': stamp}}}
        self.cache.seed([previous])
        self.providers.request = self.response
        result = enrich_prices({'name': 'Example'}, previous, self.providers)
        self.assertEqual(len(self.calls), 1)
        self.assertNotEqual(result['sources']['steamPrice']['updatedAt'], stamp)

    def test_stale_snapshot_retries_and_keeps_last_good_price_if_still_offline(self):
        stamp = '2020-01-01T00:00:00+00:00'
        data = parse_steam_price(store_response(price_overview=paid_price()), 123)
        previous = {'name': 'Example', 'steam': {'appid': 123}, 'sources': {
            'steamPrice': {'status': 'stale', 'data': data, 'updatedAt': stamp}}}
        self.cache.seed([previous])
        def offline(*args, **kwargs):
            self.calls.append('offline')
            raise OSError('offline')
        self.providers.request = offline
        result = enrich_prices({'name': 'Example'}, previous, self.providers)
        self.assertEqual(self.calls, ['offline'])
        self.assertEqual(result['price'], data)
        self.assertEqual(result['sources']['steamPrice']['status'], 'stale')
        self.assertEqual(result['sources']['steamPrice']['updatedAt'], stamp)

    def test_failure_without_old_price_has_no_updated_timestamp(self):
        self.providers.request = lambda *args, **kwargs: None
        result = enrich_prices({'name': 'Example'}, {'steam': {'appid': 123}}, self.providers)
        self.assertIsNone(result['price'])
        self.assertEqual(result['sources']['steamPrice']['status'], 'error')
        self.assertIsNone(result['sources']['steamPrice']['updatedAt'])

    def test_different_app_does_not_inherit_an_old_price_on_failure(self):
        self.providers.request = lambda *args, **kwargs: None
        previous = {'steam': {'appid': 456}, 'sources': {'steamPrice': {'status': 'ok',
            'data': parse_steam_price(store_response(price_overview=paid_price()), 123),
            'updatedAt': '2020-01-01T00:00:00+00:00'}}}
        self.cache.seed([previous])
        result = enrich_prices({'name': 'Different app'}, previous, self.providers)
        self.assertIsNone(result['price'])
        self.assertEqual(result['sources']['steamPrice']['status'], 'error')


if __name__ == '__main__':
    unittest.main()
