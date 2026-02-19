import sqlite3
import zlib
import json
import sys

def dump_c2d(filepath):
    try:
        conn = sqlite3.connect(filepath)
        cursor = conn.cursor()
        
        print(f"--- Dumping items from {filepath} ---")
        cursor.execute("SELECT id, uuid, name, type, data FROM items")
        items = cursor.fetchall()
        
        for item_id, uuid, name, item_type, data in items:
            print(f"\nID: {item_id}, UUID: {uuid}, Name: {name}, Type: {item_type}")
            if data:
                try:
                    # Try decompressing
                    decompressed = zlib.decompress(data)
                    try:
                        # Try parsing as JSON
                        json_data = json.loads(decompressed)
                        print(json.dumps(json_data, indent=2))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        print(f"Raw Data (first 100 bytes): {decompressed[:100]}")
                except zlib.error:
                    print("Data is not zlib compressed or is corrupt.")
            else:
                print("No data.")
                
        print("\n--- Dumping params ---")
        cursor.execute("SELECT key, value FROM params")
        params = cursor.fetchall()
        for key, value in params:
            print(f"{key}: {value}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python dump_c2d.py <c2d_file>")
    else:
        dump_c2d(sys.argv[1])
