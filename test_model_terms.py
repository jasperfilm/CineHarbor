"""Model notices describe imported H3 bindings without exposing project data."""
import unittest
from model_terms import describe_config


class ModelTerms(unittest.TestCase):
    def test_custom_h3_recipe_is_identified_without_prompt_scanning(self):
        other = describe_config({'model': 'workflow', 'prompt': 'do not use MiniMaxH3'})
        self.assertEqual(other['id'], 'custom-workflow')
        h3 = describe_config({'model': 'workflow', 'recipe': {'graph': {'1': {'class_type': 'MiniMaxH3ImageToVideo', 'inputs': {}}}}})
        self.assertEqual(h3['id'], 'minimax-h3')
        self.assertFalse(h3['rights_granted'])

    def test_notice_does_not_echo_private_prompt_paths_or_identifiers(self):
        notice = describe_config({'model': 'workflow', 'prompt': 'private text', 'recipe': {'model_files': [{'file': '/private/secret.safetensors'}]}})
        self.assertNotIn('private', str(notice))
        self.assertNotIn('secret', str(notice))

if __name__ == '__main__': unittest.main()
