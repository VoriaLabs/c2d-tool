import unittest
import os
import shutil
import sqlite3
import zlib
import json
from c2d_tool.c2d import C2DFile
from c2d_tool.dxf import DXFImporter
from c2d_tool.main import main
import sys
from unittest.mock import patch

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.test_c2d = "test_integration.c2d"
        self.test_dxf = "test_integration.dxf"
        
        # Create a minimal valid C2D file (sqlite db)
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
        conn.commit()
        conn.close()
        
        # Create a minimal DXF
        import ezdxf
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_line((0, 0), (10, 10))
        doc.saveas(self.test_dxf)

    def tearDown(self):
        if os.path.exists(self.test_c2d):
            os.remove(self.test_c2d)
        if os.path.exists(self.test_dxf):
            os.remove(self.test_dxf)
        if os.path.exists(self.test_c2d + ".bak"):
            os.remove(self.test_c2d + ".bak")

    def test_import_flow(self):
        # Run main with arguments
        test_args = ["c2d-tool", self.test_c2d, "--import-to-layer", "TestLayer", self.test_dxf]
        with patch.object(sys, 'argv', test_args):
            from c2d_tool.main import main
            main()
            
        # Verify
        c2d = C2DFile(self.test_c2d)
        c2d.load()
        
        # Check if element exists
        c2d.cursor.execute("SELECT data FROM items WHERE type='element'")
        rows = c2d.cursor.fetchall()
        self.assertEqual(len(rows), 1)
        
        data = c2d._read_item_data(rows[0]['data'])
        self.assertEqual(data['layer']['name'], "TestLayer")
        self.assertEqual(data['geometryType'], "path")

if __name__ == '__main__':
    unittest.main()
