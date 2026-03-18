# tests/test_config.py

import textwrap
import tempfile
import unittest
from pathlib import Path
from src.loader import load_config, _validate_config


class TestValidateConfig(unittest.TestCase):
    def _minimal_ontology(self, **overrides):
        base = {
            "label": "Test Onto",
            "uri": "https://example.org/test/",
            "prefix": "test",
            "openalex_keywords": ["test ontology"],
        }
        base.update(overrides)
        return base
    
    def test_valid_config_passes(self):
        config = {"ontologies": [self._minimal_ontology()]}
        _validate_config(config)
 
    def test_missing_ontologies_key_raises(self):
        with self.assertRaises(ValueError):
            _validate_config({})
 
    def test_empty_ontologies_list_raises(self):
        with self.assertRaises(ValueError):
            _validate_config({"ontologies": []})
 
    def test_missing_label_raises(self):
        onto = self._minimal_ontology()
        del onto["label"]
        with self.assertRaises(ValueError):
            _validate_config({"ontologies": [onto]})
 
    def test_missing_uri_raises(self):
        onto = self._minimal_ontology()
        del onto["uri"]
        with self.assertRaises(ValueError):
            _validate_config({"ontologies": [onto]})
 
    def test_missing_prefix_raises(self):
        onto = self._minimal_ontology()
        del onto["prefix"]
        with self.assertRaises(ValueError):
            _validate_config({"ontologies": [onto]})
 
    def test_missing_openalex_keywords_raises(self):
        onto = self._minimal_ontology()
        del onto["openalex_keywords"]
        with self.assertRaises(ValueError):
            _validate_config({"ontologies": [onto]})
 
    def test_multiple_ontologies_valid(self):
        config = {
            "ontologies": [
                self._minimal_ontology(prefix="a"),
                self._minimal_ontology(prefix="b"),
            ]
        }
        _validate_config(config)
 
    def test_error_message_contains_field_name(self):
        onto = self._minimal_ontology()
        del onto["uri"]
        with self.assertRaises(ValueError) as ctx:
            _validate_config({"ontologies": [onto]})
        self.assertIn("uri", str(ctx.exception))


class TestLoadConfig(unittest.TestCase):
    def _write_yaml(self, content: str) -> Path:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        f.write(content)
        f.close()
        return Path(f.name)
 
    def test_loads_valid_yaml(self):
        yaml_content = textwrap.dedent("""\
            output_dir: docs
            ontologies:
              - label: "My Onto"
                uri: "https://example.org/onto/"
                prefix: "myonto"
                openalex_keywords:
                  - "my ontology"
        """)
        path = self._write_yaml(yaml_content)
        config = load_config(path)
        self.assertEqual(config["output_dir"], "docs")
        self.assertEqual(len(config["ontologies"]), 1)
        self.assertEqual(config["ontologies"][0]["prefix"], "myonto")
 
    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_config("/tmp/definitely_does_not_exist_xyz.yaml")
 
    def test_output_dir_defaults_when_absent(self):
        """output_dir is optional; monitor.py falls back to 'docs'."""
        yaml_content = textwrap.dedent("""\
            ontologies:
              - label: "X"
                uri: "https://example.org/x/"
                prefix: "x"
                openalex_keywords: ["x"]
        """)
        path = self._write_yaml(yaml_content)
        config = load_config(path)
        self.assertNotIn("output_dir", config)  # absent from file, handled downstream
 
    def test_multiple_ontologies_loaded(self):
        yaml_content = textwrap.dedent("""\
            ontologies:
              - label: "A"
                uri: "https://a.org/"
                prefix: "a"
                openalex_keywords: ["a"]
              - label: "B"
                uri: "https://b.org/"
                prefix: "b"
                openalex_keywords: ["b1", "b2"]
        """)
        path = self._write_yaml(yaml_content)
        config = load_config(path)
        self.assertEqual(len(config["ontologies"]), 2)
        self.assertEqual(config["ontologies"][1]["openalex_keywords"], ["b1", "b2"])
 
 
if __name__ == "__main__":
    unittest.main()