import ezdxf

doc = ezdxf.new()
msp = doc.modelspace()

# Add a line
msp.add_line((0, 0), (100, 100))

# Add a circle
msp.add_circle((50, 50), radius=25)

# Add a polyline (rectangle)
msp.add_lwpolyline([(10, 10), (90, 10), (90, 90), (10, 90)], close=True)

doc.saveas("test.dxf")
print("Created test.dxf")
