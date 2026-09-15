import unittest

from tags import parse_tags


class ParseTagsTest(unittest.TestCase):
    def test_strips_each_tag(self) -> None:
        self.assertEqual(parse_tags("red, blue ,green"), ["red", "blue", "green"])


if __name__ == "__main__":
    unittest.main()
