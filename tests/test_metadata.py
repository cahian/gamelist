import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import game_metadata as gm
from refresh import Cache


class MetadataTests(unittest.TestCase):
    def test_matching_does_not_confuse_sequels_or_soundtracks(self):
        candidates = [{'name': 'Control: Resonant', 'id': 2},
                      {'name': 'Control Soundtrack', 'id': 3},
                      {'name': 'Control Ultimate Edition', 'id': 4}]
        self.assertEqual(gm.match_game('Control', candidates, 'name', editions=True)['id'], 4)
        self.assertIsNone(gm.match_game('Control', candidates[:2], 'name', editions=True))

    def test_matching_distinguishes_original_and_remake_by_year(self):
        candidates = [{'game_name': "Demon's Souls", 'release_world': 2020},
                      {'game_name': "Demon's Souls", 'release_world': 2009}]
        self.assertEqual(gm.match_game("Demon's Souls [2009]", candidates, 'game_name',
                                      year=2009)['release_world'], 2009)
        self.assertIsNone(gm.match_game('Fable', [{'game_name': 'Fable', 'release_world': 2004}],
                                         'game_name', year=2026))

    def test_trademarks_punctuation_and_roman_numerals(self):
        candidates = [{'name': 'FINAL FANTASY VII REMAKE INTERGRADE', 'id': 1}]
        self.assertIsNotNone(gm.match_game('Final Fantasy 7 Remake Intergrade', candidates, 'name'))
        self.assertIsNotNone(gm.match_game('Batman: Arkham Knight',
                                         [{'name': 'Batman™: Arkham Knight'}], 'name'))

    def test_directors_cut_and_ampersands_match_store_names(self):
        self.assertIsNotNone(gm.match_game('Ghost of Tsushima',
            [{'name': "Ghost of Tsushima DIRECTOR'S CUT"}], 'name', editions=True))
        self.assertEqual(gm.normalize('Mario & Luigi'), gm.normalize('Mario and Luigi'))

    def test_brand_prefix_and_delta_symbol_do_not_hide_pc_ports(self):
        self.assertIsNotNone(gm.match_game('Spider-Man Remastered',
            [{'name': 'Marvel’s Spider-Man Remastered'}], 'name', editions=True))
        self.assertEqual(gm.normalize('Metal Gear Solid Δ: Snake Eater'),
                         gm.normalize('Metal Gear Solid Delta: Snake Eater'))

    def test_enhanced_pc_edition_is_found_without_matching_a_sequel(self):
        self.assertIsNotNone(gm.match_game('Divinity: Original Sin II',
            [{'name': 'Divinity: Original Sin 2 - Definitive Edition'}], 'name', editions=True))

    def test_ign_linked_hltb_data_preserves_times_and_steam_id(self):
        result = gm.parse_ign({'id': 'ign-id', 'slug': 'control',
            'metadata': {'names': {'name': 'Control', 'alt': []}},
            'objectRegions': [{'releases': [{'date': '2019-08-27',
                                           'platformAttributes': [{'name': 'PC'}]}]}],
            'hl2bData': {'id': 57507, 'steam_id': 870780, 'platforms': 'PC',
                         'time': {'main': 42084, 'main_plus': 69231, 'completionist': 104256}}})
        self.assertEqual(result['appid'], 870780)
        self.assertEqual(result['hltb']['main'], 11.7)
        self.assertEqual(result['year'], 2019)

    def test_ign_rejects_wrong_title_or_release_year(self):
        provider = __import__('refresh').Providers(None)
        provider.request = lambda *args, **kwargs: {'data': {'objectSelectByTypeAndSlug': {
            'id': 'remake', 'slug': 'demons-souls',
            'metadata': {'names': {'name': "Demon's Souls"}},
            'objectRegions': [{'releases': [{'date': '2020-11-12',
                                           'platformAttributes': [{'name': 'PlayStation 5'}]}]}]}}}
        self.assertIsNone(provider.ign({'name': "Demon's Souls [2009]", 'year': 2009,
                                       'mslug': 'demons-souls'}))

    def test_dlc_uses_base_game_for_compatibility_and_keeps_its_own_title(self):
        provider = __import__('refresh').Providers(None)
        provider.request = lambda *args, **kwargs: {'2138330': {'success': True, 'data': {
            'type': 'dlc', 'name': 'Cyberpunk 2077: Phantom Liberty',
            'fullgame': {'appid': '1091500', 'name': 'Cyberpunk 2077'},
            'platforms': {'linux': False}, 'release_date': {'coming_soon': False}}}}
        result = provider.steam_details(2138330)
        self.assertIsNotNone(result)
        self.assertEqual(result['compatAppid'], 1091500)
        self.assertEqual(result['appid'], 2138330)

    def test_ign_follows_its_canonical_redirect_and_validates_title(self):
        provider = __import__('refresh').Providers(None)
        def response(url, **kwargs):
            from urllib.parse import parse_qs, urlparse
            args = parse_qs(urlparse(url).query)
            slug = json.loads(args['variables'][0])['slug']
            if slug == 'marvels-spider-man-remastered':
                return {'errors': [{'message': '301: /games/spider-man-remastered',
                                    'extensions': {'code': 'REDIRECT'}}],
                        'data': {'objectSelectByTypeAndSlug': None}}
            return {'data': {'objectSelectByTypeAndSlug': {'id': 'id', 'slug': 'spider-man-remastered',
                'metadata': {'names': {'name': 'Spider-Man Remastered'}}, 'objectRegions': []}}}
        provider.request = response
        result = provider.ign({'name': 'Spider-Man Remastered', 'year': 2022,
                               'mslug': 'marvels-spider-man-remastered'})
        self.assertEqual(result['slug'], 'spider-man-remastered')

    def test_store_reissue_title_matches_the_original_without_manual_id(self):
        self.assertIsNotNone(gm.match_game('Grand Theft Auto IV',
            [{'name': 'Grand Theft Auto IV: The Complete Edition'}], 'name', editions=True))

    def test_remaster_does_not_match_original_silently(self):
        self.assertIsNone(gm.match_game('Paper Mario: The Thousand-Year Door [Remake]',
                                       [{'game_name': 'Paper Mario: The Thousand-Year Door',
                                         'release_world': 2004}], 'game_name', year=2024))

    def test_completion_times_are_hours_and_unknown_is_null(self):
        result = gm.parse_hltb({'game_id': 42, 'game_name': 'Example', 'comp_main': 5400,
                               'comp_plus': 0, 'comp_100': 10800,
                               'profile_platform': 'PC, PlayStation 3'})
        self.assertEqual(result['main'], 1.5)
        self.assertIsNone(result['extras'])
        self.assertEqual(result['complete'], 3)
        self.assertEqual(result['platforms'], ['PC', 'PlayStation 3'])

    def test_metacritic_keeps_score_platform_and_user_scale(self):
        result = gm.parse_metacritic({'components': [
            {'meta': {'componentName': 'product'}, 'data': {'item': {
                'title': 'Control', 'slug': 'control', 'platform': 'PlayStation 4',
                'criticScoreSummary': {'score': 82}, 'platforms': [
                    {'name': 'PC', 'criticScoreSummary': {'score': 85}}]}}},
            {'meta': {'componentName': 'user-score-summary'},
             'data': {'item': {'score': 7.4}}}]})
        self.assertEqual((result['critic'], result['user']), (82, 7.4))
        self.assertEqual(result['platform'], 'PlayStation 4')
        self.assertEqual(result['pcCritic'], 85)

    def test_malformed_api_is_an_error_not_empty_metadata(self):
        with self.assertRaises(ValueError):
            gm.parse_metacritic({'components': []})
        with self.assertRaises(ValueError):
            gm.parse_proton({'error': 'maintenance'})

    def test_proton_rating_is_not_a_deck_fps_rating(self):
        game = {'name': 'Heavy game', 'dg': 'F', 'plat': 'PC'}
        result = gm.recommend(game, steam={'appid': 1, 'linux': False, 'comingSoon': False},
                              proton={'tier': 'platinum'}, deck={'category': 3})
        self.assertEqual(result['device'], 'PC')
        self.assertNotIn('60 fps', result['reason'])

    def test_anticheat_keeps_windows_as_explicit_fallback(self):
        result = gm.recommend({'name': 'Blocked game', 'dg': 'X'},
                              steam={'appid': 1, 'linux': False},
                              proton={'tier': 'borked'}, deck={'category': 1})
        self.assertEqual(result['device'], 'PC')
        self.assertEqual(result['method'], 'Windows')
        self.assertEqual(result['status'], 'fallback')

    def test_native_linux_can_work_even_without_proton_reports(self):
        result = gm.recommend({'name': 'Native game', 'dg': 'A'},
                              steam={'appid': 1, 'linux': True}, deck={'category': 3})
        self.assertEqual(result['device'], 'Steam Deck')
        self.assertEqual(result['method'], 'Nativo Linux')

    def test_unreleased_steam_game_does_not_reuse_old_performance_claim(self):
        result = gm.recommend({'name': 'Future game', 'dg': 'A'},
                              steam={'appid': 1, 'comingSoon': True}, proton={'tier': 'gold'})
        self.assertEqual(result['status'], 'waiting')

    def test_new_release_can_use_deck_when_valve_confirms_compatibility(self):
        result = gm.recommend({'name': 'Now released', 'dg': 'N'},
                              steam={'appid': 1, 'comingSoon': False},
                              proton={'tier': 'gold'}, deck={'category': 3})
        self.assertEqual(result['device'], 'Steam Deck')
        self.assertNotIn('referência anterior', result['reason'])

    def test_rpcs3_ingame_is_not_reported_as_playable(self):
        result = gm.recommend({'name': 'Console game', 'dg': 'D'},
                              emulation={'emulator': 'RPCS3', 'status': 'Ingame', 'verified': True})
        self.assertEqual(result['status'], 'waiting')

    def test_ps5_exclusive_stays_visible_without_invented_emulation(self):
        result = gm.recommend({'name': "Demon's Souls", 'plat': 'PlayStation 5', 'dg': 'X'},
                              platforms=['PlayStation 5'])
        self.assertEqual(result['status'], 'waiting')
        self.assertEqual(result['device'], 'PC')
        self.assertEqual(result['method'], 'Emulação futura')

    def test_nintendo_game_uses_its_console_instead_of_emulation(self):
        result = gm.recommend({'name': 'Metroid Dread', 'plat': 'Nintendo Switch', 'dg': 'A'},
                              emulation={'emulator': 'Eden', 'status': 'Referência anterior',
                                         'verified': False, 'console': 'Switch'})
        self.assertEqual(result['device'], 'Nintendo')
        self.assertEqual(result['method'], 'Nintendo Switch')
        self.assertEqual(result['status'], 'ready')
        self.assertNotIn('emulador', result['how'].lower())

    def test_light_emulation_can_use_deck_with_a_good_performance_reference(self):
        result = gm.recommend({'name': 'PS2 game', 'dg': 'A'},
                              emulation={'emulator': 'PCSX2', 'status': 'A confirmar', 'verified': False})
        self.assertEqual(result['device'], 'Steam Deck')
        self.assertEqual(result['method'], 'Emulação · PCSX2')
        self.assertEqual(result['status'], 'check')
        self.assertIn('Deck', result['how'])

    def test_pc_family_release_wins_over_nintendo_even_when_deck_is_best(self):
        result = gm.recommend({'name': 'Multiplatform', 'plat': 'Nintendo Switch', 'dg': 'A'},
                              steam={'appid': 1}, proton={'tier': 'gold'},
                              deck={'category': 3}, platforms=['Nintendo Switch', 'PC'])
        self.assertEqual(result['device'], 'Steam Deck')
        self.assertEqual(result['method'], 'Proton')

    def test_heavy_or_blocked_deck_games_stay_on_pc_despite_valve_compatibility(self):
        for grade in ['D', 'F', 'X']:
            with self.subTest(grade=grade):
                result = gm.recommend({'name': 'Demanding game', 'dg': grade},
                                      steam={'appid': 1}, proton={'tier': 'gold'}, deck={'category': 3})
                self.assertEqual(result['device'], 'PC')

    def test_deck_unsupported_overrides_an_old_good_grade(self):
        result = gm.recommend({'name': 'Unsupported', 'dg': 'A'}, steam={'appid': 1},
                              proton={'tier': 'gold'}, deck={'category': 1})
        self.assertEqual(result['device'], 'PC')

    def test_vr_only_games_use_pc_and_keep_unreleased_state(self):
        for coming_soon in [False, True]:
            with self.subTest(coming_soon=coming_soon):
                result = gm.recommend({'name': 'VR', 'dg': 'A'},
                                      steam={'appid': 1, 'vrOnly': True, 'comingSoon': coming_soon},
                                      proton={'tier': 'gold'}, deck={'category': 3})
                self.assertEqual(result['device'], 'PC')
                self.assertEqual(result['status'], 'waiting' if coming_soon else 'check')

    def test_heavy_emulators_stay_on_pc_and_unplayable_reports_stay_waiting(self):
        for emulator in ['RPCS3', 'shadPS4', 'Xenia Canary']:
            for status in ['Playable', 'Ingame']:
                with self.subTest(emulator=emulator, status=status):
                    result = gm.recommend({'name': 'Console game', 'dg': 'A'},
                                          emulation={'emulator': emulator, 'verified': True, 'status': status})
                    self.assertEqual(result['device'], 'PC')
                    self.assertEqual(result['status'], 'ready' if status == 'Playable' else 'waiting')

    def test_no_deck_evidence_defaults_to_pc(self):
        result = gm.recommend({'name': 'Unknown performance'}, steam={'appid': 1}, proton={'tier': 'gold'})
        self.assertEqual(result['device'], 'PC')

    def test_non_steam_pc_release_can_use_deck_but_keeps_compatibility_caveat(self):
        result = gm.recommend({'name': 'External launcher', 'dg': 'A'}, platforms=['PC', 'Nintendo Switch'])
        self.assertEqual(result['device'], 'Steam Deck')
        self.assertEqual(result['status'], 'check')

    def test_non_steam_linux_block_overrides_a_good_deck_grade(self):
        result = gm.recommend({'name': 'Blocked launcher', 'dg': 'A', 'plat': 'Windows'}, platforms=['PC'])
        self.assertEqual(result['device'], 'PC')
        self.assertEqual(result['method'], 'Windows')

    def test_old_pc_hardware_preference_does_not_invent_a_pc_edition(self):
        result = gm.recommend({'name': 'Console-only edition', 'plat': 'PC', 'dg': 'A'},
                              platforms=['PlayStation 5'])
        self.assertEqual(result['device'], 'PC')
        self.assertEqual(result['method'], 'Emulação futura')
        self.assertEqual(result['status'], 'waiting')

    def test_pc_release_wins_over_an_old_nintendo_preference(self):
        for steam, platforms in [({'appid': 1}, ['Nintendo Switch']),
                                 (None, ['Nintendo Switch', 'PC'])]:
            with self.subTest(steam=steam, platforms=platforms):
                result = gm.recommend({'name': 'Multiplatform', 'plat': 'Nintendo Switch'},
                                      steam=steam, platforms=platforms)
                self.assertEqual(result['device'], 'PC')

    def test_confirmed_pc_edition_does_not_reuse_an_old_nintendo_emulator(self):
        result = gm.recommend({'name': 'Multiplatform', 'plat': 'Nintendo Switch'},
                              platforms=['Nintendo Switch', 'PC'],
                              emulation={'emulator': 'Eden', 'console': 'Switch', 'verified': False})
        self.assertEqual(result['device'], 'PC')
        self.assertEqual(result['method'], 'Proton / Lutris')

    def test_nintendo_console_uses_known_edition_instead_of_old_hardware_preference(self):
        result = gm.recommend({'name': 'Nintendo game', 'plat': 'Nintendo Switch 2'},
                              platforms=['Nintendo Switch'])
        self.assertEqual(result['device'], 'Nintendo')
        self.assertEqual(result['method'], 'Nintendo Switch')

    def test_nintendo_platforms_are_detected_without_name_or_emulation_heuristics(self):
        for platform in ['Nintendo Switch 2', 'Nintendo Switch', 'Wii U', 'Wii',
                         'GameCube', 'Nintendo 64', 'Nintendo 3DS', 'Nintendo DS', 'Game Boy Advance']:
            with self.subTest(platform=platform):
                result = gm.recommend({'name': 'Example', 'plat': 'Steam Deck'}, platforms=[platform])
                self.assertEqual(result['device'], 'Nintendo')
                self.assertEqual(result['method'], platform)
                self.assertEqual(result['status'], 'ready')

    def test_announced_games_keep_their_target_platform_without_becoming_available(self):
        for game, steam, platforms in [({'name': 'Future Nintendo', 'released': False}, None, ['Nintendo Switch 2']),
                                      ({'name': 'Future PC'}, {'appid': 1, 'comingSoon': True}, ['PC'])]:
            with self.subTest(game=game):
                result = gm.recommend(game, steam=steam, platforms=platforms)
                self.assertEqual(result['device'], 'Nintendo' if platforms == ['Nintendo Switch 2'] else 'PC')
                self.assertEqual(result['status'], 'waiting')

    def test_future_nintendo_release_date_does_not_become_ready(self):
        result = gm.recommend({'name': 'Future', 'plat': 'Nintendo Switch 2'}, release_date='2999-12-31')
        self.assertEqual(result['device'], 'Nintendo')
        self.assertEqual(result['status'], 'waiting')

    def test_missing_steam_listing_does_not_mean_no_pc_version(self):
        result = gm.recommend({'name': 'Old PC game', 'dg': 'A'}, platforms=['PC'])
        self.assertEqual(result['method'], 'Proton / Lutris')
        self.assertEqual(result['status'], 'check')

    def test_cache_retains_last_good_data_and_date_on_api_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cache.json'
            cache = Cache(path)
            previous = cache.get('proton', '1', lambda: {'tier': 'gold'}, ttl=100)
            def failure():
                raise OSError('provider offline')
            current = cache.get('proton', '1', failure, ttl=-1)
            self.assertEqual(current['data'], previous['data'])
            self.assertEqual(current['updatedAt'], previous['updatedAt'])
            self.assertEqual(current['status'], 'stale')
            cache.save()
            self.assertEqual(json.loads(path.read_text())['proton:1']['data']['tier'], 'gold')

    def test_fresh_snapshot_seeds_ci_cache_without_changing_source_date(self):
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as directory:
            cache = Cache(Path(directory) / 'cache.json')
            stamp = datetime.now(timezone.utc).isoformat()
            game = {'name': 'Example', 'steam': {'appid': 123}, 'sources': {
                'proton': {'data': {'tier': 'gold'}, 'updatedAt': stamp, 'status': 'ok'}}}
            cache.seed([game])
            def must_not_request():
                self.fail('Fresh source should reuse the snapshot')
            result = cache.get('proton', '123', must_not_request)
            self.assertEqual(result['updatedAt'], stamp)
            self.assertEqual(result['data']['tier'], 'gold')

    def test_old_or_failed_snapshot_is_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Cache(Path(directory) / 'cache.json')
            game = {'name': 'Example', 'steam': {'appid': 123}, 'sources': {
                'proton': {'data': {'tier': 'gold'}, 'updatedAt': '2020-01-01T00:00:00+00:00', 'status': 'ok'}}}
            cache.seed([game])
            result = cache.get('proton', '123', lambda: {'tier': 'platinum'})
            self.assertEqual(result['data']['tier'], 'platinum')


if __name__ == '__main__':
    unittest.main()
