import unittest

from anvil import utils


class TestUtils(unittest.TestCase):
    def test_expand(self):
        text = "blah $v"
        text = utils.expand_template(text, {
            'v': 'blah',
        })
        self.assertEquals(text, "blah blah")
