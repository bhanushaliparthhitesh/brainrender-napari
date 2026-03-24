# brainrender-napari — Functionality Extension Plan

> **Purpose:** A professional, theory-tested plan for extending
> `brainrender-napari` with new functionality using minimal code.
> Includes a complete function reference, identified bugs, required
> Python/Qt concepts, and a full testing and documentation strategy.

---

## Table of Contents

1. [Repository Overview](#1-repository-overview)
2. [Complete Function Reference](#2-complete-function-reference)
3. [Identified Bugs & Issues](#3-identified-bugs--issues)
4. [Proposed New Functionality](#4-proposed-new-functionality)
5. [Professional Execution Plan](#5-professional-execution-plan)
6. [Python & Qt Concepts Required](#6-python--qt-concepts-required)
7. [Testing Strategy](#7-testing-strategy)
8. [Documentation Requirements](#8-documentation-requirements)
9. [Dependency Impact](#9-dependency-impact)

---

## 1. Repository Overview

### Architecture

```
brainrender-napari (Pre-Alpha v0.0.1)
│
├── napari Plugin Entry Points (napari.yaml)
│   ├── BrainrenderViewerWidget  – view & visualise downloaded atlases
│   └── BrainrenderManagerWidget – download & update atlases
│
├── Data Layer
│   ├── AtlasTableModel      – QAbstractTableModel (atlas list)
│   └── StructureTreeModel   – QAbstractItemModel (brain region tree)
│
├── View Layer
│   ├── AtlasViewerView      – QTableView (viewer tab)
│   ├── AtlasManagerView     – QTableView (manager tab)
│   ├── StructureView        – QTreeView  (brain region tree)
│   ├── AtlasProgressBar     – QProgressBar
│   ├── AtlasManagerFilter   – QWidget (search box)
│   └── AtlasManagerDialog   – QDialog (confirm download/update)
│
├── Bridge Layer
│   └── NapariAtlasRepresentation – @dataclass bridging BrainGlobeAtlas ↔ napari
│
└── Utilities
    ├── formatting.py    – format_atlas_name, format_bytes
    └── load_user_data.py – read_atlas_metadata_from_file, read_atlas_structures_from_file
```

### Signal/Slot Connection Map

```
AtlasViewerView.add_atlas_requested        → BrainrenderViewerWidget._on_add_atlas_requested
AtlasViewerView.additional_reference_requested → BrainrenderViewerWidget._on_additional_reference_requested
AtlasViewerView.selected_atlas_changed     → BrainrenderViewerWidget._on_atlas_selection_changed
StructureView.add_structure_requested      → BrainrenderViewerWidget._on_add_structure_requested
QCheckBox.clicked                          → BrainrenderViewerWidget._on_show_structure_names_clicked

AtlasManagerView.progress_updated          → AtlasProgressBar.update_progress
AtlasManagerView.download_atlas_confirmed  → AtlasProgressBar.operation_completed
AtlasManagerView.update_atlas_confirmed    → AtlasProgressBar.operation_completed
```

---

## 2. Complete Function Reference

### 2.1 `NapariAtlasRepresentation` (napari_atlas_representation.py)

```python
@dataclass
class NapariAtlasRepresentation:
    bg_atlas: BrainGlobeAtlas
    viewer: Viewer
    mesh_opacity: float = 0.4
    mesh_blending: str = "translucent_no_depth"
```

| Method | Signature | Responsibility |
|--------|-----------|----------------|
| `__post_init__` | `() -> None` | Creates a floating `QLabel` tooltip; enables napari layer tooltips via settings |
| `add_to_viewer` | `() -> None` | Adds reference image (hidden) + annotation labels layer to viewer; attaches mouse-move callback |
| `add_structure_to_viewer` | `(structure_name: str) -> None` | Fetches mesh from atlas API, scales to pixel space, calls `_add_mesh` |
| `_add_mesh` | `(mesh: Mesh, scale: list, name: str, color=None) -> None` | Low-level helper: converts `meshio.Mesh` into napari surface layer |
| `add_additional_reference` | `(additional_reference_key: str) -> None` | Adds alternative reference image layer; attaches mouse-move callback |
| `_on_mouse_move` | `(layer, event) -> None` | Tooltip callback: queries atlas API for structure name & hemisphere at cursor |

---

### 2.2 `BrainrenderViewerWidget` (brainrender_viewer_widget.py)

```python
class BrainrenderViewerWidget(QWidget):
    _viewer: Viewer
    atlas_viewer_view: AtlasViewerView
    show_structure_names: QCheckBox
    structure_view: StructureView
```

| Method | Signature | Responsibility |
|--------|-----------|----------------|
| `__init__` | `(napari_viewer: Viewer) -> None` | Builds layout, creates sub-widgets, wires all signal-slot connections |
| `_on_add_structure_requested` | `(structure_name: str) -> None` | Creates `BrainGlobeAtlas` + `NapariAtlasRepresentation`; calls `add_structure_to_viewer` |
| `_on_additional_reference_requested` | `(additional_reference_name: str) -> None` | Creates atlas representation; calls `add_additional_reference` |
| `_on_atlas_selection_changed` | `(atlas_name: str) -> None` | Refreshes structure tree; shows/hides structure group depending on download state |
| `_on_add_atlas_requested` | `(atlas_name: str) -> None` | Creates atlas representation; calls `add_to_viewer` |
| `_on_show_structure_names_clicked` | `() -> None` | Reads checkbox state; refreshes structure view |

---

### 2.3 `BrainrenderManagerWidget` (brainrender_manager_widget.py)

```python
class BrainrenderManagerWidget(QWidget):
    _viewer: Viewer
    atlas_manager_view: AtlasManagerView
    atlas_manager_filter: AtlasManagerFilter
    progress_bar: AtlasProgressBar
```

| Method | Signature | Responsibility |
|--------|-----------|----------------|
| `__init__` | `(napari_viewer: Viewer) -> None` | Builds layout, creates sub-widgets, wires signal-slot connections |

---

### 2.4 `AtlasTableModel` (data_models/atlas_table_model.py)

```python
class AtlasTableModel(QAbstractTableModel):
    column_headers: list[str]  # ["Raw name", "Atlas", "Local version", "Latest version"]
    view_type: QTableView
    _data: list[list[str]]
```

| Method | Signature | Responsibility |
|--------|-----------|----------------|
| `__init__` | `(view_type: QTableView)` | Validates view_type has `get_tooltip_text`; calls `refresh_data` |
| `refresh_data` | `() -> None` | Queries `get_all_atlases_lastversions` + `get_atlases_lastversions`; rebuilds `_data` |
| `data` | `(index, role=Qt.DisplayRole)` | Returns display text, tooltip text, or background brush |
| `rowCount` | `(index=QModelIndex()) -> int` | `len(self._data)` |
| `columnCount` | `(index=QModelIndex()) -> int` | `len(self._data[0])` |
| `headerData` | `(section, orientation, role)` | Returns column header text; raises `ValueError` for out-of-range section |

---

### 2.5 `StructureTreeModel` + `StructureTreeItem` (widgets/structure_view.py)

```python
class StructureTreeItem:
    parent_item: StructureTreeItem | None
    item_data: tuple          # (acronym, name, id)
    child_items: list
```

| Method | Signature | Responsibility |
|--------|-----------|----------------|
| `__init__` | `(data, parent=None)` | Stores data tuple and parent reference |
| `appendChild` | `(item) -> None` | Appends child to `child_items` |
| `child` | `(row) -> StructureTreeItem` | Returns child at `row` index |
| `childCount` | `() -> int` | `len(self.child_items)` |
| `columnCount` | `() -> int` | `len(self.item_data)` |
| `data` | `(column)` | Returns `item_data[column]`; returns `None` on `IndexError` |
| `parent` | `()` | Returns `parent_item` |
| `row` | `()` | Returns index of self in parent's `child_items`; 0 for root |

```python
class StructureTreeModel(QAbstractItemModel):
    root_item: StructureTreeItem
```

| Method | Signature | Responsibility |
|--------|-----------|----------------|
| `__init__` | `(data: List, parent=None)` | Creates root item; calls `build_structure_tree` |
| `build_structure_tree` | `(structures, root)` | Iterates `get_structures_tree().expand_tree()` in sorted order; inserts items parent-first |
| `data` | `(index, role=Qt.DisplayRole)` | Display-role only; delegates to `StructureTreeItem.data` |
| `rowCount` | `(parent)` | Child count of item at `parent`; 0 for non-root columns |
| `columnCount` | `(parent)` | Column count from item |
| `parent` | `(index)` | Returns parent's first-column index; empty index for root |
| `index` | `(row, column, parent=QModelIndex())` | Creates model index using `createIndex` |

---

### 2.6 `StructureView` (widgets/structure_view.py)

```python
class StructureView(QTreeView):
    add_structure_requested = Signal(str)
```

| Method | Signature | Responsibility |
|--------|-----------|----------------|
| `__init__` | `(parent=None)` | Wires double-click + expand-to-resize-column signals |
| `refresh` | `(selected_atlas_name, show_structure_names=False)` | Rebuilds model; shows/hides name column; expands to depth 0; hides view if atlas not downloaded |
| `selected_structure_acronym` | `() -> str` | Returns acronym from current selection (asserts valid index) |
| `_on_row_double_clicked` | `()` | Emits `add_structure_requested` with acronym |

---

### 2.7 `AtlasManagerView` (widgets/atlas_manager_view.py)

```python
class AtlasManagerView(QTableView):
    download_atlas_confirmed = Signal(str)
    update_atlas_confirmed   = Signal(str)
    progress_updated         = Signal(int, int, str, object)
    source_model: AtlasTableModel
    proxy_model: QSortFilterProxyModel
    hidden_columns: list[str]
```

| Method | Signature | Responsibility |
|--------|-----------|----------------|
| `__init__` | `(parent=None)` | Creates model + proxy; hides raw name column; connects double-click |
| `_on_row_double_clicked` | `() -> None` | Checks if downloaded + up-to-date; shows dialog; triggers download or update |
| `_on_download_atlas_confirmed` | `() -> None` | Starts threaded `install_atlas`; emits progress; refreshes model on completion |
| `_on_update_atlas_confirmed` | `() -> None` | Starts threaded `update_atlas`; emits progress; refreshes model on completion |
| `selected_atlas_name` | `() -> str` | Resolves current proxy index to raw atlas name (column 0) |
| `_apply_in_thread` | `(apply: Callable, *args, **kwargs)` | `@thread_worker` helper; runs callable in napari worker thread |
| `get_tooltip_text` | `(atlas_name: str) -> str` | `@classmethod`; returns formatted status tooltip |

---

### 2.8 `AtlasViewerView` (widgets/atlas_viewer_view.py)

```python
class AtlasViewerView(QTableView):
    add_atlas_requested            = Signal(str)
    no_atlas_available             = Signal()
    additional_reference_requested = Signal(str)
    selected_atlas_changed         = Signal(str)
```

| Method | Signature | Responsibility |
|--------|-----------|----------------|
| `__init__` | `(parent=None)` | Creates model; hides non-local rows + metadata columns; wires signals |
| `selected_atlas_name` | `() -> str` | Returns current selection's raw atlas name; asserts validity |
| `_on_context_menu_requested` | `(position: Tuple[float]) -> None` | Opens context menu of additional references for selected atlas |
| `_on_row_double_clicked` | `() -> None` | Emits `add_atlas_requested` with atlas name |
| `_on_current_changed` | `() -> None` | Emits `selected_atlas_changed` |
| `get_tooltip_text` | `(atlas_name: str) -> str` | `@classmethod`; returns full metadata tooltip |

---

### 2.9 `AtlasProgressBar` (widgets/atlas_progress_bar.py)

```python
class AtlasProgressBar(QProgressBar):
```

| Method | Signature | Responsibility |
|--------|-----------|----------------|
| `__init__` | `(parent=None)` | Configures text-visible, centered style; hides by default |
| `update_progress` | `(completed, total, atlas_name, operation_type) -> None` | Calculates percentage; sets value + format text; shows widget |
| `operation_completed` | `() -> None` | Sets value to maximum; hides widget |

---

### 2.10 `AtlasManagerFilter` (widgets/atlas_manager_filter.py)

```python
class AtlasManagerFilter(QWidget):
    atlas_manager_view: AtlasManagerView
    query_field: QLineEdit
    column_field: QComboBox
```

| Method | Signature | Responsibility |
|--------|-----------|----------------|
| `__init__` | `(atlas_manager_view, parent=None)` | Stores view ref; calls `setup_ui` |
| `setup_ui` | `() -> None` | Creates `QLineEdit` + `QComboBox`; populates column options; wires change signals |
| `apply` | `() -> None` | Reads query + column; sets proxy filter key column and filter string |

---

### 2.11 `AtlasManagerDialog` (widgets/atlas_manager_dialog.py)

```python
class AtlasManagerDialog(QDialog):
    label: QLabel
    ok_button: QPushButton
    cancel_button: QPushButton
```

| Method | Signature | Responsibility |
|--------|-----------|----------------|
| `__init__` | `(atlas_name: str, action: str)` | Validates atlas name; builds confirmation UI; raises `ValueError` for unknown atlas |

---

### 2.12 Utility Functions

```python
# brainrender_napari/utils/formatting.py
def format_atlas_name(name: str) -> str
def format_bytes(num_bytes: float) -> str

# brainrender_napari/utils/load_user_data.py
def read_atlas_metadata_from_file(atlas_name: str) -> dict
def read_atlas_structures_from_file(atlas_name: str) -> list
```

---

## 3. Identified Bugs & Issues

### Bug 1 — Memory leak: repeated `NapariAtlasRepresentation` instances

**Location:** `BrainrenderViewerWidget._on_add_structure_requested`,
`_on_additional_reference_requested`

**Code:**
```python
def _on_add_structure_requested(self, structure_name: str) -> None:
    selected_atlas = BrainGlobeAtlas(...)
    selected_atlas_representation = NapariAtlasRepresentation(...)  # new each call!
    selected_atlas_representation.add_structure_to_viewer(structure_name)
```

**Problem:** Every invocation of `_on_add_structure_requested` constructs a
new `NapariAtlasRepresentation`, which in `__post_init__` creates a new
`QLabel` tooltip widget. After N structure additions there are N orphaned
tooltip widgets consuming memory and potentially intercepting Qt events.

**Fix (minimal):** Cache one `NapariAtlasRepresentation` per atlas name in a
dict on `BrainrenderViewerWidget`:
```python
self._atlas_representations: dict[str, NapariAtlasRepresentation] = {}

def _get_or_create_representation(self, atlas_name: str) -> NapariAtlasRepresentation:
    if atlas_name not in self._atlas_representations:
        self._atlas_representations[atlas_name] = NapariAtlasRepresentation(
            bg_atlas=BrainGlobeAtlas(atlas_name), viewer=self._viewer
        )
    return self._atlas_representations[atlas_name]
```

---

### Bug 2 — `assert` used for input validation (silently disabled with `-O`)

**Location:** `AtlasViewerView.selected_atlas_name`,
`AtlasManagerView.selected_atlas_name`,
`StructureView.selected_structure_acronym`

**Code:**
```python
def selected_atlas_name(self) -> str:
    selected_index = self.selectionModel().currentIndex()
    assert selected_index.isValid()   # ← disabled in optimised mode
    ...
```

**Problem:** Python's `-O` (optimise) flag disables all `assert` statements.
In production napari installations where Python is run optimised, these
assertions are silently skipped, and downstream code receives an invalid
model index, leading to opaque crashes.

**Fix:** Replace `assert` with explicit `if not ... raise ValueError` or guard
the call site to only call when a selection is confirmed valid.

---

### Bug 3 — `AtlasTableModel.columnCount` crashes on empty data

**Location:** `AtlasTableModel.columnCount`

**Code:**
```python
def columnCount(self, index=QModelIndex()) -> int:
    return len(self._data[0])  # IndexError if _data is []
```

**Problem:** If `get_all_atlases_lastversions()` returns an empty dict
(network failure, empty registry), `self._data` will be `[]` and
`self._data[0]` raises `IndexError`.

**Fix:**
```python
def columnCount(self, index=QModelIndex()) -> int:
    return len(self._data[0]) if self._data else len(self.column_headers)
```

---

### Bug 4 — `_on_mouse_move` excludes coordinate 0 (valid atlas boundary)

**Location:** `NapariAtlasRepresentation._on_mouse_move`

**Code:**
```python
if (
    tooltip_visibility
    and np.all(np.array(cursor_position) > 0)  # ← strict >
    and self.viewer.dims.ndisplay == 2
):
```

**Problem:** The condition `> 0` excludes the slice at index 0 (e.g. the top
row or first slice of the volume). For any atlas, coordinate 0 along any axis
is a perfectly valid position that may contain structures. The tooltip will
silently not display for these voxels.

**Fix:** Change the guard to `>= 0` and additionally check against the shape
of the annotation array to detect out-of-bounds.

---

### Bug 5 — Internal napari API access (`qt_viewer`) may break across versions

**Location:** `NapariAtlasRepresentation.__post_init__`

**Code:**
```python
self._tooltip = QLabel(self.viewer.window.qt_viewer.parent())
```

**Problem:** `viewer.window.qt_viewer` is an internal (private) napari
attribute that has been deprecated and removed in some development builds.
This line will raise `AttributeError` on newer napari versions.

**Fix:** Use a safer parent widget lookup:
```python
parent_widget = self.viewer.window._qt_window  # still internal but more stable
# or use None as parent (floating widget):
self._tooltip = QLabel()
```

---

### Bug 6 — `AtlasManagerFilter` shadows `QWidget.layout()` method

**Location:** `AtlasManagerFilter.setup_ui`

**Code:**
```python
def setup_ui(self) -> None:
    self.layout = QHBoxLayout(self)   # ← shadows QWidget.layout()
```

**Problem:** Assigning `self.layout = QHBoxLayout(self)` shadows the
inherited `QWidget.layout()` method. Any code that later calls
`self.layout()` (expecting the method) will instead get the `QHBoxLayout`
object and fail with `TypeError: 'QHBoxLayout' object is not callable`.

**Fix:** Rename the attribute:
```python
self._filter_layout = QHBoxLayout(self)
```

---

### Bug 7 — `AtlasViewerView._on_context_menu_requested` can crash if no row is selected

**Location:** `AtlasViewerView._on_context_menu_requested`

**Code:**
```python
def _on_context_menu_requested(self, position):
    selected_atlas_name = self.selected_atlas_name()  # asserts valid index
```

**Problem:** A right-click on an empty area of the table (no row selected)
will call `selected_atlas_name()`, which will fail at
`assert selected_index.isValid()` with `AssertionError`.

**Fix:** Guard with validity check before calling `selected_atlas_name`:
```python
def _on_context_menu_requested(self, position):
    if not self.selectionModel().currentIndex().isValid():
        return
    selected_atlas_name = self.selected_atlas_name()
```

---

### Bug 8 — `format_atlas_name` fails for non-standard atlas name formats

**Location:** `brainrender_napari/utils/formatting.py`

**Code:**
```python
def format_atlas_name(name: str) -> str:
    formatted_name = name.split("_")
    formatted_name[-1] = f"({formatted_name[-1].split('um')[0]} μm)"
```

**Problem:** If the atlas name does not end in `_NUMBERum` (e.g. a future
atlas named `custom_atlas_v2`), `formatted_name[-1].split('um')[0]` returns
the whole final token and the result looks like `(custom_atlas_v2 μm)`.
No `ValueError` is raised — it silently produces malformed output.

**Fix:** Add a validation step or make the formatting conditional:
```python
def format_atlas_name(name: str) -> str:
    parts = name.split("_")
    parts[0] = parts[0].capitalize()
    if parts[-1].endswith("um"):
        parts[-1] = f"({parts[-1][:-2]} μm)"
    return " ".join(parts)
```

---

### Bug 9 — Thread-safety: `source_model.refresh_data()` called from lambda in worker thread

**Location:** `AtlasManagerView._on_download_atlas_confirmed`,
`_on_update_atlas_confirmed`

**Code:**
```python
worker.returned.connect(
    lambda result: [
        self.download_atlas_confirmed.emit(result),
        self.source_model.refresh_data(),   # ← called in worker's returned signal
    ]
)
```

**Problem:** `worker.returned` fires in the Qt main thread (this is correct
for napari workers), so `refresh_data()` is called on the main thread.
However, `refresh_data()` internally calls `get_all_atlases_lastversions()`
which may perform file I/O or network access — blocking the UI thread.

**Fix:** Move the refresh into a separate `@thread_worker` or use
`QTimer.singleShot(0, self.source_model.refresh_data)` to defer it.

---

### Bug 10 — `AtlasManagerDialog`: `super().__init__()` not called on invalid atlas name

**Location:** `AtlasManagerDialog.__init__`

**Code:**
```python
def __init__(self, atlas_name: str, action: str) -> None:
    if atlas_name in get_all_atlases_lastversions().keys():
        super().__init__()   # ← only called in success path
        ...
    else:
        raise ValueError(...)
```

**Problem:** Python's `QDialog.__init__` is never called in the error path,
but this is acceptable because `ValueError` is raised before the object is
used. However, if a caller catches `ValueError` and still calls Qt methods on
the partially-initialised `QDialog`, Qt will segfault. The pattern is fragile.

**Fix:** Call `super().__init__()` unconditionally first, then validate:
```python
def __init__(self, atlas_name: str, action: str) -> None:
    super().__init__()
    if atlas_name not in get_all_atlases_lastversions().keys():
        raise ValueError("Atlas manager dialog called with invalid atlas name.")
    ...  # build UI
```

---

## 4. Proposed New Functionality

The following features are ordered by impact-to-effort ratio (highest first).
Each feature is designed to use the minimum code possible by reusing existing
patterns in the codebase.

### F1 — Structure Search / Filter in Tree View

**Value:** The structure tree can contain hundreds of regions. Users need to
be able to search by name or acronym.

**Minimal Implementation:** Reuse the existing `AtlasManagerFilter` pattern
(a `QLineEdit` + `QSortFilterProxyModel`) and apply it to `StructureView`.

**New/modified files:**
- `brainrender_napari/widgets/structure_view.py` — add
  `QSortFilterProxyModel`; wrap existing model in proxy
- `brainrender_napari/brainrender_viewer_widget.py` — add search box above
  structure tree

**Estimated lines of new code:** ~35

---

### F2 — Batch Structure Addition (Multi-Select)

**Value:** Currently only single-select is possible. Researchers often need to
add 5–20 structures at once for comparative visualisation.

**Minimal Implementation:** Change `StructureView`'s selection mode to
`ExtendedSelection` and update `_on_row_double_clicked` to emit signals for
all selected rows. A new `Add selected` button would also work.

**New/modified files:**
- `brainrender_napari/widgets/structure_view.py` — add multi-select button or
  keyboard shortcut (`Return` key)

**Estimated lines of new code:** ~20

---

### F3 — Layer Opacity / Colour Controls for Meshes

**Value:** Researchers need to adjust mesh opacity and colour after adding
structures, without removing and re-adding layers.

**Minimal Implementation:** Add a `QSlider` for opacity and a `QPushButton`
that opens `QColorDialog`. These connect to the corresponding napari surface
layer's `opacity` and `vertex_colors` properties.

**New/modified files:**
- New file: `brainrender_napari/widgets/layer_controls_widget.py`
- `brainrender_napari/brainrender_viewer_widget.py` — embed widget

**Estimated lines of new code:** ~80

---

### F4 — Export Current View as Screenshot

**Value:** Quick documentation of analysis results without leaving napari.

**Minimal Implementation:** napari's `Viewer.screenshot()` method already
does this. A single button with a `QFileDialog` to choose the save path is all
that's needed.

**New/modified files:**
- `brainrender_napari/brainrender_viewer_widget.py` — add export button
- New helper: `brainrender_napari/utils/export.py`

**Estimated lines of new code:** ~25

---

### F5 — Atlas Metadata Expanded Panel

**Value:** The tooltip currently shows metadata on hover, but users need a
persistent panel to read and copy metadata values.

**Minimal Implementation:** A collapsible `QGroupBox` that populates a
`QTextEdit` with formatted metadata JSON when an atlas is selected.

**New/modified files:**
- New file: `brainrender_napari/widgets/atlas_metadata_panel.py`
- `brainrender_napari/brainrender_viewer_widget.py` — embed panel

**Estimated lines of new code:** ~60

---

### F6 — Structure Highlight on Hover (2D tooltip upgrade)

**Value:** Rather than just a text tooltip, highlight the hovered region with
a bounding box or colour overlay.

**Minimal Implementation:** On `_on_mouse_move`, add the structure's bounding
box as a `viewer.add_shapes` layer with ephemeral lifetime (removed on next
move). The bounding box is computed from `bg_atlas.structures[acronym]["mesh"]`
bounds.

**New/modified files:**
- `brainrender_napari/napari_atlas_representation.py` — extend `_on_mouse_move`

**Estimated lines of new code:** ~30

---

### F7 — Atlas Version History Panel

**Value:** Researchers need to see what changed between atlas versions before
deciding to update.

**Minimal Implementation:** Call the BrainGlobe API's changelog endpoint (if
available) or parse the GitHub releases page for the relevant atlas repo. Show
in a `QTextBrowser` with clickable links.

**New/modified files:**
- New file: `brainrender_napari/widgets/atlas_version_history.py`
- `brainrender_napari/brainrender_manager_widget.py` — embed panel

**Estimated lines of new code:** ~70

---

### F8 — Atlas Comparison Mode (Side-by-side)

**Value:** Power users want to compare two atlas versions or two different
species atlases in a split napari viewer.

**Minimal Implementation:** napari supports grid mode. Add a button that calls
`viewer.grid.enabled = True` and adds a second atlas to a different viewer
grid position.

**New/modified files:**
- `brainrender_napari/brainrender_viewer_widget.py` — add comparison button
- `brainrender_napari/napari_atlas_representation.py` — parameterise grid slot

**Estimated lines of new code:** ~40

---

## 5. Professional Execution Plan

This plan follows the principle of **minimal, safe, incremental changes** with
full test coverage before merging any phase.

### Phase 0 — Prerequisite: Bug Fixes (Sprint 1, ~3 days)

All bug fixes must precede new features to avoid building on a broken
foundation.

**Checklist:**
- [ ] Fix Bug 3: `columnCount` crash on empty data (`atlas_table_model.py`)
- [ ] Fix Bug 6: `layout` attribute shadowing (`atlas_manager_filter.py`)
- [ ] Fix Bug 7: context menu right-click crash (`atlas_viewer_view.py`)
- [ ] Fix Bug 8: `format_atlas_name` for non-standard names (`formatting.py`)
- [ ] Fix Bug 10: `AtlasManagerDialog` `super().__init__()` ordering
- [ ] Fix Bug 4: mouse move `> 0` → `>= 0` (`napari_atlas_representation.py`)
- [ ] Fix Bug 2: replace `assert` with explicit `ValueError` in all `selected_*` methods
- [ ] Write regression tests for each fix (one test per bug, in existing test files)

**Commit strategy:** One commit per bug fix with test.

---

### Phase 1 — Quick Wins (Sprint 2, ~3 days)

High-value, low-risk features that reuse existing patterns.

**1a. Structure Search (F1)**

```
Step 1: In StructureView.__init__, create a QSortFilterProxyModel and
        set the source to the StructureTreeModel when refresh() is called.
Step 2: Add a QLineEdit above the tree in BrainrenderViewerWidget (similar
        to AtlasManagerFilter but inline).
Step 3: Connect QLineEdit.textChanged → proxy.setFilterFixedString.
Step 4: Set proxy.setFilterCaseSensitivity(Qt.CaseInsensitive).
Step 5: Set proxy.setFilterKeyColumn(-1)  # search both acronym and name.
Step 6: Write unit tests: search "cortex" returns only cortex rows.
```

**1b. Export Screenshot (F4)**

```
Step 1: Add a QPushButton "Save screenshot" to BrainrenderViewerWidget.
Step 2: Connect to a new slot _on_save_screenshot_clicked().
Step 3: Slot opens QFileDialog.getSaveFileName with PNG/TIFF filters.
Step 4: If path is selected, call viewer.screenshot(path=path, canvas_only=True).
Step 5: Show napari show_info("Screenshot saved to {path}").
Step 6: Write integration test: mock QFileDialog; verify file is written.
```

---

### Phase 2 — Core Enhancements (Sprint 3, ~5 days)

**2a. Batch Structure Addition (F2)**

```
Step 1: Change StructureView selection mode to
        QAbstractItemView.ExtendedSelection.
Step 2: Add a QPushButton "Add selected structures" below the tree.
Step 3: Button click iterates all selected rows, emitting
        add_structure_requested for each valid acronym.
Step 4: Keep double-click behaviour as-is for single-structure workflow.
Step 5: Write unit tests: select 3 rows, click button, verify 3 signals.
```

**2b. Mesh Opacity Control (F3 — simplified)**

```
Step 1: After add_structure_to_viewer, retrieve the newly added surface layer
        by name from viewer.layers.
Step 2: Add a QSlider (range 0–100, default 40) labeled "Mesh opacity".
Step 3: Connect QSlider.valueChanged → update the opacity of ALL surface
        layers matching the pattern "{atlas_name}_*_mesh".
Step 4: Persist slider value per atlas in BrainrenderViewerWidget.
Step 5: Write unit tests: set slider to 80, verify layer.opacity == 0.8.
```

---

### Phase 3 — Extended Features (Sprint 4, ~7 days)

**3a. Atlas Metadata Panel (F5)**

```
Step 1: Create AtlasMetadataPanel(QGroupBox) in new file
        brainrender_napari/widgets/atlas_metadata_panel.py.
Step 2: Panel contains a QTextEdit (read-only) + "Copy" QPushButton.
Step 3: BrainrenderViewerWidget connects selected_atlas_changed to
        AtlasMetadataPanel.update(atlas_name).
Step 4: update() calls read_atlas_metadata_from_file and formats as text.
Step 5: "Copy" button copies text to system clipboard.
Step 6: Panel is collapsible (use QGroupBox checkable=True).
Step 7: Write unit tests for each public method of AtlasMetadataPanel.
```

**3b. Structure Highlight on Hover (F6)**

```
Step 1: In NapariAtlasRepresentation, add _highlight_layer: Optional[Layer]
        attribute initialised to None.
Step 2: In _on_mouse_move, after resolving structure_acronym, compute the
        structure's bounds from bg_atlas.structures[acronym].
Step 3: If _highlight_layer exists, remove it from viewer.layers.
Step 4: Add a shapes layer (rectangle) matching the bounding box.
Step 5: Store reference in _highlight_layer.
Step 6: Performance consideration: skip highlight if cursor hasn't moved to a
        different structure (cache last acronym).
Step 7: Write unit tests: mock cursor position; verify shapes layer is added.
```

---

### Phase 4 — Advanced Features (Sprint 5, ~10 days)

**4a. Atlas Version History (F7)**

```
Step 1: Create AtlasVersionHistoryWidget(QWidget) in new file.
Step 2: On atlas selection in manager view, call background worker to fetch
        changelog from BrainGlobe GitHub API
        (https://api.github.com/repos/brainglobe/{atlas_name}/releases).
Step 3: Display results in QTextBrowser (HTML formatted).
Step 4: Cache results per atlas to avoid repeated network calls.
Step 5: Handle network failure gracefully: show "Changelog unavailable".
Step 6: Write tests with mocked HTTP responses using pytest-mock.
```

**4b. Atlas Comparison Mode (F8)**

```
Step 1: Add "Compare with..." button to AtlasViewerView context menu.
Step 2: On click, enable napari grid mode: viewer.grid.enabled = True.
Step 3: Add second atlas to the next grid slot.
Step 4: Synchronise camera between grid slots using
        viewer.camera.events.connect.
Step 5: Add "Exit comparison mode" button that disables grid.
Step 6: Write integration tests for grid state and layer counts.
```

---

## 6. Python & Qt Concepts Required

### 6.1 Python Language Concepts

| Concept | Usage in this project |
|---------|----------------------|
| **Dataclasses** (`@dataclass`) | `NapariAtlasRepresentation` uses `@dataclass` with `__post_init__` for setup after field initialisation |
| **Type hints** | All public methods use type hints; required for `mypy` checks |
| **`typing.Optional`** | Used for nullable attributes (e.g. cached layers) |
| **`typing.Dict`, `List`** | Data model storage |
| **`pathlib.Path`** | Used in `load_user_data.py` for filesystem paths (safer than `os.path`) |
| **`json`** | Reading `metadata.json` and `structures.json` files |
| **`assert`** → **`if/raise`** | Assertion-based vs explicit validation |
| **Lambda functions** | Used in signal-slot connections for inline logic |
| **List comprehensions** | Used in `refresh_data`, `build_structure_tree` |
| **`@classmethod`** | `get_tooltip_text` in view classes (no instance needed) |
| **`@staticmethod`** | Could replace `@classmethod` where `cls` is unused |
| **Context managers (`with`)** | File reading in `load_user_data.py` |
| **Exception handling** | `KeyError, IndexError` in `_on_mouse_move`; `ValueError` in dialogs |
| **f-strings** | Used throughout for string formatting |
| **`__post_init__`** | Dataclass hook for side-effects after `__init__` |
| **Generator expressions** | `np.repeat`, `float(c) / 255 for c in color` |

---

### 6.2 Qt / PyQt Concepts

| Concept | Usage |
|---------|-------|
| **Model/View Pattern** | `QAbstractTableModel`, `QAbstractItemModel` decoupled from `QTableView`, `QTreeView` |
| **`QModelIndex`** | Opaque index used to navigate models without direct data access |
| **`QSortFilterProxyModel`** | Wraps source models for filtering/sorting without modifying source |
| **Signals & Slots** | `Signal(str)`, `Signal(int, int, str, object)` for decoupled communication |
| **`@thread_worker`** (napari) | Runs blocking I/O (download/update) in a background thread |
| **`QStandardItem`** | Base class for tree items (though here it's used as base concept only — `StructureTreeItem` inherits directly) |
| **`Qt.DisplayRole`**, **`Qt.ToolTipRole`**, **`Qt.BackgroundRole`** | Three Qt data roles used in `AtlasTableModel.data()` |
| **`QBrush`, `QColor`** | Used for atlas status background colouring |
| **`QProgressBar`** | Extended for download progress display |
| **`QDialog`** (modal) | Confirmation dialogs block interaction until dismissed |
| **`QMenu`** | Context menu for additional references |
| **`QGroupBox`** | Used to visually group related widgets with optional title |
| **`QVBoxLayout`, `QHBoxLayout`** | Standard box layouts |
| **`QCheckBox`** | Toggle for showing structure names vs acronyms |
| **`QLabel`** | Floating tooltip widget (manually positioned with `QCursor.pos()`) |
| **`Qt.WindowFlags`** | `Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint` for floating tooltip |
| **`QLineEdit`** | Search input in filter widget |
| **`QComboBox`** | Column selector in filter widget |
| **`viewport()`** | Required for correct mouse event coordinates in table/tree views |
| **`createIndex()`** | Creates opaque `QModelIndex` instances in custom models |
| **`hasIndex()`** | Validates row/column bounds before `createIndex()` |
| **`Qt.CaseInsensitive`** | Case-insensitive filter matching |
| **`mapToGlobal()`** | Converts local widget coordinates to screen coordinates for context menus |

---

### 6.3 napari-Specific Concepts

| Concept | Usage |
|---------|-------|
| **`napari.Viewer`** | Central viewer object; holds `layers`, `camera`, `dims`, `cursor` |
| **`viewer.add_image()`** | Adds volumetric image (reference, additional reference) |
| **`viewer.add_labels()`** | Adds integer annotation volume with per-label colours |
| **`viewer.add_surface()`** | Adds mesh as `(points, cells)` tuple with optional `vertex_colors` |
| **`layer.mouse_move_callbacks`** | Per-layer callback list for mouse events |
| **`viewer.dims.ndisplay`** | 2 or 3; used to show mesh warning in 2D |
| **`viewer.cursor.position`** | Current cursor position in data (voxel) coordinates |
| **`get_settings()`** | Access napari appearance settings (theme, tooltip visibility) |
| **`show_info()`** | Non-blocking info notification |
| **`thread_worker`** | Decorator that moves function to worker thread with Qt-safe signal return |
| **`viewer.screenshot()`** | Captures current canvas as numpy array or saves to file |
| **`viewer.grid.enabled`** | Enables grid display for multi-atlas comparison |

---

### 6.4 BrainGlobe Atlas API Concepts

| Concept | Usage |
|---------|-------|
| **`BrainGlobeAtlas(name)`** | Load atlas; provides `.reference`, `.annotation`, `.structures`, `.resolution` |
| **`atlas.mesh_from_structure(acronym)`** | Returns `meshio.Mesh` for a brain region |
| **`atlas.structure_from_coords(pos, microns, as_acronym)`** | Region lookup at voxel position |
| **`atlas.hemisphere_from_coords(pos, as_string, microns)`** | Left/right hemisphere at position |
| **`get_downloaded_atlases()`** | List of locally cached atlas names |
| **`get_all_atlases_lastversions()`** | Dict of all available atlases with latest version |
| **`get_atlases_lastversions()`** | Dict of downloaded atlases with version info |
| **`get_local_atlas_version(name)`** | Version string of locally installed atlas |
| **`install_atlas(name, fn_update)`** | Download atlas; `fn_update(completed, total)` callback |
| **`update_atlas(name, fn_update)`** | Update atlas; same callback signature |
| **`get_structures_tree(structures)`** | Returns `treelib.Tree` of brain region hierarchy |
| **`config.get_brainglobe_dir()`** | Returns `Path` to user's `.brainglobe/` directory |

---

## 7. Testing Strategy

### 7.1 Testing Stack

| Tool | Purpose |
|------|---------|
| `pytest` | Test runner and assertion framework |
| `pytest-qt` (`qtbot`) | Qt widget instantiation and interaction in tests |
| `pytest-mock` (`mocker`) | Mock external functions/APIs without network calls |
| `pytest-cov` | Code coverage measurement |
| `conftest.py` fixtures | Shared setup: mock user folders, pre-downloaded atlases |

### 7.2 Test Principles

1. **One test per behaviour, not per function** — test what the function does,
   not how it's implemented.
2. **Mock all external I/O** — use `mocker.patch` for
   `get_all_atlases_lastversions`, `install_atlas`, `get_downloaded_atlases`
   to keep tests fast and hermetic.
3. **Use conftest fixtures** — always run through `mock_brainglobe_user_folders`
   and `setup_preexisting_local_atlases`.
4. **Parametrize for variants** — use `@pytest.mark.parametrize` for
   multiple atlas names, edge cases (empty list, single item).
5. **Integration tests test signal chains** — verify that double-clicking a
   row in the view results in the correct layer being added to the viewer.

### 7.3 Test Structure for New Features

```
tests/
├── test_unit/
│   ├── test_formatting.py              # existing
│   ├── test_metadata_reading.py        # existing
│   ├── test_napari_atlas_representation.py  # existing (extend for F6)
│   ├── test_atlas_table_model.py       # existing (extend for Bug 3 fix)
│   ├── test_structure_tree_model.py    # existing
│   ├── test_atlas_viewer_view.py       # existing (extend for Bug 7 fix)
│   ├── test_atlas_manager_view.py      # existing (extend for Bug 9 fix)
│   ├── test_atlas_progress_bar.py      # existing
│   ├── test_atlas_manager_filter.py    # existing
│   ├── test_structure_view.py          # existing (extend for F1, F2)
│   ├── test_download_update_dialog.py  # existing (extend for Bug 10 fix)
│   ├── test_layer_controls_widget.py   # new (for F3)
│   ├── test_atlas_metadata_panel.py    # new (for F5)
│   └── test_atlas_version_history.py  # new (for F7)
└── test_integration/
    ├── test_brainrender_viewer_widget.py   # existing (extend for F1, F2, F4)
    └── test_brainrender_manager_widget.py  # existing (extend for F7)
```

### 7.4 Test Templates

#### Unit test template for a new widget method

```python
# tests/test_unit/test_new_widget.py
import pytest
from pytestqt.qtbot import QtBot
from unittest.mock import patch

from brainrender_napari.widgets.new_widget import NewWidget


@pytest.fixture
def new_widget(qtbot: QtBot) -> NewWidget:
    widget = NewWidget()
    qtbot.addWidget(widget)
    return widget


def test_initial_state(new_widget: NewWidget) -> None:
    """NewWidget should start in <expected initial state>."""
    assert new_widget.some_attribute == expected_value


def test_method_with_valid_input(new_widget: NewWidget) -> None:
    """<method> should <expected behaviour> given valid input."""
    with patch("module.external_function") as mock_fn:
        mock_fn.return_value = "expected"
        result = new_widget.method("valid_input")
    assert result == "expected"
    mock_fn.assert_called_once_with("valid_input")


def test_method_with_invalid_input_raises(new_widget: NewWidget) -> None:
    """<method> should raise ValueError for invalid input."""
    with pytest.raises(ValueError, match="expected error message"):
        new_widget.method("invalid_input")


@pytest.mark.parametrize("input,expected", [
    ("case_1", "result_1"),
    ("case_2", "result_2"),
])
def test_method_parametrized(
    new_widget: NewWidget, input: str, expected: str
) -> None:
    assert new_widget.method(input) == expected
```

#### Integration test template for signal-slot chains

```python
# tests/test_integration/test_brainrender_viewer_widget.py (extension)
def test_structure_search_filters_tree(
    qtbot: QtBot,
    make_napari_viewer,
) -> None:
    """Entering a search query should filter the structure tree."""
    viewer = make_napari_viewer()
    widget = BrainrenderViewerWidget(napari_viewer=viewer)
    qtbot.addWidget(widget)

    # Select a downloaded atlas
    atlas_index = widget.atlas_viewer_view.model().index(0, 0)
    widget.atlas_viewer_view.setCurrentIndex(atlas_index)

    # Type in the search box
    qtbot.keyClicks(widget.structure_search_box, "cortex")

    # Verify the tree is filtered
    visible_rows = sum(
        1 for row in range(widget.structure_view.model().rowCount(QModelIndex()))
        if not widget.structure_view.isRowHidden(row, QModelIndex())
    )
    assert visible_rows < widget.structure_view.model().rowCount(QModelIndex())
```

### 7.5 Test Coverage Requirements

| Feature / Fix | Minimum coverage target |
|---------------|------------------------|
| Bug fixes (Phase 0) | 100% of changed lines |
| New widgets (Phase 1–3) | ≥ 90% line coverage |
| Integration paths | All happy paths + at least one error path |
| Signal-slot connections | All signals must be tested via `qtbot.waitSignal` |

### 7.6 Testing Qt Signals

```python
# Preferred pattern for signal testing
def test_add_structure_signal_emitted(qtbot, structure_view):
    with qtbot.waitSignal(
        structure_view.add_structure_requested,
        timeout=1000
    ) as blocker:
        # trigger the action that should emit the signal
        structure_view._on_row_double_clicked()

    assert blocker.args == ["expected_acronym"]
```

### 7.7 Mocking BrainGlobe API Calls

```python
# Pattern for mocking atlas API to avoid network/disk access in unit tests
@pytest.fixture
def mock_atlas_api(mocker):
    mocker.patch(
        "brainglobe_atlasapi.list_atlases.get_all_atlases_lastversions",
        return_value={"example_mouse_100um": "1.2", "allen_mouse_10um": "3.0"},
    )
    mocker.patch(
        "brainglobe_atlasapi.list_atlases.get_downloaded_atlases",
        return_value=["example_mouse_100um"],
    )
    mocker.patch(
        "brainglobe_atlasapi.list_atlases.get_atlases_lastversions",
        return_value={
            "example_mouse_100um": {"latest_version": "1.2", "updated": True}
        },
    )
```

---

## 8. Documentation Requirements

### 8.1 Docstring Standard

All public functions and classes **must** have docstrings following the
NumPy/Google style already used in the project. Minimum requirements:

```python
def example_function(param1: str, param2: int = 0) -> bool:
    """One-line summary of what the function does.

    Longer description if the behaviour is non-obvious. Explain
    any side effects, state mutations, or signal emissions.

    Parameters
    ----------
    param1 : str
        Description of param1 and any constraints.
    param2 : int, optional
        Description of param2. Default is 0.

    Returns
    -------
    bool
        What the return value represents.

    Raises
    ------
    ValueError
        When and why this is raised.

    Notes
    -----
    Any implementation notes, performance considerations, or
    known limitations.
    """
```

### 8.2 Module-Level Docstrings

Every new `.py` file must begin with a module-level docstring explaining:
1. What the module contains
2. Its role in the widget hierarchy
3. Key design decisions

Example pattern (matches existing codebase style):
```python
"""The purpose of this file is to provide <widget description>.

Users interacting with it can:
* <user action 1>
* <user action 2>

It is designed to be agnostic from the viewer framework by emitting
signals that interested observers can connect to.
"""
```

### 8.3 Tutorial Documentation

For each major new feature, a tutorial page should be added to the BrainGlobe
documentation site (`brainglobe.github.io`):

| Feature | Tutorial Title | Format |
|---------|---------------|--------|
| Structure Search (F1) | Update "Visualising an atlas in napari" | Add section |
| Batch Structure Addition (F2) | Update existing tutorial | Add section |
| Export Screenshot (F4) | "Exporting your atlas visualisation" | New short page |
| Atlas Metadata Panel (F5) | Update existing tutorial | Add section |
| Atlas Comparison (F8) | "Comparing atlases in napari" | New page |

### 8.4 Changelog Entry Format

Each change must be documented in `CHANGELOG.md` (to be created) following
[Keep a Changelog](https://keepachangelog.com/) format:

```markdown
## [Unreleased]

### Added
- Structure search/filter box in structure tree view (#<issue>)
- Batch structure addition via multi-select (#<issue>)

### Fixed
- `columnCount` crash when atlas list is empty (#<issue>)
- Context menu crash when no row is selected (#<issue>)
- `format_atlas_name` for non-standard atlas name formats (#<issue>)
```

### 8.5 Inline Comment Standards

- Use comments **only** to explain non-obvious decisions, not to describe
  what code does (the code does that).
- Mark known limitations with `# TODO(author): description` or
  `# FIXME(author): description`.
- Mark performance-critical sections with `# PERF:`.

Example from existing code (good pattern to follow):
```python
for n_id in tree.expand_tree():  # sorts nodes by default,
    # so parents will always be already in the QAbstractItemModel
    # before their children
```

---

## 9. Dependency Impact

### 9.1 No New Dependencies Required

All proposed features can be implemented using the **existing dependency set**:

| Feature | Required existing dependencies |
|---------|-------------------------------|
| Structure search (F1) | `qtpy` (QSortFilterProxyModel already imported) |
| Batch structure addition (F2) | `qtpy` only |
| Export screenshot (F4) | `napari` (viewer.screenshot) + `qtpy` (QFileDialog) |
| Metadata panel (F5) | `qtpy` only |
| Structure highlight (F6) | `napari` (viewer.add_shapes) + `numpy` |
| Mesh opacity control (F3) | `qtpy` only |
| Atlas version history (F7) | `urllib.request` (stdlib — no new dep needed) |
| Atlas comparison (F8) | `napari` only |

### 9.2 Optional Future Dependencies

If advanced features are pursued beyond Phase 4:

| Potential dependency | Use case | Risk |
|---------------------|----------|------|
| `requests` (if not already transitive) | More robust HTTP for atlas changelog | Low — very common |
| `matplotlib` | Static plot of structure volumes | Medium — heavy |
| `vedo` | More advanced 3D mesh manipulation | High — large dep |

> **Policy:** Do not add new top-level dependencies without reviewing the
> full dependency tree. Use `pip show <package>` to check if a dep is
> already transitively available before adding it.

---

## Appendix A — File-by-File Change Impact Matrix

| File | Phase 0 (bugs) | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|------|---------------|---------|---------|---------|---------|
| `napari_atlas_representation.py` | Bug 1, 4, 5 | — | F6 | F6 | F8 |
| `brainrender_viewer_widget.py` | Bug 1 | F1, F4 | F2, F3 | F5 | F8 |
| `brainrender_manager_widget.py` | — | — | — | — | F7 |
| `atlas_table_model.py` | Bug 3 | — | — | — | — |
| `atlas_manager_view.py` | Bug 9 | — | — | — | — |
| `atlas_viewer_view.py` | Bug 7 | — | — | — | — |
| `structure_view.py` | Bug 2 | F1, F2 | — | — | — |
| `atlas_manager_filter.py` | Bug 6 | — | — | — | — |
| `atlas_manager_dialog.py` | Bug 10 | — | — | — | — |
| `formatting.py` | Bug 8 | — | — | — | — |
| `load_user_data.py` | — | — | — | F5 | — |
| *(new)* `layer_controls_widget.py` | — | — | F3 | — | — |
| *(new)* `atlas_metadata_panel.py` | — | — | — | F5 | — |
| *(new)* `atlas_version_history.py` | — | — | — | — | F7 |
| *(new)* `utils/export.py` | — | F4 | — | — | — |

---

## Appendix B — Estimated Effort Summary

| Phase | Duration | Risk | Value |
|-------|----------|------|-------|
| 0 — Bug Fixes | 3 days | Low | High (stability) |
| 1 — Quick Wins | 3 days | Low | High (UX) |
| 2 — Core Enhancements | 5 days | Medium | High (UX) |
| 3 — Extended Features | 7 days | Medium | Medium |
| 4 — Advanced Features | 10 days | High | Medium |
| **Total** | **~28 days** | | |

---

*This document was generated from a full analysis of the
`brainrender-napari` v0.0.1 codebase (940 lines of production code,
14 source files, 13 test files). All function signatures, bugs, and plans
have been derived from reading the actual source code rather than
assumptions.*
