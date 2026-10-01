import argparse
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

import run_evals


class ServerStartupTests(unittest.TestCase):
    @patch("run_evals.time.sleep")
    @patch("run_evals.urllib.request.urlopen")
    def test_waits_after_connection_refused(self, urlopen, sleep):
        urlopen.side_effect = [
            urllib.error.URLError(ConnectionRefusedError("refused")),
            MagicMock(),
        ]
        run_evals.wait_for_server("http://localhost:8000/chat")
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once()
        self.assertIsInstance(urlopen.call_args.args[0], str)

    @patch("run_evals.urllib.request.urlopen")
    def test_get_404_means_server_is_ready(self, urlopen):
        url = "http://localhost:8000/chat"
        urlopen.side_effect = urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        run_evals.wait_for_server(url)
        urlopen.assert_called_once()

    @patch("run_evals.time.sleep")
    @patch("run_evals.time.monotonic", side_effect=[0, 0, 11])
    @patch("run_evals.urllib.request.urlopen")
    def test_unavailable_server_has_actionable_error(self, urlopen, monotonic, sleep):
        urlopen.side_effect = urllib.error.URLError(ConnectionRefusedError("refused"))
        with self.assertRaisesRegex(ConnectionError, "localhost:8000/chat.*HOST och PORT"):
            run_evals.wait_for_server("http://localhost:8000/chat")
        sleep.assert_not_called()

    @patch.dict("os.environ", {"CHATBOT_SECRET": "test-secret"})
    @patch("run_evals.parse_args", return_value=argparse.Namespace(
        url="http://localhost:8000/chat", cases="cases.yaml", repeat=1))
    @patch("run_evals.load_cases", return_value=[{"id": "test-case"}])
    @patch("run_evals.wait_for_server")
    @patch("run_evals.run_case", side_effect=urllib.error.URLError("refused"))
    def test_connection_loss_exits_with_case_context(self, *mocks):
        with self.assertRaisesRegex(SystemExit, "misslyckades under test-case: refused"):
            run_evals.main()


if __name__ == "__main__":
    unittest.main()
