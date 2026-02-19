import sqlite3
import zlib
import json
import shutil
import os
from typing import List, Dict, Optional, Any
from .utils import generate_uuid

class C2DFile:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.conn = None
        self.cursor = None

    def load(self):
        """Open connection to the SQLite database."""
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"File not found: {self.filepath}")
        self.conn = sqlite3.connect(self.filepath)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def save(self, output_path: Optional[str] = None, backup: bool = True):
        """
        Save changes.
        If output_path is provided, we copy the current file to output_path 
        (if it's different) and then we are actually working on the original file 
        in-place until we close? 
        
        Actually, sqlite works on the file directly. 
        If we want to save to a different file, we should have copied it *before* opening,
        or we use the backup API.
        
        Strategy:
        1. If output_path is None (in-place):
           - If backup is True, copy self.filepath to self.filepath + ".bak"
           - Commit changes.
        2. If output_path is specified:
           - It's tricky to "save as" with an open sqlite connection if we've already made changes.
           - Better approach for CLI: Copy input to output *first*, then open output.
        
        For this class, let's assume we are modifying the file we opened.
        The CLI should handle the file copying logic.
        """
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    def _read_item_data(self, data_blob: bytes) -> Any:
        """Decompress and parse JSON data from a blob."""
        if not data_blob:
            return None
        try:
            decompressed = zlib.decompress(data_blob)
            return json.loads(decompressed)
        except (zlib.error, json.JSONDecodeError):
            # Return raw bytes if not valid zlib or JSON
            return data_blob

    def _write_item_data(self, data_obj: Any) -> bytes:
        """Serialize and compress data object."""
        if data_obj is None:
            return None
        json_str = json.dumps(data_obj, separators=(',', ':')) # Minimal whitespace
        data_bytes = json_str.encode('utf-8')
        return zlib.compress(data_bytes, level=1)

    def get_layers(self) -> List[Dict]:
        """Return a list of all layer objects."""
        self.cursor.execute("SELECT data FROM items WHERE type='layer'")
        layers = []
        for row in self.cursor.fetchall():
            layer_data = self._read_item_data(row['data'])
            if layer_data:
                layers.append(layer_data)
        return layers

    def get_layer(self, name: str) -> Optional[Dict]:
        """Find a layer by name."""
        layers = self.get_layers()
        for layer in layers:
            if layer.get('name') == name:
                return layer
        return None

    def create_layer(self, name: str) -> Dict:
        """Create a new layer if it doesn't exist."""
        existing = self.get_layer(name)
        if existing:
            return existing

        # Create new layer
        new_uuid = generate_uuid()
        layer_data = {
            "blue": 0,
            "green": 0,
            "locked": False,
            "name": name,
            "red": 0, # TODO: Randomize color?
            "uuid": new_uuid,
            "visible": True
        }
        
        blob = self._write_item_data(layer_data)
        # sz for JSON items is usually len of uncompressed string
        sz = len(json.dumps(layer_data, separators=(',', ':')).encode('utf-8'))
        
        self.cursor.execute(
            "INSERT INTO items (uuid, name, type, version, sz, data) VALUES (?, ?, ?, ?, ?, ?)",
            (new_uuid, name, 'layer', '', sz, blob)
        )
        return layer_data

    def clear_layer(self, name: str):
        """Remove all elements associated with the layer name."""
        # We need to iterate all elements and check their layer name
        # Since we can't easily query inside the compressed JSON in SQL,
        # we have to fetch all elements.
        
        self.cursor.execute("SELECT id, data FROM items WHERE type='element'")
        rows = self.cursor.fetchall()
        
        ids_to_delete = []
        for row in rows:
            data = self._read_item_data(row['data'])
            if data and 'layer' in data and data['layer'].get('name') == name:
                ids_to_delete.append(row['id'])
        
        if ids_to_delete:
            # Execute delete
            placeholders = ','.join('?' for _ in ids_to_delete)
            self.cursor.execute(f"DELETE FROM items WHERE id IN ({placeholders})", ids_to_delete)

    def delete_layer(self, name: str):
        """Delete the layer and all its elements."""
        self.clear_layer(name)
        self.cursor.execute("DELETE FROM items WHERE type='layer' AND name=?", (name,))

    def add_element(self, layer_data: Dict, element_data: Dict):
        """Add an element to the database."""
        # Ensure element has the correct layer data embedded
        element_data['layer'] = layer_data
        
        # Generate ID if missing
        if 'id' not in element_data:
            element_data['id'] = generate_uuid()
            
        blob = self._write_item_data(element_data)
        sz = len(json.dumps(element_data, separators=(',', ':')).encode('utf-8'))
        
        self.cursor.execute(
            "INSERT INTO items (uuid, name, type, version, sz, data) VALUES (?, ?, ?, ?, ?, ?)",
            (element_data['id'], element_data.get('geometryType', 'element'), 'element', '', sz, blob)
        )

    def set_param(self, key: str, value: str):
        """Set a parameter in the params table."""
        self.cursor.execute(
            "INSERT INTO params (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value))
        )

    def get_param(self, key: str) -> Optional[str]:
        """Get a parameter value."""
        self.cursor.execute("SELECT value FROM params WHERE key=?", (key,))
        row = self.cursor.fetchone()
        return row['value'] if row else None

    def get_layer_elements(self, layer_name: str) -> List[Dict]:
        """Get all elements belonging to a specific layer."""
        self.cursor.execute("SELECT data FROM items WHERE type='element'")
        elements = []
        for row in self.cursor.fetchall():
            data = self._read_item_data(row['data'])
            if data and 'layer' in data and data['layer'].get('name') == layer_name:
                elements.append(data)
        return elements

    def resize_to_fit_layer(self, layer_name: str):
        """Resize project width/height to fit the elements of the layer."""
        elements = self.get_layer_elements(layer_name)
        if not elements:
            return

        max_x = 0.0
        max_y = 0.0
        
        for el in elements:
            pos = el.get('position', [0.0, 0.0])
            points = el.get('points', [])
            
            for pt in points:
                # Absolute coordinates
                abs_x = pos[0] + pt[0]
                abs_y = pos[1] + pt[1]
                
                if abs_x > max_x:
                    max_x = abs_x
                if abs_y > max_y:
                    max_y = abs_y
        
        # Update params if larger
        # We assume we want to expand to fit, but maybe we should just set it?
        # The user said "ensure that it fits".
        # Let's read current size first.
        current_width = float(self.get_param('width') or 0)
        current_height = float(self.get_param('height') or 0)
        
        new_width = max(current_width, max_x)
        new_height = max(current_height, max_y)
        
        # Add a small margin? Maybe not unless requested.
        # But if max_x is exactly on the edge, it might be safer to have a tiny bit more?
        # Let's stick to exact or max for now.
        
        if new_width > current_width:
            self.set_param('width', str(new_width))
        if new_height > current_height:
            self.set_param('height', str(new_height))

    def get_layers_by_name(self, name: str) -> List[Dict]:
        """Return all layers with the given name."""
        layers = self.get_layers()
        return [l for l in layers if l.get('name') == name]

    def get_layer_by_uuid(self, uuid: str) -> Optional[Dict]:
        """Find a layer by UUID."""
        self.cursor.execute("SELECT data FROM items WHERE type='layer' AND uuid=?", (uuid,))
        row = self.cursor.fetchone()
        if row:
            return self._read_item_data(row['data'])
        return None

    def rename_layer(self, identifier: str, new_name: str):
        """Rename a layer identified by name or UUID."""
        # Find layer
        layer = self.get_layer_by_uuid(identifier)
        if not layer:
            layers = self.get_layers_by_name(identifier)
            if not layers:
                raise ValueError(f"Layer not found: {identifier}")
            if len(layers) > 1:
                raise ValueError(f"Multiple layers found with name '{identifier}'. Use UUID to specify.")
            layer = layers[0]

        old_name = layer['name']
        layer_uuid = layer['uuid']

        # Update layer object
        layer['name'] = new_name
        blob = self._write_item_data(layer)
        sz = len(json.dumps(layer, separators=(',', ':')).encode('utf-8'))

        # Update items table for the layer
        self.cursor.execute(
            "UPDATE items SET name=?, data=?, sz=? WHERE type='layer' AND uuid=?",
            (new_name, blob, sz, layer_uuid)
        )

        # Update all elements on this layer
        self.cursor.execute("SELECT id, data FROM items WHERE type='element'")
        rows = self.cursor.fetchall()

        for row in rows:
            data = self._read_item_data(row['data'])
            if data and 'layer' in data and data['layer'].get('uuid') == layer_uuid:
                # Update embedded layer name
                data['layer']['name'] = new_name

                new_blob = self._write_item_data(data)
                new_sz = len(json.dumps(data, separators=(',', ':')).encode('utf-8'))

                self.cursor.execute(
                    "UPDATE items SET data=?, sz=? WHERE id=?",
                    (new_blob, new_sz, row['id'])
                )

    def delete_unused_layers(self) -> List[str]:
        """Delete layers not used by any toolpath. Returns list of deleted layer names."""
        # 1. Get all used layer UUIDs from toolpaths
        used_layer_uuids = set()
        self.cursor.execute("SELECT data FROM items WHERE type='toolpath'")
        for row in self.cursor.fetchall():
            data = self._read_item_data(row['data'])
            if data and 'toolpath_layers' in data:
                for luuid in data['toolpath_layers']:
                    if luuid is not None:
                        used_layer_uuids.add(luuid)

        # 2. Get all layers
        all_layers = self.get_layers()
        deleted_layers = []

        for layer in all_layers:
            luuid = layer['uuid']
            if luuid not in used_layer_uuids:
                name = layer.get('name', 'Unknown')
                self._delete_layer_by_uuid(luuid)
                deleted_layers.append(name)

        return deleted_layers

    def _delete_layer_by_uuid(self, uuid: str):
        """Helper to delete a layer and its elements by UUID."""
        # Delete elements first
        self.cursor.execute("SELECT id, data FROM items WHERE type='element'")
        rows = self.cursor.fetchall()
        ids_to_delete = []
        for row in rows:
            data = self._read_item_data(row['data'])
            if data and 'layer' in data and data['layer'].get('uuid') == uuid:
                ids_to_delete.append(row['id'])

        if ids_to_delete:
            placeholders = ','.join('?' for _ in ids_to_delete)
            self.cursor.execute(f"DELETE FROM items WHERE id IN ({placeholders})", ids_to_delete)

        # Delete layer item
        self.cursor.execute("DELETE FROM items WHERE type='layer' AND uuid=?", (uuid,))

    def list_files(self) -> List[Dict]:
        """List files in sqlar."""
        self.cursor.execute("SELECT name, sz, mtime FROM sqlar")
        files = []
        for row in self.cursor.fetchall():
            files.append({
                "name": row['name'],
                "size": row['sz'],
                "mtime": row['mtime']
            })
        return files

    def get_file_content(self, name: str) -> Optional[bytes]:
        """Get raw content of a file from sqlar."""
        self.cursor.execute("SELECT data FROM sqlar WHERE name=?", (name,))
        row = self.cursor.fetchone()
        if row and row['data']:
            try:
                return zlib.decompress(row['data'])
            except zlib.error:
                return row['data']
        return None
