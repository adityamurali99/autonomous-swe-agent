import unittest

from slug import slugify


class SlugifyTest(unittest.TestCase):
    def test_normalizes_words(self) -> None:
        self.assertEqual(slugify("  Hello, SWE Agent!  "), "hello-swe-agent")

    def test_collapses_separators(self) -> None:
        self.assertEqual(slugify("one___two   three"), "one-two-three")


if __name__ == "__main__":
    unittest.main()
