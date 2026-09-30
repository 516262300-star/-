import unittest
from unittest.mock import patch
import erp_client as erp
from erp_desktop_auth import DesktopLoginRequired

class AdsDesktopTests(unittest.TestCase):
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
