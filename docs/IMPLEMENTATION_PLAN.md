# Implementation Plan - c2d-tool

## 1. Project Structure

```
c2d-tool/
├── c2d_tool/
│   ├── __init__.py
│   ├── main.py          # CLI entry point and argument parsing
│   ├── c2d.py           # Core logic for handling .c2d (SQLite) files
│   ├── dxf.py           # DXF parsing and conversion logic
│   └── utils.py         # Helper functions (compression, UUIDs)
├── tests/
│   ├── test_c2d.py
│   └── test_dxf.py
├── setup.py             # Package installation
└── requirements.txt     # Dependencies (ezdxf)
```

## 2. Core Components

### 2.1 `C2DFile` Class (`c2d_tool/c2d.py`)
Responsible for low-level interaction with the SQLite database and high-level manipulation of the project structure.

*   **Attributes**:
    *   `filepath`: Path to the file.
    *   `conn`: SQLite connection object.
    *   `cursor`: SQLite cursor.
*   **Methods**:
    *   `__init__(filepath)`: Initialize.
    *   `load()`: Open connection.
    *   `save(output_path=None)`: Commit changes. If `output_path` is different, copy file first or use `backup` API.
    *   `get_layers()`: Return list of layer objects (parsed JSON).
    *   `get_layer(name)`: Return specific layer object.
    *   `create_layer(name)`: Create a new layer item.
    *   `clear_layer(name)`: Find layer UUID, delete all child elements (items linked to this layer).
    *   `delete_layer(name)`: Delete the layer item and all child elements.
    *   `add_element(layer_name, element_data)`: Add a new geometry element linked to the layer.
    *   `list_files()`: Query `sqlar` table.
    *   `get_file_content(name)`: Retrieve and decompress blob from `sqlar`.
    *   `_read_item(id)`: Helper to read and decompress/deserialize item.
    *   `_write_item(item)`: Helper to serialize/compress and write item.

### 2.2 `DXFImporter` Class (`c2d_tool/dxf.py`)
Responsible for reading DXF files and converting entities into the JSON format expected by Carbide Create.

*   **Dependencies**: `ezdxf`
*   **Methods**:
    *   `load(filepath)`: Parse DXF.
    *   `extract_vectors()`: Iterate through model space.
    *   `_convert_line(entity)`: Convert LINE to C2D path.
    *   `_convert_polyline(entity)`: Convert LWPOLYLINE/POLYLINE to C2D path.
    *   `_convert_circle(entity)`: Convert CIRCLE to C2D circle.
    *   `_convert_arc(entity)`: Convert ARC to C2D arc.

### 2.3 CLI Logic (`c2d_tool/main.py`)
*   Use `argparse` to handle arguments.
*   Implement an `Action` queue to manage the order of operations (e.g., ensure clears happen before imports if specified for the same layer).
*   **Workflow**:
    1.  Parse arguments.
    2.  Open `C2DFile`.
    3.  Execute Inspection commands (`--list-layers`, etc.).
    4.  Execute Modification commands (`--clear-layer`, `--import-to-layer`).
    5.  Save file (if modified).

## 3. Data Formats & Conversion

### 3.1 C2D Element Schema (Inferred/To-Be-Verified)
We need to determine the exact JSON structure for:
*   **Paths**: Lists of points, open/closed flags.
*   **Circles**: Center point, radius.
*   **Layers**: Name, UUID, color, visibility.

*Action*: During implementation, we will inspect `example.c2d` to reverse-engineer the exact JSON keys (e.g., `type`, `path`, `radius`, `cx`, `cy`).

### 3.2 Coordinate Systems
*   DXF coordinates need to map 1:1 to C2D coordinates.
*   Unit handling: C2D usually defaults to the project settings (mm or inches). We might need to check `params` table for `Units` to ensure DXF is imported correctly, or assume the user handles scaling.

## 4. Implementation Steps

1.  **Setup**: Initialize git, create venv, install `ezdxf`.
2.  **Exploration**: Write a script to dump the JSON content of `example.c2d` to understand the schema for Layers and Elements.
3.  **Base C2D Class**: Implement reading/writing of the `items` table with zlib compression.
4.  **Layer Management**: Implement `list_layers`, `get_layer`, `clear_layer`.
5.  **DXF Parsing**: Implement basic DXF reading and conversion to internal Python dicts matching C2D schema.
6.  **Integration**: Connect DXF import to `add_element`.
7.  **CLI**: Build the command-line interface.
8.  **Testing**: Verify with `example.c2d` and generated DXFs.

## 5. Testing Strategy
*   **Round-trip Test**: Read `example.c2d`, write it back, ensure it's identical (or functionally equivalent).
*   **Import Test**: Create a simple DXF (square), import it, inspect the resulting C2D JSON to verify structure.
*   **Integration**: Open the modified file in Carbide Create (manual verification).
