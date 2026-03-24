# Plan: Visualise Atlas Annotation with Preset Colours

> **Status:** Proposal — ready for implementation  
> **Target repository:** `brainrender-napari`  
> **Scope:** Smallest-possible, surgical change to colour the annotation
> (`add_labels`) layer using each brain region's canonical RGB colour from
> the BrainGlobe Atlas API, with an optional UI toggle.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture](#2-current-architecture)
3. [Key Python / napari / Qt Concepts Required](#3-key-python--napari--qt-concepts-required)
4. [The Core Mechanism: napari Labels `color` Parameter](#4-the-core-mechanism-napari-labels-color-parameter)
5. [BrainGlobe Atlas Colour Data](#5-brainglobe-atlas-colour-data)
6. [Detailed Implementation Plan](#6-detailed-implementation-plan)
   - [Step 1 – Build the colour dictionary helper](#step-1--build-the-colour-dictionary-helper)
   - [Step 2 – Apply it in `add_to_viewer`](#step-2--apply-it-in-add_to_viewer)
   - [Step 3 – Add a UI toggle checkbox](#step-3--add-a-ui-toggle-checkbox)
   - [Step 4 – Connect the toggle signal](#step-4--connect-the-toggle-signal)
   - [Step 5 – Update tests](#step-5--update-tests)
7. [Potential Bugs & Edge Cases](#7-potential-bugs--edge-cases)
8. [Test Plan](#8-test-plan)
9. [Execution Checklist](#9-execution-checklist)

---

## 1. Executive Summary

When a user double-clicks an atlas in the viewer, the plugin currently calls:

```python
viewer.add_labels(atlas.annotation, name="..._annotation")
```

napari assigns **arbitrary, random colours** to each label value, so the same
region looks different every time the plugin is opened, and the colours bear no
relation to the canonical colours used by BrainGlobe and Brainrender.

**Goal**: Pass a `color` dictionary to `add_labels` so every annotation region
is coloured with its canonical RGB triplet from `atlas.structures`, matching
exactly what Brainrender and the BrainGlobe website show.

The minimal code change is **≈ 15 lines** added/modified in two files, plus a
matching test update.  An optional UI toggle (`QCheckBox`) lets the user switch
between preset and napari-auto colours without reloading the atlas.

---

## 2. Current Architecture

```
BrainrenderViewerWidget (brainrender_viewer_widget.py)
    │  double-click on atlas row
    ▼
_on_add_atlas_requested(atlas_name)
    │  creates BrainGlobeAtlas + NapariAtlasRepresentation
    ▼
NapariAtlasRepresentation.add_to_viewer()       ← CHANGE HAPPENS HERE
    │  viewer.add_image(atlas.reference, visible=False)
    │  viewer.add_labels(atlas.annotation)      ← no colour dict today
    │  connect mouse_move_callbacks
    ▼
napari Labels layer – random auto-colours       ← problem
```

### Relevant files

| File | Role |
|---|---|
| `brainrender_napari/napari_atlas_representation.py` | Core layer-creation logic |
| `brainrender_napari/brainrender_viewer_widget.py` | Main widget, holds UI |
| `brainrender_napari/widgets/structure_view.py` | Region tree view (reference only) |
| `tests/test_unit/test_napari_atlas_representation.py` | Unit tests to update |
| `tests/test_integration/test_brainrender_viewer_widget.py` | Integration tests to update |

---

## 3. Key Python / napari / Qt Concepts Required

### 3.1 Python dataclass (`@dataclass`)

`NapariAtlasRepresentation` is declared with `@dataclass`.  
Adding a new field requires only one line inside the class body, and
`__post_init__` handles any initialisation logic.

```python
@dataclass
class NapariAtlasRepresentation:
    bg_atlas: BrainGlobeAtlas
    viewer: Viewer
    use_preset_colours: bool = True   # ← new field; default True
    mesh_opacity: float = 0.4
    mesh_blending: str = "translucent_no_depth"
```

### 3.2 Python `dict` comprehension

Building a `{label_id: colour}` mapping from a list of structures in one
readable expression:

```python
{s["id"]: [c / 255.0 for c in s["rgb_triplet"]] + [1.0]
 for s in atlas.structures.values()}
```

### 3.3 Type aliases and `Optional`

```python
from typing import Optional, Dict
ColourDict = Dict[int, list]   # {label_id → [R, G, B, A] in 0-1 range}
```

### 3.4 napari `Labels` layer — `color` parameter

`napari.viewer.Viewer.add_labels()` signature (relevant part):

```python
def add_labels(
    data: np.ndarray,
    *,
    name: str = "Labels",
    color: Optional[Dict[int, ColorType]] = None,
    ...
) -> Labels
```

- `color=None` → napari assigns random colours (current behaviour).
- `color={id: rgba}` → exact colours per label.
- After creation the property is also writeable:
  `layer.color = new_colour_dict` — this enables the live toggle.

**`ColorType`** can be:
- A length-4 list/tuple of `float` values in `[0.0, 1.0]`: `[R, G, B, A]`
- A colour name string: `"red"`
- A hex string: `"#ff0000"`

We will always use the `[R, G, B, A]` tuple form for reliability.

### 3.5 napari `Labels.color` as a live-update property

```python
annotation_layer = viewer.add_labels(data, color=my_dict)
# Later, to restore napari auto-colours:
annotation_layer.color = {}          # empty → auto
# To restore preset colours:
annotation_layer.color = my_dict     # restore preset
```

This means we can toggle colours without removing and re-adding the layer,
preserving the user's zoom/camera state.

### 3.6 Qt `QCheckBox` + `Signal` / `Slot`

```python
from qtpy.QtWidgets import QCheckBox
self.use_preset_colours = QCheckBox("Use preset colours")
self.use_preset_colours.setChecked(True)
self.use_preset_colours.stateChanged.connect(self._on_preset_colours_toggled)
```

### 3.7 BrainGlobe Atlas API — structure data access

```python
from brainglobe_atlasapi import BrainGlobeAtlas
atlas = BrainGlobeAtlas("allen_mouse_100um")

# atlas.structures is a dict keyed by acronym string
# Each entry has at minimum:
#   "id"          → int  (matches annotation array values)
#   "rgb_triplet" → [R, G, B]  values 0–255
#   "name"        → str

print(atlas.structures["CP"])
# → {'acronym': 'CP', 'id': 672, 'name': 'Caudoputamen',
#    'rgb_triplet': [152, 214, 249], 'structure_id_path': [...], ...}
```

### 3.8 numpy — efficient colour array repeat (already used)

The existing `_add_mesh` method already converts `rgb_triplet` → `[0-1]`:

```python
vertex_colors = np.repeat(
    [[float(c) / 255 for c in color]], len(points), axis=0
)
```

We reuse the same normalisation pattern for label colours.

---

## 4. The Core Mechanism: napari Labels `color` Parameter

### What the parameter expects

```python
colour_dict: Dict[int, List[float]] = {
    0:    [0.0, 0.0, 0.0, 0.0],   # background – fully transparent
    672:  [0.596, 0.839, 0.976, 1.0],  # CP – Caudoputamen
    ...
}
viewer.add_labels(atlas.annotation, color=colour_dict)
```

Keys are **integer label values** matching the `atlas.annotation` array.
Values are **RGBA** tuples/lists with components in `[0.0, 1.0]`.

### Why label ID 0 needs special treatment

In napari, label `0` is always the **background** and is rendered transparent
regardless of any colour dict entry.  We still include it explicitly for
clarity and forward-compatibility, but omitting it is also safe.

### Behaviour when a label ID is not in the dict

napari falls back to a deterministic hash-based colour for any label not in
`color`.  For a correctly-formed BrainGlobe atlas this should not happen
(every voxel ID has a structure entry), but the fallback is safe.

---

## 5. BrainGlobe Atlas Colour Data

### Where it lives

```
~/.brainglobe/allen_mouse_100um_v1.2/structures.json
```

Each entry in `structures.json`:

```json
{
  "acronym": "CP",
  "id": 672,
  "name": "Caudoputamen",
  "structure_id_path": [997, 8, 567, 688, 695, 315, 672],
  "rgb_triplet": [152, 214, 249]
}
```

### How the API exposes it

```python
atlas.structures          # dict[acronym → dict]
atlas.structures["CP"]["id"]           # 672  (int)
atlas.structures["CP"]["rgb_triplet"]  # [152, 214, 249]  (list[int], 0–255)
```

### Conversion formula (0-255 → 0.0-1.0 RGBA)

```python
rgb = atlas.structures["CP"]["rgb_triplet"]   # [152, 214, 249]
rgba = [c / 255.0 for c in rgb] + [1.0]       # [0.596, 0.839, 0.976, 1.0]
```

---

## 6. Detailed Implementation Plan

### Step 1 – Build the colour dictionary helper

**File:** `brainrender_napari/napari_atlas_representation.py`

Add a **private static method** (no `self` needed — pure data transformation)
to `NapariAtlasRepresentation`:

```python
@staticmethod
def _build_annotation_colour_dict(
    bg_atlas: BrainGlobeAtlas,
) -> dict[int, list[float]]:
    """Return {label_id: [R, G, B, A]} for every atlas structure.

    Colours are sourced from the BrainGlobe canonical rgb_triplet
    (0-255 range) and converted to napari's 0.0-1.0 RGBA format.
    Background label 0 is mapped to fully transparent.
    """
    colour_dict: dict[int, list[float]] = {
        0: [0.0, 0.0, 0.0, 0.0]  # background – transparent
    }
    for structure in bg_atlas.structures.values():
        label_id: int = structure["id"]
        rgb: list[int] = structure["rgb_triplet"]
        colour_dict[label_id] = [c / 255.0 for c in rgb] + [1.0]
    return colour_dict
```

**Why static?**  
- Takes only `bg_atlas` — no viewer or widget state needed.
- Easier to unit-test in isolation (no fixture overhead).
- Documents that it is a pure data transformation.

---

### Step 2 – Apply it in `add_to_viewer`

**File:** `brainrender_napari/napari_atlas_representation.py`

Modify `add_to_viewer` to pass `color=` when `use_preset_colours` is `True`:

```python
def add_to_viewer(self) -> None:
    """Adds the reference and annotation images as layers to the viewer.

    The annotation layer uses the BrainGlobe canonical colours by default
    (use_preset_colours=True).  Set use_preset_colours=False to use
    napari's automatic colour assignment instead.
    """
    reference = self.viewer.add_image(
        self.bg_atlas.reference,
        name=f"{self.bg_atlas.atlas_name}_reference",
        visible=False,
    )

    colour_dict = (
        self._build_annotation_colour_dict(self.bg_atlas)
        if self.use_preset_colours
        else None
    )
    annotation = self.viewer.add_labels(
        self.bg_atlas.annotation,
        name=f"{self.bg_atlas.atlas_name}_annotation",
        color=colour_dict,
    )

    annotation.mouse_move_callbacks.append(self._on_mouse_move)
    reference.mouse_move_callbacks.append(self._on_mouse_move)
```

Also add the new field to the dataclass (one line):

```python
@dataclass
class NapariAtlasRepresentation:
    bg_atlas: BrainGlobeAtlas
    viewer: Viewer
    use_preset_colours: bool = True    # ← ADD THIS LINE
    mesh_opacity: float = 0.4
    mesh_blending: str = "translucent_no_depth"
```

> **Default is `True`**: preset colours are on by default, matching the
> spirit of the feature request.  Existing callers that don't pass
> `use_preset_colours` are unaffected by the interface change.

---

### Step 3 – Add a UI toggle checkbox

**File:** `brainrender_napari/brainrender_viewer_widget.py`

In `__init__`, alongside the existing `show_structure_names` checkbox:

```python
# existing checkbox
self.show_structure_names = QCheckBox()
self.show_structure_names.setChecked(False)
self.show_structure_names.setText("Show region names")
...

# NEW checkbox
self.use_preset_colours = QCheckBox()
self.use_preset_colours.setChecked(True)
self.use_preset_colours.setText("Use preset annotation colours")
self.use_preset_colours.setToolTip(
    "Tick to colour annotation regions with their canonical "
    "BrainGlobe colours.\nUntick for napari's automatic colours."
)
```

Add it to the Atlas Viewer group box layout (below the atlas table):

```python
self.atlas_viewer_group.layout().addWidget(self.atlas_viewer_view)
self.atlas_viewer_group.layout().addWidget(self.use_preset_colours)  # NEW
```

---

### Step 4 – Connect the toggle signal

**File:** `brainrender_napari/brainrender_viewer_widget.py`

In `__init__`, after the existing signal connections:

```python
self.use_preset_colours.stateChanged.connect(
    self._on_use_preset_colours_changed
)
```

Add the handler method:

```python
def _on_use_preset_colours_changed(self) -> None:
    """Update the colour of every annotation layer already in the viewer."""
    use_preset: bool = self.use_preset_colours.isChecked()
    for layer in self._viewer.layers:
        if layer.name.endswith("_annotation"):
            # Identify which atlas this annotation belongs to
            atlas_name = layer.name.removesuffix("_annotation")
            atlas = BrainGlobeAtlas(atlas_name=atlas_name)
            atlas_rep = NapariAtlasRepresentation(
                bg_atlas=atlas, viewer=self._viewer
            )
            if use_preset:
                layer.color = atlas_rep._build_annotation_colour_dict(atlas)
            else:
                layer.color = {}   # empty dict → napari auto-colours
```

> **Why iterate existing layers?**  
> The toggle must affect annotation layers that are *already* in the viewer,
> not just future ones.  Iterating `viewer.layers` and checking the name
> suffix is the minimal approach without adding a separate registry.
>
> **Why re-create `NapariAtlasRepresentation` temporarily?**  
> It's a dataclass — construction is cheap, and this avoids keeping a
> long-lived mapping from atlas name → representation object.  If the
> widget is later refactored to store representations, this can be
> simplified.

---

### Step 5 – Update tests

**File:** `tests/test_unit/test_napari_atlas_representation.py`

#### 5a — New test: preset colours are applied by default

```python
@pytest.mark.parametrize(
    "atlas_name",
    ["example_mouse_100um", "allen_mouse_100um", "osten_mouse_100um"],
)
def test_annotation_uses_preset_colours_by_default(
    make_napari_viewer, atlas_name
):
    """The annotation layer must be coloured with canonical BrainGlobe
    colours when use_preset_colours=True (the default)."""
    viewer = make_napari_viewer()
    atlas = BrainGlobeAtlas(atlas_name=atlas_name)
    atlas_rep = NapariAtlasRepresentation(bg_atlas=atlas, viewer=viewer)
    atlas_rep.add_to_viewer()

    annotation = next(
        layer for layer in viewer.layers if layer.name.endswith("_annotation")
    )
    # Pick any known structure (use the first one alphabetically)
    sample_structure = next(iter(atlas.structures.values()))
    label_id = sample_structure["id"]
    expected_rgb = sample_structure["rgb_triplet"]

    actual_colour = annotation.color[label_id]   # [R, G, B, A] in 0-1
    for actual, expected in zip(actual_colour[:3], expected_rgb):
        assert abs(actual * 255 - expected) < 1e-6
```

#### 5b — New test: `_build_annotation_colour_dict` correctness

```python
def test_build_annotation_colour_dict(make_napari_viewer):
    """The colour dict maps every structure ID to its normalised RGBA,
    and the background label 0 is transparent."""
    viewer = make_napari_viewer()
    atlas = BrainGlobeAtlas("allen_mouse_100um")
    atlas_rep = NapariAtlasRepresentation(bg_atlas=atlas, viewer=viewer)

    colour_dict = atlas_rep._build_annotation_colour_dict(atlas)

    # Background label must be transparent
    assert colour_dict[0] == [0.0, 0.0, 0.0, 0.0]

    # Every structure must have an entry with correct normalised values
    for structure in atlas.structures.values():
        label_id = structure["id"]
        rgb = structure["rgb_triplet"]
        assert label_id in colour_dict
        assert len(colour_dict[label_id]) == 4          # RGBA
        for actual, expected in zip(colour_dict[label_id][:3], rgb):
            assert abs(actual * 255 - expected) < 1e-6
        assert colour_dict[label_id][3] == 1.0          # fully opaque
```

#### 5c — New test: `use_preset_colours=False` uses napari auto-colours

```python
def test_annotation_no_preset_colours_when_disabled(make_napari_viewer):
    """When use_preset_colours=False, add_labels is called without a
    colour dict, leaving napari to assign automatic colours."""
    viewer = make_napari_viewer()
    atlas = BrainGlobeAtlas("allen_mouse_100um")
    atlas_rep = NapariAtlasRepresentation(
        bg_atlas=atlas, viewer=viewer, use_preset_colours=False
    )
    atlas_rep.add_to_viewer()
    annotation = next(
        layer for layer in viewer.layers if layer.name.endswith("_annotation")
    )
    # When no colour dict is supplied napari's auto-colour dict contains
    # no user-defined keys (it only has None → default colour mapping).
    # Verify by checking a known structure colour does NOT match preset.
    sample = next(iter(atlas.structures.values()))
    label_id = sample["id"]
    expected_preset = [c / 255.0 for c in sample["rgb_triplet"]] + [1.0]
    actual = annotation.color.get(label_id, None)
    # Either no entry or a different colour from the preset
    assert actual != expected_preset
```

#### 5d — Existing test `test_add_to_viewer` — verify still passes unchanged

The existing test only checks layer types, names, extents and callbacks.
It does **not** check colours, so it requires no modification.

---

## 7. Potential Bugs & Edge Cases

### Bug 1 — Label ID 0 (background) visible instead of transparent

**Risk:** If `colour_dict[0]` is accidentally given an opaque colour, the
background of every annotation slice will be painted solid.

**Fix:** Always explicitly set `colour_dict[0] = [0.0, 0.0, 0.0, 0.0]` as
the first entry in `_build_annotation_colour_dict`.

---

### Bug 2 — Structure `id` collision

**Risk:** Two structures in a malformed atlas with the same `id` will
silently overwrite each other in the dict comprehension.  Last-write wins.

**Detection:** This is an atlas data quality issue, not a plugin bug.
**Mitigation:** The helper iterates `atlas.structures.values()` — if the
atlas is well-formed (all IDs unique, guaranteed by BrainGlobe), no collision
occurs.  No additional code needed; document the assumption.

---

### Bug 3 — `layer.color = {}` does not restore full auto-colour

**Risk:** Setting `layer.color = {}` clears the explicit mappings but may
leave cached colours in napari's colour engine until the layer is refreshed.

**Fix:** After setting `layer.color = {}`, call `layer.refresh()` to force
a repaint:

```python
layer.color = {}
layer.refresh()
```

---

### Bug 4 — `_on_use_preset_colours_changed` re-creates `BrainGlobeAtlas`

**Risk:** `BrainGlobeAtlas` loads data from disk each time it is constructed.
On slow file systems, toggling the checkbox may be sluggish.

**Mitigation (minimal):** `atlas.structures` is a small JSON dict, not the
volumetric data; construction is fast (~milliseconds).  No code change
needed for v1.  Document as a known trade-off.

**Future improvement:** Cache `{atlas_name: NapariAtlasRepresentation}` in
the widget if performance becomes an issue.

---

### Bug 5 — `layer.name.removesuffix` requires Python ≥ 3.9

**Risk:** `str.removesuffix` was added in Python 3.9.

**Check:** `pyproject.toml` states `requires-python = ">=3.11.0"`.  
**Conclusion:** Safe to use — no issue.

---

### Bug 6 — Atlas layer name collision

**Risk:** If the user loads the same atlas twice, two layers share the same
`_annotation` suffix pattern.  The toggle handler will update both.

**Behaviour:** Both layers updated with the same colour dict → correct and
benign.  No fix needed.

---

### Bug 7 — Missing `rgb_triplet` key in a non-standard atlas

**Risk:** A community-contributed atlas might omit `rgb_triplet` from some
structures.

**Fix:** Guard inside the helper:

```python
for structure in bg_atlas.structures.values():
    label_id = structure["id"]
    rgb = structure.get("rgb_triplet", None)
    if rgb is not None:
        colour_dict[label_id] = [c / 255.0 for c in rgb] + [1.0]
    # If rgb_triplet absent, napari will auto-colour that label
```

---

### Bug 8 — Annotation layer `color` property API change across napari versions

**Risk:** napari ≥ 0.6 may change how `Labels.color` is accessed.

**Mitigation:** The project already requires `napari >= 0.6.1`; pin the
version and test against it in CI.  The `color` property has been stable
since napari 0.4.x.

---

## 8. Test Plan

| Test | File | What it checks |
|---|---|---|
| `test_annotation_uses_preset_colours_by_default` | `test_napari_atlas_representation.py` | Annotation layer colour dict matches `rgb_triplet` (parametrised over 3 atlases) |
| `test_build_annotation_colour_dict` | `test_napari_atlas_representation.py` | Helper returns correct RGBA, background is transparent, alpha=1.0 |
| `test_annotation_no_preset_colours_when_disabled` | `test_napari_atlas_representation.py` | `use_preset_colours=False` → no preset colour applied |
| `test_add_to_viewer` (existing) | `test_napari_atlas_representation.py` | No modification needed; still passes |
| `test_preset_colour_toggle` (new integration) | `test_brainrender_viewer_widget.py` | Toggling checkbox updates all annotation layers live |

### Integration test sketch

```python
def test_preset_colour_toggle(make_napari_viewer, qtbot):
    """Toggling the preset-colour checkbox updates annotation layers live."""
    viewer = make_napari_viewer()
    widget = BrainrenderViewerWidget(napari_viewer=viewer)

    # Simulate adding an atlas
    atlas = BrainGlobeAtlas("allen_mouse_100um")
    atlas_rep = NapariAtlasRepresentation(bg_atlas=atlas, viewer=viewer)
    atlas_rep.add_to_viewer()

    annotation = next(
        layer for layer in viewer.layers if layer.name.endswith("_annotation")
    )
    sample = next(iter(atlas.structures.values()))
    label_id = sample["id"]
    expected_preset = [c / 255.0 for c in sample["rgb_triplet"]] + [1.0]

    # Initially preset colours should be active
    assert widget.use_preset_colours.isChecked()
    assert annotation.color.get(label_id) == expected_preset

    # Uncheck → auto colours
    widget.use_preset_colours.setChecked(False)
    assert annotation.color.get(label_id) != expected_preset

    # Re-check → preset colours restored
    widget.use_preset_colours.setChecked(True)
    assert annotation.color.get(label_id) == expected_preset
```

---

## 9. Execution Checklist

```
Files to change (in order):
─────────────────────────────────────────────────────
[ ] 1. brainrender_napari/napari_atlas_representation.py
        [a] Add field `use_preset_colours: bool = True` to dataclass
        [b] Add static method `_build_annotation_colour_dict`
        [c] Update `add_to_viewer` to pass `color=` conditionally

[ ] 2. brainrender_napari/brainrender_viewer_widget.py
        [a] Add `self.use_preset_colours` QCheckBox (checked by default)
        [b] Add it to atlas_viewer_group layout
        [c] Connect stateChanged → `_on_use_preset_colours_changed`
        [d] Implement `_on_use_preset_colours_changed`

[ ] 3. tests/test_unit/test_napari_atlas_representation.py
        [a] Add `test_annotation_uses_preset_colours_by_default`
        [b] Add `test_build_annotation_colour_dict`
        [c] Add `test_annotation_no_preset_colours_when_disabled`

[ ] 4. tests/test_integration/test_brainrender_viewer_widget.py
        [a] Add `test_preset_colour_toggle`

[ ] 5. Run existing test suite: `pytest tests/` – all green
[ ] 6. Manual smoke test in napari: double-click atlas, verify colours
[ ] 7. Run linters: `ruff check .` and `mypy brainrender_napari/`
```

---

## Complete Diff Summary (lines added / modified)

| File | Lines added | Lines modified |
|---|---|---|
| `napari_atlas_representation.py` | ~20 | 6 |
| `brainrender_viewer_widget.py` | ~25 | 2 |
| `test_napari_atlas_representation.py` | ~55 | 0 |
| `test_brainrender_viewer_widget.py` | ~30 | 0 |
| **Total** | **~130** | **8** |

This is the **minimum viable change** that:

- Colours annotation regions with canonical BrainGlobe preset colours.
- Does not remove any existing functionality.
- Is backward-compatible (default `True` means existing callers are unaffected).
- Includes a live-toggle UI control.
- Is fully tested.
- Handles all identified edge cases.
