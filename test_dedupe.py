
import unittest
from unittest.mock import patch
import mx
import re

class TestDedupe(unittest.TestCase):
    @patch('builtins.input')
    @patch('builtins.print')
    def test_ask_selection_dedupe(self, mock_print, mock_input):
        variants = [{'bandwidth': 1000}]
        # Duplicate languages
        audio = [
            {'language': 'en', 'name': 'English', 'group_id': 'audio-high'},
            {'language': 'en', 'name': 'English', 'group_id': 'audio-low'},
            {'language': 'hi', 'name': 'Hindi', 'group_id': 'audio-high'}
        ]

        # User selects 'A' (All)
        mock_input.side_effect = ['1', 'a']

        v_filter, a_filter, q_label, a_label = mx.ask_selection(variants, audio)

        # Regex should contain audio-high but not audio-low
        # a_filter will be something like (audio\-high|audio\-high)
        self.assertTrue('audio-high' in a_filter.replace('\\', ''))
        self.assertNotIn('audio-low', a_filter)

        self.assertEqual(a_label, 'Multi')

if __name__ == '__main__':
    unittest.main()
