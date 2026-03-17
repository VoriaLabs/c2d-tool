import unittest
import os
import shutil
import sqlite3
import zlib
import json
from c2d_tool.c2d import C2DFile
from c2d_tool.main import main
import sys
from unittest.mock import patch

class TestParams(unittest.TestCase):
    def setUp(self):
        self.test_c2d = "test_params.c2d"
        
        # Create a minimal valid C2D file
        conn = sqlite3.connect(self.test_c2d)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE items(id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT UNIQUE, name TEXT, type TEXT, version TEXT, sz INT, data BLOB)")
        cursor.execute("CREATE TABLE params(key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("CREATE TABLE sqlar(name TEXT PRIMARY KEY, mode INT, mtime INT, sz INT, data BLOB)")
        
        # Add a layer
        layer_data = {
            "name": "TestLayer",
            "uuid": "{test-uuid}",
            "visible": True
        }
        blob = zlib.compress(json.dumps(layer_data).encode('utf-8'), level=1)
        cursor.execute("INSERT INTO items (uuid, name, type, data) VALUES (?, ?, ?, ?)", 
                       ("{test-uuid}", "TestLayer", "layer", blob))
        
        # Add an element at (100, 200)
        element_data = {
            "id": "{el-uuid}",
            "geometryType": "path",
            "layer": layer_data,
            "position": [0, 0],
            "points": [[100, 200]]
        }
        blob_el = zlib.compress(json.dumps(element_data).encode('utf-8'), level=1)
        cursor.execute("INSERT INTO items (uuid, name, type, data) VALUES (?, ?, ?, ?)", 
                       ("{el-uuid}", "path", "element", blob_el))
        
        # Initial params
        cursor.execute("INSERT INTO params (key, value) VALUES (?, ?)", ("width", "50"))
        cursor.execute("INSERT INTO params (key, value) VALUES (?, ?)", ("height", "50"))
        
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.test_c2d):
            os.remove(self.test_c2d)
        if os.path.exists(self.test_c2d + ".bak"):
            os.remove(self.test_c2d + ".bak")

    def test_set_param(self):
        test_args = ["c2d-tool", self.test_c2d, "--set-param", "display_mm", "0"]
        with patch.object(sys, 'argv', test_args):
            main()
            
        c2d = C2DFile(self.test_c2d)
        c2d.load()
        self.assertEqual(c2d.get_param("display_mm"), "0")

    def test_resize_to_fit_layer(self):
        test_args = ["c2d-tool", self.test_c2d, "--resize-to-fit-layer", "TestLayer"]
        with patch.object(sys, 'argv', test_args):
            main()
            
        c2d = C2DFile(self.test_c2d)
        c2d.load()
        # Element is at 100, 200. Initial size 50, 50.
        # Should resize to at least 100, 200.
        self.assertEqual(float(c2d.get_param("width")), 100.0)
        self.assertEqual(float(c2d.get_param("height")), 200.0)

    def test_resize_to_fit_layer_shrinks_when_current_size_is_larger(self):
        c2d = C2DFile(self.test_c2d)
        c2d.load()
        c2d.set_param("width", "500")
        c2d.set_param("height", "500")
        c2d.save()

        test_args = ["c2d-tool", self.test_c2d, "--resize-to-fit-layer", "TestLayer"]
        with patch.object(sys, 'argv', test_args):
            main()

        c2d = C2DFile(self.test_c2d)
        c2d.load()
        self.assertEqual(float(c2d.get_param("width")), 100.0)
        self.assertEqual(float(c2d.get_param("height")), 200.0)

if __name__ == '__main__':
    unittest.main()
