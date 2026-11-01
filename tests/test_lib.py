import io
import os
import socket
import sys
import unittest
import urllib.error
from unittest import mock

from tests.helpers import SKILL_ROOT

sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from lib import (  # noqa: E402
    is_network_error,
    is_network_error_text,
    network_hint,
    proxy_env_names,
)


class NetworkDetectionTest(unittest.TestCase):
    def test_http_error_is_not_a_network_problem(self):
        exc = urllib.error.HTTPError("http://127.0.0.1/x", 404, "Not Found", {}, None)
        self.assertFalse(is_network_error(exc))

    def test_url_error_is_a_network_problem(self):
        self.assertTrue(is_network_error(urllib.error.URLError("Connection refused")))

    def test_connection_refused_is_a_network_problem(self):
        self.assertTrue(is_network_error(ConnectionRefusedError("refused")))

    def test_timeout_is_a_network_problem(self):
        self.assertTrue(is_network_error(TimeoutError("timed out")))

    def test_dns_text_is_detected(self):
        self.assertTrue(
            is_network_error_text("Temporary failure in name resolution")
        )

    def test_unrelated_text_is_not_detected(self):
        self.assertFalse(is_network_error_text("schema_id 与 id 不一致"))


class NetworkHintTest(unittest.TestCase):
    def test_hint_suggests_proxy_when_unset(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            text = network_hint("Connection refused")
            self.assertEqual(proxy_env_names(), [])
        self.assertIn("代理", text)
        self.assertIn("https_proxy", text)
        self.assertIn("Connection refused", text)

    def test_hint_acknowledges_existing_proxy(self):
        env = {"https_proxy": "http://127.0.0.1:7890"}
        with mock.patch.dict(os.environ, env, clear=True):
            text = network_hint()
            self.assertEqual(proxy_env_names(), ["https_proxy"])
        self.assertIn("已检测到代理环境变量 https_proxy", text)
        self.assertIn("确认代理地址", text)

    def test_hint_never_prints_proxy_value(self):
        env = {"https_proxy": "http://user:secret@127.0.0.1:7890"}
        with mock.patch.dict(os.environ, env, clear=True):
            text = network_hint()
        self.assertNotIn("secret", text)


if __name__ == "__main__":
    unittest.main()
