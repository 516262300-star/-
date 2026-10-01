import unittest
import asyncio
from types import SimpleNamespace
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, Mock, patch
import erp_client as erp
import erp_desktop_auth as auth
from erp_desktop_auth import DesktopLoginRequired

class AdsDesktopTests(unittest.TestCase):
    def setUp(self):
        auth._cookies = None

    def tearDown(self):
        auth._cookies = None

    def test_valid_session_reused_across_runs_without_opening_tabs(self):
        cookie = {'domain': 'ldswj.net', 'name': 'session', 'value': 'synthetic'}
        with patch.object(auth, '_read_browser_cookies', new_callable=AsyncMock, return_value=[cookie]), patch.object(auth, 'client_action') as command:
            for _ in range(3):
                auth._cookies = None  # Each scheduled process starts with no cache.
                self.assertEqual(auth.get_client_cookies(), [cookie])
            command.assert_not_called()

    def test_unavailable_session_opens_only_once_then_verifies(self):
        cookie = {'domain': 'ldswj.net', 'name': 'session', 'value': 'synthetic'}
        with patch.object(auth, '_read_browser_cookies', new_callable=AsyncMock, side_effect=[auth._SessionRefreshRequired('expired'), [cookie]]) as read, patch.object(auth, 'client_action') as command:
            self.assertEqual(auth.get_client_cookies(), [cookie])
            command.assert_called_once_with('open')
            self.assertEqual(read.await_count, 2)

    def test_read_only_check_never_opens_browser_even_on_failure(self):
        with patch.object(auth, '_read_browser_cookies', new_callable=AsyncMock, side_effect=DesktopLoginRequired('unavailable')), patch.object(auth, 'client_action') as command:
            with self.assertRaises(DesktopLoginRequired):
                auth.get_client_cookies(force=True, allow_open=False)
            command.assert_not_called()

    def test_network_failure_does_not_open_unnecessary_webpage(self):
        with patch.object(auth, '_read_browser_cookies', new_callable=AsyncMock, side_effect=DesktopLoginRequired('network timeout')), patch.object(auth, 'client_action') as command:
            with self.assertRaises(DesktopLoginRequired):
                auth.get_client_cookies()
            command.assert_not_called()

    def test_explicit_refresh_opens_once(self):
        with patch.object(auth, '_read_browser_cookies', new_callable=AsyncMock, return_value=[{'name': 'new'}]), patch.object(auth, 'client_action') as command:
            self.assertEqual(auth.get_client_cookies(force=True), [{'name': 'new'}])
            command.assert_called_once_with('open')

    def test_background_browser_is_headless_and_closed_on_success_or_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder) / 'LeedisDesktop' / 'erp-chrome'
            profile.mkdir(parents=True)
            for failure in (False, True):
                context = SimpleNamespace(close=AsyncMock())
                chromium = SimpleNamespace(launch_persistent_context=AsyncMock(return_value=context))
                with patch.dict(auth.os.environ, {'LOCALAPPDATA': folder}), patch.object(auth, '_verified_cookies', new_callable=AsyncMock, return_value=[{'name': 'session'}], side_effect=DesktopLoginRequired('expired') if failure else None):
                    if failure:
                        with self.assertRaises(DesktopLoginRequired):
                            asyncio.run(auth._read_background_cookies(chromium))
                    else:
                        self.assertEqual(asyncio.run(auth._read_background_cookies(chromium)), [{'name': 'session'}])
                chromium.launch_persistent_context.assert_awaited_once_with(str(profile), channel='chrome', headless=True, timeout=15000)
                context.close.assert_awaited_once()

    def test_browser_startup_connection_retries(self):
        browser = object()
        chromium = SimpleNamespace(connect_over_cdp=AsyncMock(side_effect=[OSError('private URL'), browser]))
        with patch.object(auth.asyncio, 'sleep', new_callable=AsyncMock):
            self.assertIs(asyncio.run(auth._connect_browser(chromium)), browser)
        self.assertEqual(chromium.connect_over_cdp.await_count, 2)

    def test_browser_failure_reports_stage_without_private_error(self):
        chromium = SimpleNamespace(connect_over_cdp=AsyncMock(side_effect=OSError('private URL')))
        with patch.object(auth.asyncio, 'sleep', new_callable=AsyncMock):
            with self.assertRaises(auth.DesktopLoginRequired) as result:
                asyncio.run(auth._connect_browser(chromium))
        self.assertIn('9222', str(result.exception))
        self.assertNotIn('private URL', str(result.exception))
        self.assertEqual(chromium.connect_over_cdp.await_count, 3)

    def test_profile_timeout_recovers_without_reopening_client(self):
        cookie = {'domain': 'ldswj.net', 'name': 'session', 'value': 'synthetic'}
        response = SimpleNamespace(ok=True, status=200, url=auth.PROFILE_URL,
                                   text=AsyncMock(return_value='<a onclick="logout()">退出</a>'))
        context = SimpleNamespace(cookies=AsyncMock(return_value=[cookie]),
                                  request=SimpleNamespace(get=AsyncMock(side_effect=[TimeoutError('private token'), response])))
        with patch.object(auth.asyncio, 'sleep', new_callable=AsyncMock), patch.object(auth, 'client_action') as command:
            self.assertEqual(asyncio.run(auth._verified_cookies(context)), [cookie])
            command.assert_not_called()
        self.assertEqual(context.request.get.await_count, 2)

    def test_profile_network_failure_is_bounded_and_sanitized(self):
        context = SimpleNamespace(cookies=AsyncMock(return_value=[{'domain': 'ldswj.net'}]),
                                  request=SimpleNamespace(get=AsyncMock(side_effect=TimeoutError('private token'))))
        with patch.object(auth, 'time', SimpleNamespace(monotonic=Mock(side_effect=[0, 0, 46]))), patch.object(auth.asyncio, 'sleep', new_callable=AsyncMock):
            with self.assertRaises(auth.DesktopLoginRequired) as result:
                asyncio.run(auth._verified_cookies(context))
        self.assertIn('TimeoutError', str(result.exception))
        self.assertNotIn('private token', str(result.exception))

    def test_login_page_never_returns_unverified_cookies(self):
        response = SimpleNamespace(ok=True, status=200, url=auth.PROFILE_URL,
                                   text=AsyncMock(return_value='<input name="password">'))
        context = SimpleNamespace(cookies=AsyncMock(return_value=[{'domain': 'ldswj.net'}]),
                                  request=SimpleNamespace(get=AsyncMock(return_value=response)))
        with patch.object(auth, 'time', SimpleNamespace(monotonic=Mock(side_effect=[0, 0, 46]))), patch.object(auth.asyncio, 'sleep', new_callable=AsyncMock):
            with self.assertRaises(auth.DesktopLoginRequired):
                asyncio.run(auth._verified_cookies(context))

    def test_missing_client_stops_without_old_session(self):
        with patch.object(erp, 'get_client_cookies', side_effect=DesktopLoginRequired('client needed')):
            with self.assertRaises(erp.LoginRequiredError):
                erp.build_requests_session()

    def test_expired_web_session_refreshes_once(self):
        cookie = {'name': 'session', 'value': 'synthetic', 'domain': 'ldswj.net', 'path': '/'}
        with patch.object(erp, 'get_client_cookies', return_value=[cookie]) as cookies, patch.object(erp, '_request_html', side_effect=[('<title>登录</title>', 'https://ldswj.net/login'), ('<table/>', 'https://ldswj.net/data')]):
            self.assertEqual(erp.fetch_html_with_login('https://ldswj.net/data')[0], '<table/>')
            self.assertEqual([c.kwargs['force'] for c in cookies.call_args_list], [False, True])

    def test_still_expired_is_failure(self):
        with patch.object(erp, 'get_client_cookies', return_value=[]), patch.object(erp, '_request_html', return_value=('<title>登录</title>', 'https://ldswj.net/login')):
            with self.assertRaises(erp.LoginRequiredError):
                erp.fetch_html_with_login('https://ldswj.net/data')

if __name__ == '__main__':
    unittest.main()
