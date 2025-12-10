
import unittest
from unittest.mock import patch
import mx

class TestDedupe(unittest.TestCase):
    @patch('builtins.input')
    @patch('builtins.print')
    def test_ask_selection_all(self, mock_print, mock_input):
        variants = [{'bandwidth': 1000}]
        audio = [{'language': 'en'}, {'language': 'hi'}]

        # 'A' selects all
        mock_input.side_effect = ['1', 'a']
        v, a, q, l = mx.ask_selection(variants, audio)
        self.assertEqual(a, 'all')
        self.assertEqual(l, 'Multi')

    @patch('builtins.input')
    @patch('builtins.print')
    def test_ask_selection_manual(self, mock_print, mock_input):
        variants = [{'bandwidth': 1000}]
        audio = [
            {'language': 'en', 'group_id': 'audio-high'},
            {'language': 'hi', 'group_id': 'audio-high'}
        ]

        # Select English (1)
        mock_input.side_effect = ['1', '1']
        v, a, q, l = mx.ask_selection(variants, audio)

        # Should prioritize Language over GroupId
        self.assertTrue('en' in a)
        self.assertFalse('audio-high' in a)

if __name__ == '__main__':
    unittest.main()
