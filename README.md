Carbide Create Tool
===================

`c2d-tool` is a command-line utility for programmatically modifying Carbide Create (`.c2d`) project files. Its primary purpose is to automate the workflow of updating vector data within existing project files, such as replacing specific layers with content from DXF files.

## Usage

```bash
c2d-tool [OPTIONS] C2D_FILE [OPERATIONS]...
```

### Examples

**Replace layer content:**
Clear an existing layer and import new vectors from a DXF file.
```bash
c2d-tool project.c2d \
  --clear-layer "Profile Cut" \
  --import-to-layer "Profile Cut" "shapes.dxf"
```

**Update multiple layers:**
```bash
c2d-tool project.c2d \
  --clear-layer "Pockets" --import-to-layer "Pockets" "pockets.dxf" \
  --clear-layer "Drill" --import-to-layer "Drill" "holes.dxf"
```

**Inspect file contents:**
```bash
c2d-tool project.c2d --list-layers --list-files
```

**Export embedded assets:**
```bash
c2d-tool project.c2d --export-file "background.png" "extracted_bg.png"
```

## Command Line Arguments

### General Options
*   `C2D_FILE`: Path to the input `.c2d` file.
*   `-o, --output <filename>`: Path to write the modified file. If omitted, the input file is modified in-place (a backup is created by default unless `--no-backup` is used).
*   `--no-backup`: Disable automatic backup creation when modifying in-place.
*   `-v, --verbose`: Enable verbose output.
*   `--fail-on-duplicate-layer`: Exit with an error if an operation targets a layer name shared by multiple layers.

### Inspection Operations
*   `--list-layers`: List all vector layers found in the project.
*   `--list-files`: List all embedded files in the `sqlar` archive (images, previews, etc.).

### Modification Operations
Operations are generally performed in the order they appear, but `clear-layer` operations for a specific layer are prioritized before `import-to-layer` for the same layer to ensure clean replacement.

*   `--rename-layer <old_name_or_uuid> <new_name>`: Renames a layer. Supports targeting by name or UUID.
*   `--clear-layer <layer_name>`: Removes all vector elements associated with the specified layer. The layer itself is preserved.
*   `--delete-layer <layer_name>`: Completely removes the layer and all its associated vectors.
*   `--delete-unused-layers`: Deletes all layers that are not referenced by any toolpath.
*   `--create-layer <layer_name>`: Creates a new empty layer if it does not exist.
*   `--import-to-layer <layer_name> <dxf_file>`: Parses the specified DXF file and imports supported entities (LINES, POLYLINES, CIRCLES, ARCS) into the target layer. If the layer does not exist, it will be created.

### Parameter Operations
*   `--set-param <key> <value>`: Sets a specific project parameter (e.g., `--set-param display_mm 0`).
*   `--resize-to-fit-layer <layer_name>`: Updates the project `width` and `height` parameters to ensure they are large enough to contain all elements on the specified layer. (Assumes bottom-left origin).

### Asset Operations
*   `--export-file <internal_name> <output_path>`: Extracts a file from the internal `sqlar` archive to the local filesystem.
*   `--dump-file <internal_name>`: Prints the content of an internal file to stdout.

## Supported DXF Entities
The importer currently supports the following DXF entities:
*   **LINE**: Converted to open paths.
*   **LWPOLYLINE / POLYLINE**: Converted to open or closed paths.
*   **CIRCLE**: Converted to circle elements.
*   **ARC**: Converted to arc paths.
*   **SPLINE**: (Planned) Approximated as polyline paths.

## Installation

### Prerequisites
*   Python 3.8 or higher
*   `pip` (Python package installer)

### Setup

1.  Navigate to the `cc-tool` directory.

2.  Create and activate a virtual environment (recommended):
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
    ```

3.  Install the package:
    ```bash
    pip install -e .
    ```

### Usage

Once installed, you can run the tool directly:

```bash
c2d-tool --help
```

Or run it as a module:

```bash
python -m c2d_tool.main --help
```

## License

This project is licensed under the CC0 1.0 Universal text - see the [LICENSE](LICENSE) file for details.



