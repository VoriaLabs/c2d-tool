import argparse
import sys
import shutil
import os
from .c2d import C2DFile
from .dxf import DXFImporter

def main():
    parser = argparse.ArgumentParser(description="Carbide Create Tool (c2d-tool)")
    parser.add_argument("filename", help="Path to the .c2d file")
    parser.add_argument("-o", "--output", help="Path to write the modified file")
    parser.add_argument("--no-backup", action="store_true", help="Disable automatic backup")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--fail-on-duplicate-layer", action="store_true", help="Fail if multiple layers match a name")
    
    # Inspection
    parser.add_argument("--list-layers", action="store_true", help="List all layers")
    parser.add_argument("--list-files", action="store_true", help="List embedded files")
    
    # Modification
    parser.add_argument("--rename-layer", action="append", nargs=2, metavar=('OLD', 'NEW'), help="Rename a layer")
    parser.add_argument("--clear-layer", action="append", help="Clear all vectors from a layer")
    parser.add_argument("--delete-layer", action="append", help="Delete a layer and its vectors")
    parser.add_argument("--delete-unused-layers", action="store_true", help="Delete layers not used by any toolpath")
    parser.add_argument("--create-layer", action="append", help="Create a new empty layer")
    parser.add_argument("--import-to-layer", action="append", nargs=2, metavar=('LAYER', 'DXF'), help="Import DXF to layer")
    parser.add_argument("--min-closed-area-mm2", type=float, default=0.1, help="Minimum area in mm^2 for importing closed DXF shapes (default: 0.1)")
    
    # Parameters
    parser.add_argument("--set-param", action="append", nargs=2, metavar=('KEY', 'VALUE'), help="Set a project parameter")
    parser.add_argument("--resize-to-fit-layer", action="append", help="Resize project to fit layer content")

    # Assets
    parser.add_argument("--export-file", action="append", nargs=2, metavar=('INTERNAL', 'OUTPUT'), help="Export embedded file")
    parser.add_argument("--dump-file", action="append", help="Dump embedded file content to stdout")

    args = parser.parse_args()
    
    input_path = args.filename
    output_path = args.output
    
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    # Handle file copy/backup logic
    working_path = input_path
    
    if output_path:
        # Copy input to output, then work on output
        if args.verbose:
            print(f"Copying {input_path} to {output_path}...")
        shutil.copy2(input_path, output_path)
        working_path = output_path
    elif not args.no_backup:
        # Create backup
        backup_path = input_path + ".bak"
        if args.verbose:
            print(f"Creating backup at {backup_path}...")
        shutil.copy2(input_path, backup_path)
    
    try:
        c2d = C2DFile(working_path)
        c2d.load()
        
        # Inspection
        if args.list_layers:
            layers = c2d.get_layers()
            print(f"Layers in {working_path}:")
            for l in layers:
                print(f"  - {l['name']} (UUID: {l['uuid']})")
                
        if args.list_files:
            files = c2d.list_files()
            print(f"Embedded files in {working_path}:")
            for f in files:
                print(f"  - {f['name']} ({f['size']} bytes)")

        # Helper to check duplicates
        def check_duplicates(name):
            layers = c2d.get_layers_by_name(name)
            if len(layers) > 1:
                print(f"Warning: Multiple layers found with name '{name}'")
                if args.fail_on_duplicate_layer:
                    sys.exit(1)
            return layers

        # Modifications

        # 0. Rename layers
        if args.rename_layer:
            for old_id, new_name in args.rename_layer:
                if args.verbose:
                    print(f"Renaming layer {old_id} to {new_name}")
                try:
                    c2d.rename_layer(old_id, new_name)
                except ValueError as e:
                    print(f"Error: {e}")
                    sys.exit(1)

        # 1. Delete layers
        if args.delete_layer:
            for layer_name in args.delete_layer:
                check_duplicates(layer_name)
                if args.verbose:
                    print(f"Deleting layer: {layer_name}")
                c2d.delete_layer(layer_name)
                
        # 2. Clear layers
        if args.clear_layer:
            for layer_name in args.clear_layer:
                check_duplicates(layer_name)
                if args.verbose:
                    print(f"Clearing layer: {layer_name}")
                c2d.clear_layer(layer_name)
                
        # 3. Create layers
        if args.create_layer:
            for layer_name in args.create_layer:
                if args.verbose:
                    print(f"Creating layer: {layer_name}")
                c2d.create_layer(layer_name)
                
        # 4. Import DXF
        if args.import_to_layer:
            importer = DXFImporter()
            for layer_name, dxf_path in args.import_to_layer:
                if args.verbose:
                    print(f"Importing {dxf_path} to layer {layer_name}...")
                
                # Ensure layer exists
                layers = check_duplicates(layer_name)
                if layers:
                    layer = layers[0]
                else:
                    if args.verbose:
                        print(f"Layer {layer_name} not found, creating it.")
                    layer = c2d.create_layer(layer_name)
                
                # Load DXF
                try:
                    elements = importer.load(dxf_path, min_closed_area_mm2=args.min_closed_area_mm2)
                    count = 0
                    for el in elements:
                        c2d.add_element(layer, el)
                        count += 1
                    if args.verbose:
                        print(f"Imported {count} elements.")
                except Exception as e:
                    print(f"Error importing DXF {dxf_path}: {e}")
                    sys.exit(1)

        # 5. Delete unused layers
        if args.delete_unused_layers:
            if args.verbose:
                print("Deleting unused layers...")
            deleted_layers = c2d.delete_unused_layers()
            if args.verbose:
                print(f"Deleted {len(deleted_layers)} unused layers:")
                for name in deleted_layers:
                    print(f"  - {name}")

        # Parameter operations

        # Parameter operations
        if args.set_param:
            for key, value in args.set_param:
                if args.verbose:
                    print(f"Setting param {key} = {value}")
                c2d.set_param(key, value)

        if args.resize_to_fit_layer:
            for layer_name in args.resize_to_fit_layer:
                if args.verbose:
                    print(f"Resizing project to fit layer: {layer_name}")
                c2d.resize_to_fit_layer(layer_name)

        # Asset operations
        if args.export_file:
            for internal_name, out_path in args.export_file:
                content = c2d.get_file_content(internal_name)
                if content:
                    with open(out_path, 'wb') as f:
                        f.write(content)
                    if args.verbose:
                        print(f"Exported {internal_name} to {out_path}")
                else:
                    print(f"Error: File {internal_name} not found in archive.")
                    
        if args.dump_file:
            for internal_name in args.dump_file:
                content = c2d.get_file_content(internal_name)
                if content:
                    # Try to decode as text if possible, else print repr
                    try:
                        print(content.decode('utf-8'))
                    except UnicodeDecodeError:
                        print(content)
                else:
                    print(f"Error: File {internal_name} not found in archive.")

        c2d.save()
        if args.verbose:
            print("Done.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
