import unittest
import os
import sqlite3
import zlib
import json
from c2d_tool.c2d import C2DFile
from c2d_tool.main import main
import sys
from unittest.mock import patch

class TestAdvancedLayers(unittest.TestCase):
    def setUp(self):
        self.test_c2d = "test_adv.c2d"
        
        # Create a minimal valid C2D file
        conn = sqlite3.connect(self.test_c2d)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE items(id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT UNIQUE, name TEXT, type TEXT, version TEXT, sz INT, data BLOB)")
        cursor.execute("CREATE TABLE params(key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("CREATE TABLE sqlar(name TEXT PRIMARY KEY, mode INT, mtime INT, sz INT, data BLOB)")
        
        # Add Layer A
        layer_a = {"name": "LayerA", "uuid": "{uuid-a}", "visible": True}
        blob_a = zlib.compress(json.dumps(layer_a).encode('utf-8'), level=1)
        cursor.execute("INSERT INTO items (uuid, name, type, data) VALUES (?, ?, ?, ?)", ("{uuid-a}", "LayerA", "layer", blob_a))
        
        # Add Layer B (Unused)
        layer_b = {"name": "LayerB", "uuid": "{uuid-b}", "visible": True}
        blob_b = zlib.compress(json.dumps(layer_b).encode('utf-8'), level=1)
        cursor.execute("INSERT INTO items (uuid, name, type, data) VALUES (?, ?, ?, ?)", ("{uuid-b}", "LayerB", "layer", blob_b))
        
        # Add Toolpath using Layer A
        tp = {
            "name": "TP1",
            "toolpath_layers": ["{uuid-a}"]
        }
        blob_tp = zlib.compress(json.dumps(tp).encode('utf-8'), level=1)
        cursor.execute("INSERT INTO items (uuid, name, type, data) VALUES (?, ?, ?, ?)", ("{uuid-tp}", "TP1", "toolpath", blob_tp))
        
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.test_c2d):
            os.remove(self.test_c2d)
        if os.path.exists(self.test_c2d + ".bak"):
            os.remove(self.test_c2d + ".bak")

    def test_rename_layer(self):
        test_args = ["c2d-tool", self.test_c2d, "--rename-layer", "LayerA", "LayerNew"]
        with patch.object(sys, 'argv', test_args):
            main()
            
        c2d = C2DFile(self.test_c2d)
        c2d.load()
        self.assertIsNotNone(c2d.get_layer("LayerNew"))
        self.assertIsNone(c2d.get_layer("LayerA"))

    def test_delete_unused_layers(self):
        test_args = ["c2d-tool", self.test_c2d, "--delete-unused-layers"]
        with patch.object(sys, 'argv', test_args):
            main()
            
        c2d = C2DFile(self.test_c2d)
        c2d.load()
        # Layer A is used by TP1, should remain
        self.assertIsNotNone(c2d.get_layer("LayerA"))
        # Layer B is unused, should be gone
        self.assertIsNone(c2d.get_layer("LayerB"))

    def test_duplicate_warning(self):
        # Add duplicate LayerA manually
        conn = sqlite3.connect(self.test_c2d)
        cursor = conn.cursor()
        layer_a2 = {"name": "LayerA", "uuid": "{uuid-a2}", "visible": True}
        blob_a2 = zlib.compress(json.dumps(layer_a2).encode('utf-8'), level=1)
        cursor.execute("INSERT INTO items (uuid, name, type, data) VALUES (?, ?, ?, ?)", ("{uuid-a2}", "LayerA", "layer", blob_a2))
        conn.commit()
        conn.close()
        
        # Try to rename LayerA - should fail or warn?
        # We implemented rename_layer to raise ValueError if duplicates found by name
        c2d = C2DFile(self.test_c2d)
        c2d.load()
        with self.assertRaises(ValueError):
            c2d.rename_layer("LayerA", "NewName")

if __name__ == '__main__':
    unittest.main()
