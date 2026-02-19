# Carbide Create `.c2d` (SQLite) — `items` and `params` format

This document describes the parts of the Carbide Create `.c2d` file format that matter for programmatic editing of project content, with a focus on **`items`** (geometry, layers, toolpaths) and **`params`** (project settings).

A `.c2d` file is a **SQLite3 database**. The schema commonly includes: `items`, `params`, `sqlar`, `metadata`, and `log`. For geometry replacement workflows (e.g., replacing a layer’s contents with vectors from DXF), the **primary tables are `items` and `params`**.

---

## 1) Tables of interest

### 1.1 `params`
```sql
CREATE TABLE params(
    key TEXT PRIMARY KEY,
    value TEXT
);
```

### 1.2 `items`
```sql
CREATE TABLE items(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE,
    name TEXT,
    type TEXT,
    version TEXT,
    sz INT,
    data BLOB
);
```

---

## 2) Common encoding rules

### 2.1 Zlib compression for `items.data`
Observed `.c2d` files store `items.data` as **zlib-compressed** payloads (DEFLATE in a zlib wrapper), not gzip.

* The zlib header commonly begins with `0x78 0x01`, corresponding to “fastest” compression hint.
* For round-tripping with minimal differences, recompress using:
  * `zlib.compress(payload, level=1)`

> **Practical tip:** When editing JSON items, decompress → modify → serialize → recompress. Avoid trying to “surgically” patch compressed bytes.

### 2.2 `items.sz`
For **JSON-based items** (`layer`, `element`, `toolpath_group`, `toolpath`), observed:
* `sz == len(uncompressed_payload_bytes)`

For binary payload items (e.g., `type="model"`), **do not assume** `sz` matches the decompressed length; it may not.

### 2.3 JSON encoding
JSON payloads are UTF-8 text. Many files use pretty printing with indentation and a trailing newline.

This formatting is not strictly required, but preserving it makes diffs stable and keeps the database “native-looking.”

### 2.4 UUID identity invariants (important)
Across observed JSON items:

* `type="layer"`: `items.uuid` == JSON field `"uuid"`
* `type="toolpath_group"`: `items.uuid` == JSON field `"uuid"`
* `type="toolpath"`: `items.uuid` == JSON field `"uuid"`
* `type="element"`: `items.uuid` == JSON field `"id"` (note: field name differs)

**Recommendation:** preserve this invariant when editing and especially when creating new items.

### 2.5 Embedded layer objects inside elements
Each `element` JSON embeds a full `"layer": {...}` object (name, uuid, visibility/lock, RGB).

To avoid subtle inconsistencies:
* When renaming/recoloring a layer, update:
  1) the canonical `layer` item, and  
  2) the embedded `"layer"` objects within all elements on that layer (safest).

---

## 3) `params` table

### 3.1 Shape
`params` is a simple key/value store. **All values are stored as TEXT**, including numbers and booleans.

Examples:
* `"display_mm": "0" | "1"`
* `"width": "1066.8"`
* `"grid_enabled": "1"`

### 3.2 Common keys (not exhaustive)
You’ll often see keys like:

* Document/material: `width`, `height`, `thickness`, `material`
* Units/UI: `display_mm`, `grid_enabled`, `grid_spacing`
* Work zero/origin: `zero_x`, `zero_y`, `zero_z`
* Active layer: `active_layer` (a layer UUID string; often `{...}` form)
* Version/requirements: `version`, `build_num`, `minimum_build_num`, `requires_pro`, `minimum_carbide_motion_version`
* Toolpaths: `num_toolpaths`

### 3.3 Editing guidance
For workflows that **replace vector geometry in layers**, `params` often requires no changes.

If you add/remove toolpaths:
* update `num_toolpaths` accordingly.

If you delete a layer referenced by `active_layer`:
* update `active_layer` to a valid layer UUID, or Carbide Create may repair/reset it.

---

## 4) `items` table: object model

### 4.1 Item types
Common values of `items.type`:

* `layer` — vector layer definitions (name, color, visibility, lock)
* `element` — vector geometry
* `toolpath_group` — UI grouping for toolpaths
* `toolpath` — CAM operations (often select geometry by layer and/or element)
* `model` — binary payload (not required for typical geometry-layer replacement)

### 4.2 Version field (`items.version`)
* `"J1"` is commonly used for JSON-based items.
* Other versions exist (e.g. `"model_2"` for `model` items).

---

## 5) `layer` items (`type="layer"`, `version="J1"`)

### 5.1 Schema
```json
{
  "uuid": "{5c4c5f2c-2e78-4693-8a4e-af86ea7fd455}",
  "name": "MyLayer",
  "visible": true,
  "locked": false,
  "red": 0,
  "green": 0,
  "blue": 0
}
```

### 5.2 Notes
* Layer UUID is typically a `{...}` UUID string.
* Some files may use an empty string `""` as a layer UUID; treat it as valid if present.

---

## 6) `element` items (`type="element"`, `version="J1"`)

Elements represent vector shapes. Geometry is stored as a **cubic Bezier path representation**, even for straight line segments.

### 6.1 Common element fields
Most elements contain:
```json
{
  "id": "{2fafb3a8-d0ac-4673-a385-2c7220795c49}",
  "geometryType": "path",
  "behavior": 0,

  "position": [0.0, 0.0],
  "center": [450.85, 539.75],

  "points": [[...], ...],
  "cp1": [[...], ...],
  "cp2": [[...], ...],
  "point_type": [0, ...],
  "smooth": [1, ...],

  "layer": { "...layer object..." },
  "group_id": [],
  "tabs": []
}
```

Notes:
* `id` corresponds to `items.uuid` for elements.
* Not all geometries have a `"center"` field.
* `group_id` and `tabs` may be empty; preserve if non-empty.

### 6.2 Array length invariant
Observed invariant:
* `len(points) == len(cp1) == len(cp2) == len(point_type) == len(smooth)`

### 6.3 Segment interpretation (cubic Beziers)
For each index `i >= 1`, the segment from `points[i-1]` to `points[i]` is defined by:
* control point 1 = `cp1[i]`
* control point 2 = `cp2[i]`

### 6.4 Straight segments as degenerate cubics
Straight edges are often encoded with “degenerate” cubic controls:
* `cp1[i] == points[i-1]`
* `cp2[i] == points[i]`

This is particularly convenient for importing polylines (e.g., from DXF).

### 6.5 `point_type` (inferred enum)
Observed values include `0`, `1`, `3`, `4`.

**Inferred mapping (best current guess):**
* `0` = **MoveTo** (first entry)
* `1` = **LineTo** (seen in rectangle/polygon-like primitives)
* `3` = **CurveTo** (cubic Bezier segment endpoint; can also represent lines via degenerate controls)
* `4` = **ClosePath marker / sentinel**

Notes:
* Some files encode straight segments using `1` (LineTo).
* Other files encode everything as `3` with degenerate control points.
* For import/replacement tooling, using only `0/3/4` with degenerate cubics is typically robust.

### 6.6 Closure conventions
Closed shapes typically include a final `point_type` value of `4` (ClosePath marker).

**Important:** the final entry’s coordinates may be a sentinel and not part of the geometric loop, depending on `geometryType` (circles commonly use a `[0,0]` sentinel at the final point).

Treat closure as driven by `point_type`, not by raw equality of first/last points.

### 6.7 `behavior` (underspecified; inferred)
`behavior` is an integer that correlates with `geometryType` in observed samples:

* `"path"` often uses `behavior: 0`
* `"rectangle"` observed with `behavior: 1`
* `"circle"` observed with `behavior: 3`

**Hypothesis (educated guess):** `behavior` selects which editor/primitive constraint model applies (free path vs parametric primitive types).  
If your workflow replaces geometry with imported vectors, using `"path"` with `behavior: 0` is a practical default.

If preserving existing primitives, preserve their existing `behavior` values.

### 6.8 Geometry-specific schemas and examples

#### A) `geometryType = "path"` (recommended interchange representation)
A closed rectangle polyline encoded as degenerate cubics:

```json
{
  "behavior": 0,
  "geometryType": "path",
  "id": "{11111111-1111-1111-1111-111111111111}",
  "position": [0.0, 0.0],
  "points": [
    [0.0, 0.0],
    [10.0, 0.0],
    [10.0, 5.0],
    [0.0, 5.0],
    [0.0, 0.0],
    [0.0, 0.0]
  ],
  "cp1": [
    [0.0, 0.0],
    [0.0, 0.0],
    [10.0, 0.0],
    [10.0, 5.0],
    [0.0, 5.0],
    [0.0, 0.0]
  ],
  "cp2": [
    [0.0, 0.0],
    [10.0, 0.0],
    [10.0, 5.0],
    [0.0, 5.0],
    [0.0, 0.0],
    [0.0, 0.0]
  ],
  "point_type": [0, 3, 3, 3, 3, 4],
  "smooth": [1, 0, 0, 0, 0, 1],
  "group_id": [],
  "tabs": [],
  "layer": {
    "uuid": "{LAYER-UUID}",
    "name": "Imported",
    "visible": true,
    "locked": false,
    "red": 0,
    "green": 0,
    "blue": 0
  }
}
```

**Writing guidance for DXF polylines:**  
For a polyline `P0..Pn`:
* `point_type[0]=0`, `point_type[i]=3` for `i=1..n`
* degenerate controls: `cp1[i]=P(i-1)`, `cp2[i]=Pi`
If closed, add a final segment endpoint `P0` (as a `3`), then a `4` close marker.

#### B) `geometryType = "circle"` (parametric primitive)
Circles are stored as 4 cubic arcs + a close sentinel. Includes `center`, `position`, and `radius`.

```json
{
  "behavior": 3,
  "geometryType": "circle",
  "id": "{22222222-2222-2222-2222-222222222222}",
  "center": [50.0, 50.0],
  "position": [50.0, 50.0],
  "radius": 10.0,

  "points": [
    [-10.0, 0.0],
    [0.0, 10.0],
    [10.0, 0.0],
    [0.0, -10.0],
    [-10.0, 0.0],
    [0.0, 0.0]
  ],
  "point_type": [0, 3, 3, 3, 3, 4],

  "cp1": [
    [-10.0, 0.0],
    [-10.0, 5.5228474983],
    [-5.5228474983, 10.0],
    [10.0, -5.5228474983],
    [5.5228474983, -10.0],
    [0.0, 0.0]
  ],
  "cp2": [
    [-10.0, 0.0],
    [5.5228474983, 10.0],
    [10.0, 5.5228474983],
    [-5.5228474983, -10.0],
    [-10.0, -5.5228474983],
    [0.0, 0.0]
  ],

  "smooth": [1, 1, 1, 1, 1, 1],
  "group_id": [],
  "tabs": [],
  "layer": { "...layer object..." }
}
```

Notes:
* The last `[0,0]` is commonly used as a sentinel in circle encoding.
* Controls use kappa `k ≈ 0.5522847498` (`k*r` offsets).

#### C) `geometryType = "rectangle"` (parametric primitive)
Rectangles include additional fields: `width`, `height`, `radius`, `corner_type`, `center`, and often use `point_type=1` (LineTo).

```json
{
  "behavior": 1,
  "geometryType": "rectangle",
  "id": "{33333333-3333-3333-3333-333333333333}",
  "center": [100.0, 100.0],
  "position": [100.0, 100.0],

  "width": 40.0,
  "height": 20.0,
  "radius": 2.0,
  "corner_type": 0,

  "points": [
    [20.0, 10.0],
    [20.0, -10.0],
    [-20.0, -10.0],
    [-20.0, 10.0],
    [20.0, 10.0],
    [20.0, 10.0]
  ],
  "cp1": [
    [20.0, 10.0],
    [20.0, 10.0],
    [20.0, -10.0],
    [-20.0, -10.0],
    [-20.0, 10.0],
    [20.0, 10.0]
  ],
  "cp2": [
    [20.0, 10.0],
    [20.0, -10.0],
    [-20.0, -10.0],
    [-20.0, 10.0],
    [20.0, 10.0],
    [20.0, 10.0]
  ],
  "point_type": [0, 1, 1, 1, 1, 4],
  "smooth": [1, 0, 0, 0, 0, 1],

  "group_id": [],
  "tabs": [],
  "layer": { "...layer object..." }
}
```

Notes:
* `corner_type` is not fully understood; likely an enum for corner treatment (sharp/rounded/chamfer, etc.).
* Many tooling workflows can ignore rectangle primitives and represent them as `"path"`.

#### D) `geometryType = "regular_polygon"` (parametric primitive)
Regular polygons include: `num_sides`, `radius`, `rotation`, `center`, and frequently use `point_type=1`.

```json
{
  "behavior": 2,
  "geometryType": "regular_polygon",
  "id": "{44444444-4444-4444-4444-444444444444}",
  "center": [200.0, 200.0],
  "position": [200.0, 200.0],

  "num_sides": 6,
  "radius": 25.0,
  "rotation": 0,

  "points": [
    [25.0, 0.0],
    [12.5, 21.6506],
    [-12.5, 21.6506],
    [-25.0, 0.0],
    [-12.5, -21.6506],
    [12.5, -21.6506],
    [25.0, 0.0],
    [25.0, 0.0]
  ],
  "cp1": [
    [25.0, 0.0],
    [25.0, 0.0],
    [12.5, 21.6506],
    [-12.5, 21.6506],
    [-25.0, 0.0],
    [-12.5, -21.6506],
    [12.5, -21.6506],
    [25.0, 0.0]
  ],
  "cp2": [
    [25.0, 0.0],
    [12.5, 21.6506],
    [-12.5, 21.6506],
    [-25.0, 0.0],
    [-12.5, -21.6506],
    [12.5, -21.6506],
    [25.0, 0.0],
    [25.0, 0.0]
  ],
  "point_type": [0, 1, 1, 1, 1, 1, 1, 4],
  "smooth": [1, 0, 0, 0, 0, 0, 0, 1],
  "group_id": [],
  "tabs": [],
  "layer": { "...layer object..." }
}
```

Notes:
* `behavior` for regular polygons is not fully confirmed; preserve it when present, or represent as `"path"`.

---

## 7) `toolpath_group` items (`type="toolpath_group"`, `version="J1"`)

### Schema + example
```json
{
  "uuid": "{aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee}",
  "name": "Group 1",
  "enabled": true,
  "expanded": true
}
```

---

## 8) `toolpath` items (`type="toolpath"`, `version="J1"`)

Toolpaths define CAM operations. Even if you regenerate gcode, toolpaths can matter structurally because they select geometry by **layers** and/or **elements**.

### 8.1 Common toolpath schema
```json
{
  "uuid": "{toolpath-uuid}",
  "name": "Toolpath Name",
  "type": "contour",
  "version": 1,

  "enabled": true,
  "automatic_parameters": true,

  "start_depth": "0.000",
  "end_depth": "t-3",

  "toolpath_group": "{group-uuid}",
  "toolpath_layers": ["{layer-uuid}", ""],
  "elements": [],

  "tolerance": 0.01,

  "speeds": {
    "feedrate": 800.0,
    "plungerate": 300.0,
    "rpm": 18000.0
  },

  "tool": {
    "uuid": "{tool-uuid}",
    "name": "1/8\" End Mill",
    "number": 1,
    "vendor": "",
    "model": "",
    "url": "",
    "type": 0,

    "diameter": 3.175,
    "angle": 0.0,
    "corner_radius": 0.0,

    "length": 12.0,
    "overall_length": 38.0,
    "flutes": 2,

    "plungerate": 300.0,
    "slot_feedrate": 600.0,
    "slot_plungerate": 300.0,
    "surfacing_feedrate": 800.0,
    "surfacing_plungerate": 300.0,

    "finish_allowance": 0.0,
    "read_only": false,
    "display_mm": true
  }
}
```

### 8.2 Depth fields as expressions
`start_depth` / `end_depth` may be numeric strings **or expression strings**, e.g.:
* `"t-3"`, `"t+0.1"`, `"t+0.1mm"`

Treat these as expressions; do not force numeric parsing.

### 8.3 Layer selection for toolpaths
Many files select geometry via:
* `toolpath_layers`: list of layer UUID strings (may include `""`)

Some files may instead populate:
* `elements`: list of element UUIDs

When replacing a layer’s contents, preserving the layer UUID allows toolpaths referencing that layer to continue working without changes.

### 8.4 Toolpath type variants (examples)

#### A) Contour
```json
{
  "...common fields...": "...",
  "type": "contour",
  "climb": true,
  "ofset_dir": 0,
  "stepdown": 1.5,
  "stepover": 0.4,
  "stock_to_leave": 0.0,

  "ignore_tabs": false,
  "tab_height": 2.0,
  "tab_width": 6.0,

  "enable_ramping": true,
  "ramp_angle": 5.0
}
```

#### B) Pocket
```json
{
  "...common fields...": "...",
  "type": "pocket_toolpath",
  "angle": 0,
  "stepdown": 1.5,
  "stepover": 0.4,
  "stock_to_leave": 0.0,

  "enable_rest": false,
  "rest_diameter": 0.0,

  "enable_ramping": true,
  "ramp_angle": 5.0
}
```

#### C) Drilling
```json
{
  "...common fields...": "...",
  "type": "drilling_toolpath",
  "drill_type": 0,
  "peck_distance": 2.0,

  "enable_ramping": false,
  "ramp_angle": 0.0
}
```

#### D) Advanced V-Carve
```json
{
  "...common fields...": "...",
  "type": "advanced_vcarve_toolpath",

  "pocket_enabled": true,
  "pocket_first": false,

  "stepdown": 0.5,
  "stepover": 0.2,
  "stock_to_leave": 0.0,

  "stepdown_pocket": 1.5,
  "stepover_pocket": 0.4,
  "stock_to_leave_pocket": 0.0,

  "tool_pocket": { "...second tool object..." },
  "speeds_pocket": { "feedrate": 800.0, "plungerate": 300.0, "rpm": 18000.0 },

  "link_type": 0,
  "link_uuid": "",
  "inlay_enabled": false
}
```

---

## 9) Practical guidance for “replace layer contents” workflows

### 9.1 Locate the target layer
Identify a layer by:
* matching `layer` item JSON `"name"`, or
* using `params.active_layer`, or
* using a known UUID.

### 9.2 Identify elements on that layer
Elements embed a `layer` object:
* `element.layer.uuid` is the element’s layer identifier.

Collect all `items` where `type="element"` and `JSON.layer.uuid == target_layer_uuid`.

### 9.3 Replacement strategy choices

**Strategy A: Delete and insert new elements**
* Delete all existing element rows on the layer.
* Insert new `element/J1` rows with:
  * `items.uuid` = new element UUID
  * JSON `"id"` = same UUID
  * `"geometryType":"path"`, `"behavior":0` (recommended)
  * arrays populated with degenerate cubic controls for linework
  * embedded `"layer"` object consistent with the canonical layer definition
* Set `sz = len(uncompressed_json_bytes)` for JSON items.

**Strategy B: In-place rewrite**
* Keep the same element UUIDs but replace their geometry arrays.
* This can be safer if some other structure references element UUIDs (some files do, via toolpaths’ `elements`).

### 9.4 Minimum invariants when writing an element
When writing any `element`:
* `items.uuid` == JSON `"id"`
* array lengths match (`points/cp1/cp2/point_type/smooth`)
* include `"layer"` object and set `"layer.uuid"` correctly
* compress with zlib, update `items.sz` appropriately

---

## 10) Known underspecified fields (preserve if you don’t understand them)

These fields exist and may influence UI or CAM behavior:

* `behavior` (int) — correlates with primitive type; treat as primitive behavior selector (inferred).
* `corner_type` (int, rectangles) — likely corner style enum.
* `group_id` (list of UUIDs) — grouping relationships; sometimes non-empty.
* `tabs` (list) — per-element tab anchors (often empty).
* `smooth` (list) — per-node smoothing flags; preserve when rewriting existing elements.

If your workflow replaces geometry, it is usually safe to:
* generate `"path"` elements with `behavior: 0`
* use degenerate cubics for linework
* set `smooth` to sharp corners unless you intentionally model curves
