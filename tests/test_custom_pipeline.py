import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from pipeline import build_pipeline, load_custom_builder, validate_custom_path


class CustomPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.path = self.directory / 'camera.py'
        self.original_search = list(sys.path)
    def tearDown(self):
        sys.path[:] = self.original_search
        sys.modules.pop('oak_webcam_custom', None)
        sys.modules.pop('custom_test_helper', None)
        self.temporary.cleanup()
    def test_absolute_readable_python_file_required(self):
        for value in [None, '', 'relative.py', 'https://example.com/a.py', str(self.directory), str(self.path)]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_custom_path(value)
        self.path.write_text('raise RuntimeError("not imported during validation")')
        self.assertEqual(validate_custom_path(str(self.path)), str(self.path))
    def test_builder_loaded_in_worker_and_sibling_imports_work(self):
        self.path.write_text('def build_pipeline(pipeline):\n    import custom_test_helper\n    return custom_test_helper.output + pipeline\n')
        (self.directory / 'custom_test_helper.py').write_text('output = 40\n')
        with patch.dict(os.environ, OAK_WEBCAM_PRESET='custom', OAK_WEBCAM_CUSTOM_PIPELINE=str(self.path)):
            self.assertEqual(build_pipeline(2), 42)
    def test_missing_builder_and_syntax_error_surface(self):
        self.path.write_text('build_pipeline = None\n')
        with self.assertRaisesRegex(ValueError, 'define build_pipeline'):
            load_custom_builder(str(self.path))
        self.path.write_text('def invalid syntax !!!\n')
        with self.assertRaises(SyntaxError):
            load_custom_builder(str(self.path))


if __name__ == '__main__': unittest.main()
