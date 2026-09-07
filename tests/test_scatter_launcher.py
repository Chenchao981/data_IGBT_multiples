import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gui import scatter_launcher


class ScatterLauncherPortIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.manifest = root / "ft_scatter_manifest.json"
        self.manifest.write_text("{}", encoding="utf-8")
        self.other_manifest = root / "other_ft_scatter_manifest.json"
        self.other_manifest.write_text("{}", encoding="utf-8")
        self.app_path = root / "frontend" / "ft_scatter_app.py"
        self.app_path.parent.mkdir()
        self.app_path.write_text("", encoding="utf-8")

        self.process_patch = patch.object(scatter_launcher, "_MANAGED_PROCESS", None)
        self.port_patch = patch.object(scatter_launcher, "_MANAGED_PORT", None)
        self.process_patch.start()
        self.port_patch.start()
        self.addCleanup(self.port_patch.stop)
        self.addCleanup(self.process_patch.stop)

    @staticmethod
    def _port_argument(popen_mock: Mock) -> str:
        command = popen_mock.call_args.args[0]
        return next(item for item in command if item.startswith("--server.port="))

    def test_external_port_occupancy_selects_the_next_free_port(self):
        child = Mock()
        child.poll.return_value = None

        def is_open(port):
            return port in {8502, 8503}

        with patch.object(scatter_launcher, "_port_is_open", side_effect=is_open), patch.object(
            scatter_launcher, "find_scatter_app", return_value=self.app_path
        ), patch.object(
            scatter_launcher.subprocess, "Popen", return_value=child
        ) as popen_mock, patch.object(
            scatter_launcher.webbrowser, "open"
        ) as browser_mock:
            url = scatter_launcher.launch_ft_scatter(self.manifest)

        self.assertTrue(url.startswith("http://127.0.0.1:8504/"))
        self.assertEqual(self._port_argument(popen_mock), "--server.port=8504")
        self.assertIs(scatter_launcher._MANAGED_PROCESS, child)
        self.assertEqual(scatter_launcher._MANAGED_PORT, 8504)
        browser_mock.assert_called_once_with(url)

    def test_live_managed_child_is_reused_without_probing_or_spawning(self):
        child = Mock()
        child.poll.return_value = None

        with patch.object(
            scatter_launcher, "_port_is_open", return_value=False
        ) as port_mock, patch.object(
            scatter_launcher, "find_scatter_app", return_value=self.app_path
        ) as app_mock, patch.object(
            scatter_launcher.subprocess, "Popen", return_value=child
        ) as popen_mock, patch.object(scatter_launcher.webbrowser, "open"):
            first_url = scatter_launcher.launch_ft_scatter(self.manifest, port=8510)
            second_url = scatter_launcher.launch_ft_scatter(
                self.other_manifest, port=8600
            )

        self.assertTrue(first_url.startswith("http://127.0.0.1:8510/"))
        self.assertTrue(second_url.startswith("http://127.0.0.1:8510/"))
        self.assertEqual(popen_mock.call_count, 1)
        self.assertEqual(app_mock.call_count, 1)
        self.assertEqual(port_mock.call_count, 1)

    def test_exited_managed_child_is_replaced_on_a_free_port(self):
        exited_child = Mock()
        exited_child.poll.return_value = 1
        replacement = Mock()
        replacement.poll.return_value = None
        scatter_launcher._MANAGED_PROCESS = exited_child
        scatter_launcher._MANAGED_PORT = 8507

        with patch.object(
            scatter_launcher, "_port_is_open", return_value=False
        ), patch.object(
            scatter_launcher, "find_scatter_app", return_value=self.app_path
        ), patch.object(
            scatter_launcher.subprocess, "Popen", return_value=replacement
        ) as popen_mock, patch.object(scatter_launcher.webbrowser, "open"):
            url = scatter_launcher.launch_ft_scatter(self.manifest, port=8502)

        self.assertTrue(url.startswith("http://127.0.0.1:8502/"))
        self.assertEqual(self._port_argument(popen_mock), "--server.port=8502")
        self.assertIs(scatter_launcher._MANAGED_PROCESS, replacement)
        self.assertEqual(scatter_launcher._MANAGED_PORT, 8502)
        exited_child.terminate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
