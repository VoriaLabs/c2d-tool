import unittest
import os
import shutil
import sqlite3
import zlib
import json
import io
from contextlib import redirect_stderr
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

    def test_min_closed_area_default_filters_small_closed_shapes(self):
        import ezdxf

        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_line((0, 0), (10, 10))
        msp.add_lwpolyline([(0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1)], close=True)  # area 0.01
        msp.add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1)], close=True)  # area 1.0
        msp.add_circle((20, 20), radius=0.1)  # area ~= 0.0314
        msp.add_circle((30, 30), radius=1.0)  # area ~= 3.1415
        doc.saveas(self.test_dxf)

        test_args = ["c2d-tool", self.test_c2d, "--import-to-layer", "TestLayer", self.test_dxf]
        stderr_buffer = io.StringIO()
        with patch.object(sys, 'argv', test_args):
            with redirect_stderr(stderr_buffer):
                main()

        stderr_output = stderr_buffer.getvalue()
        self.assertIn("Skipping closed shape LWPOLYLINE", stderr_output)
        self.assertIn("Skipping closed shape CIRCLE", stderr_output)

        c2d = C2DFile(self.test_c2d)
        c2d.load()
        c2d.cursor.execute("SELECT data FROM items WHERE type='element'")
        rows = c2d.cursor.fetchall()

        self.assertEqual(len(rows), 3)

        imported = [c2d._read_item_data(r['data']) for r in rows]
        circle_radii = sorted([el['radius'] for el in imported if el.get('geometryType') == 'circle'])
        self.assertEqual(circle_radii, [1.0])

    def test_min_closed_area_can_be_overridden_to_zero(self):
        import ezdxf

        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_line((0, 0), (10, 10))
        msp.add_lwpolyline([(0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1)], close=True)  # area 0.01
        msp.add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1)], close=True)  # area 1.0
        msp.add_circle((20, 20), radius=0.1)  # area ~= 0.0314
        msp.add_circle((30, 30), radius=1.0)  # area ~= 3.1415
        doc.saveas(self.test_dxf)

        test_args = [
            "c2d-tool",
            self.test_c2d,
            "--min-closed-area-mm2",
            "0",
            "--import-to-layer",
            "TestLayer",
            self.test_dxf
        ]
        with patch.object(sys, 'argv', test_args):
            main()

        c2d = C2DFile(self.test_c2d)
        c2d.load()
        c2d.cursor.execute("SELECT data FROM items WHERE type='element'")
        rows = c2d.cursor.fetchall()

        self.assertEqual(len(rows), 5)

if __name__ == '__main__':
    unittest.main()
