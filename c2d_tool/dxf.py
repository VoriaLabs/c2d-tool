import ezdxf
from ezdxf import path
from typing import List, Dict, Any
import math

class DXFImporter:
    def __init__(self):
        pass

    def load(self, filepath: str) -> List[Dict[str, Any]]:
        """
        Load a DXF file and return a list of C2D element dictionaries.
        """
        try:
            doc = ezdxf.readfile(filepath)
        except IOError:
            raise FileNotFoundError(f"DXF file not found: {filepath}")
        except ezdxf.DXFStructureError:
            raise ValueError(f"Invalid or corrupted DXF file: {filepath}")

        msp = doc.modelspace()
        elements = []

        # Iterate over supported entities
        for entity in msp:
            if entity.dxftype() == 'LINE':
                elements.append(self._convert_line(entity))
            elif entity.dxftype() in ('LWPOLYLINE', 'POLYLINE'):
                elements.append(self._convert_polyline(entity))
            elif entity.dxftype() == 'CIRCLE':
                elements.append(self._convert_circle(entity))
            elif entity.dxftype() == 'ARC':
                elements.append(self._convert_arc(entity))
            # TODO: Add SPLINE support via ezdxf.path

        return [e for e in elements if e is not None]

    def _convert_line(self, entity) -> Dict[str, Any]:
        start = entity.dxf.start
        end = entity.dxf.end
        
        # A line is a path with 2 points
        return {
            "geometryType": "path",
            "points": [[start.x, start.y], [end.x, end.y]],
            "point_type": [0, 1], # 0=Start, 1=Line
            "smooth": [0, 0],
            # Dummy control points (required by schema?)
            "cp1": [[start.x, start.y], [end.x, end.y]],
            "cp2": [[start.x, start.y], [end.x, end.y]],
            "position": [0, 0],
            "closed": False
        }

    def _convert_polyline(self, entity) -> Dict[str, Any]:
        # Use ezdxf.path to handle bulges (curves) in polylines if present
        # For now, let's assume simple linear polylines or handle bulges manually?
        # ezdxf.path.make_path(entity) returns a Path object which is easy to iterate.
        
        p = path.make_path(entity)
        
        points = []
        point_types = []
        smooth = []
        cp1 = []
        cp2 = []
        
        # Start point
        start = p.start
        points.append([start.x, start.y])
        point_types.append(0) # Start
        smooth.append(0)
        cp1.append([start.x, start.y])
        cp2.append([start.x, start.y])
        
        for cmd in p.commands():
            if cmd.type == path.Command.LINE_TO:
                end = cmd.end
                points.append([end.x, end.y])
                point_types.append(1) # Line
                smooth.append(0)
                cp1.append([end.x, end.y]) # No curve
                cp2.append([end.x, end.y])
                
            elif cmd.type == path.Command.CUBIC_TO:
                # Bezier curve
                end = cmd.end
                ctrl1 = cmd.ctrl1
                ctrl2 = cmd.ctrl2
                
                points.append([end.x, end.y])
                point_types.append(3) # Curve
                smooth.append(1)
                
                # C2D seems to store cp1 for the *previous* point (outgoing)
                # and cp2 for the *current* point (incoming)?
                # Let's look at the dump again.
                # ID 6 (path):
                # Point 0: type 0. cp1=[273, 146], cp2=[273, 146]. Point=[273, 146].
                # Point 1: type 3. cp1=[273, 146], cp2=[241, 298]. Point=[241, 298].
                # Wait, if Point 1 is type 3 (curve), it needs control points.
                # cp2 of Point 1 is likely the incoming control point.
                # cp1 of Point 0 is likely the outgoing control point.
                
                # So for CUBIC_TO:
                # The previous point's cp1 should be updated to ctrl1.
                # The current point's cp2 should be ctrl2.
                
                # Update previous point's outgoing control point (cp1)
                cp1[-1] = [ctrl1.x, ctrl1.y]
                
                # Current point
                cp2.append([ctrl2.x, ctrl2.y])
                # Its outgoing cp1 defaults to itself unless next segment updates it
                cp1.append([end.x, end.y]) 
                
            # TODO: Handle QUAD_TO (convert to cubic)
            
        if entity.is_closed:
            # Add closing point? Or just set type 4?
            # In C2D dump, the last point has type 4 (Close) and matches the first point?
            # ID 4 (rect): 6 points. Last point matches first. Type 4.
            # ID 6 (path): 10 points. Last point matches first. Type 4.
            
            # Check if last point equals first point
            if points[-1] != points[0]:
                points.append(points[0])
                point_types.append(4)
                smooth.append(smooth[0])
                cp1.append(cp1[0])
                cp2.append(cp2[0])
            else:
                point_types[-1] = 4
                
        return {
            "geometryType": "path",
            "points": points,
            "point_type": point_types,
            "smooth": smooth,
            "cp1": cp1,
            "cp2": cp2,
            "position": [0, 0]
        }

    def _convert_circle(self, entity) -> Dict[str, Any]:
        center = entity.dxf.center
        radius = entity.dxf.radius
        
        cx, cy = center.x, center.y
        k = 0.5522847498 * radius
        
        # Relative points and control points
        # 0: Left
        # 1: Top
        # 2: Right
        # 3: Bottom
        # 4: Left (Close)
        # 5: Center (Dummy?)
        
        points = [
            [-radius, 0],
            [0, radius],
            [radius, 0],
            [0, -radius],
            [-radius, 0],
            [0, 0]
        ]
        
        # cp1 (Outgoing)
        cp1 = [
            [-radius, k],      # Left -> Up
            [k, radius],       # Top -> Right
            [radius, -k],      # Right -> Down
            [-k, -radius],     # Bottom -> Left
            [0, 0],            # End
            [0, 0]
        ]
        
        # cp2 (Incoming)
        cp2 = [
            [0, 0],            # Start
            [-k, radius],      # Top <- Left
            [radius, k],       # Right <- Top
            [k, -radius],      # Bottom <- Right
            [-radius, -k],     # Left <- Bottom
            [0, 0]
        ]
        
        return {
            "geometryType": "circle",
            "center": [cx, cy],
            "position": [cx, cy],
            "radius": radius,
            "points": points,
            "point_type": [0, 3, 3, 3, 3, 4],
            "smooth": [1, 1, 1, 1, 1, 1],
            "cp1": cp1,
            "cp2": cp2,
            "group_id": [],
            "tabs": []
        }

    def _convert_arc(self, entity) -> Dict[str, Any]:
        # Convert ARC to a Path with curves
        # ezdxf.path.make_path(entity) handles arcs too
        return self._convert_polyline(entity)

