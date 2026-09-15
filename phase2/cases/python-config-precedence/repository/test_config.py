import unittest

from app.config import load_settings


class SettingsTest(unittest.TestCase):
    def test_file_overrides_defaults(self) -> None:
        settings = load_settings("settings.json", {})
        self.assertEqual(settings.host, "file.internal")
        self.assertEqual(settings.port, 8080)
        self.assertEqual(settings.timeout, 20)


if __name__ == "__main__":
    unittest.main()
