import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import erp_client as erp
import erp_desktop_auth as auth
from erp_desktop_auth import DesktopLoginRequired

class AdsDesktopTests(unittest.TestCase):
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
