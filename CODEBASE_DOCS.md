# brainrender-napari — Comprehensive Codebase Documentation

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Directory Structure](#2-directory-structure)
3. [How the Plugin Works — High-Level Architecture](#3-how-the-plugin-works--high-level-architecture)
4. [Entry Points and Plugin Registration](#4-entry-points-and-plugin-registration)
5. [Main Widgets (Top-Level Components)](#5-main-widgets-top-level-components)
   - [BrainrenderViewerWidget](#51-brainrenderviewerwidget)
   - [BrainrenderManagerWidget](#52-brainrendermanagerwidget)
6. [Core Engine — NapariAtlasRepresentation](#6-core-engine--napariatlasrepresentation)
7. [Data Models (Qt Model/View Framework)](#7-data-models-qt-modelview-framework)
   - [AtlasTableModel](#71-atlastablemodel)
   - [StructureTreeModel and StructureTreeItem](#72-structuretreemodel-and-structuretreeitem)
8. [Widgets (UI Components)](#8-widgets-ui-components)
   - [AtlasViewerView](#81-atlasviewerview)
   - [AtlasManagerView](#82-atlasmanagerview)
   - [AtlasManagerFilter](#83-atlasmanagerfilter)
   - [AtlasProgressBar](#84-atlasprogressbar)
   - [AtlasManagerDialog](#85-atlasmanagerdialog)
   - [StructureView](#86-structureview)
9. [Utility Functions](#9-utility-functions)
   - [formatting.py](#91-formattingpy)
   - [load_user_data.py](#92-load_user_datapy)
10. [Signal-Slot Connection Map](#10-signal-slot-connection-map)
11. [End-to-End Workflow Walkthroughs](#11-end-to-end-workflow-walkthroughs)
    - [Downloading an Atlas](#111-downloading-an-atlas)
    - [Visualising an Atlas](#112-visualising-an-atlas)
    - [Adding a 3D Brain Structure Mesh](#113-adding-a-3d-brain-structure-mesh)
    - [Searching and Filtering Atlases](#114-searching-and-filtering-atlases)
12. [Design Patterns](#12-design-patterns)
13. [Configuration and Project Setup](#13-configuration-and-project-setup)
14. [Testing Infrastructure](#14-testing-infrastructure)

---

## 1. Project Overview

**brainrender-napari** is a [napari](https://napari.org/) plugin that brings brain-atlas visualisation and management directly into the napari viewer. It ports the key functionality of [brainrender](https://github.com/brainglobe/brainrender) — a Python library for rendering 3D brain atlases — into napari's layer-based, Qt-powered interface.

### What the repository does

| Capability | Description |
|---|---|
| **Atlas visualisation** | Loads a BrainGlobe atlas and adds its *reference* (grayscale anatomical image) and *annotation* (integer-labelled regions) as napari layers. |
| **Interactive tooltips** | As the user moves the cursor over the annotation layer in 2-D mode, a floating label shows the region name and hemisphere. |
| **3D brain-region meshes** | Selected brain regions are rendered as 3-D surface meshes with atlas-defined colours. |
| **Atlas management** | Allows users to browse all atlases available through the BrainGlobe API, download them locally, and update outdated versions — all from within napari. |
| **Real-time search** | A live search box filters the atlas list by any column. |
| **Additional references** | Some atlases ship with extra reference images (e.g. CCF); these can be added via a right-click context menu. |

### Key dependencies

| Package | Role |
|---|---|
| `napari` | Host viewer; supplies `Viewer`, layers, settings, and threading utilities. |
| `brainglobe-atlasapi` | Atlas data API: download, update, list, and query brain atlases. |
| `brainglobe-utils` | BrainGlobe-wide Qt utilities (e.g. `header_widget`). |
| `qtpy` | Qt abstraction layer (works with PyQt5, PyQt6, PySide2, PySide6). |
| `meshio` | Reads mesh files; `Mesh` objects carry points and cells for 3-D surfaces. |
| `numpy` | Array operations for mesh vertex colouring and cursor-position checks. |
| `treelib` | Used internally by `brainglobe-atlasapi` to represent the structure hierarchy. |

---

## 2. Directory Structure

```
brainrender-napari/
│
├── brainrender_napari/            # Main Python package
│   ├── __init__.py                # Package version and public exports
│   ├── napari.yaml                # napari plugin manifest (entry point declarations)
│   │
│   ├── brainrender_manager_widget.py   # "Manage atlas versions" top-level widget
│   ├── brainrender_viewer_widget.py    # "Brainrender" (viewer) top-level widget
│   ├── napari_atlas_representation.py  # Atlas → napari-layer conversion engine
│   │
│   ├── data_models/               # Qt Model/View data models
│   │   ├── __init__.py
│   │   ├── atlas_table_model.py   # Flat table model for atlas listings
│   │   └── structure_tree_model.py# Hierarchical tree model for brain regions
│   │
│   ├── utils/                     # Pure helper functions (no Qt)
│   │   ├── __init__.py
│   │   ├── formatting.py          # Atlas name and byte-count formatting
│   │   └── load_user_data.py      # Read local atlas JSON files
│   │
│   └── widgets/                   # Individual Qt widget classes
│       ├── __init__.py
│       ├── atlas_manager_dialog.py # Download/update confirmation dialog
│       ├── atlas_manager_filter.py # Search-bar + column-selector widget
│       ├── atlas_manager_view.py   # Table view: download / update atlases
│       ├── atlas_progress_bar.py   # Progress bar for long-running operations
│       ├── atlas_viewer_view.py    # Table view: add atlas layers to napari
│       └── structure_view.py      # Tree view: add 3-D region meshes to napari
│
├── tests/
│   ├── conftest.py                # Shared pytest fixtures
│   ├── test_integration/          # Integration tests (full widget + viewer)
│   │   ├── test_brainrender_manager_widget.py
│   │   └── test_brainrender_viewer_widget.py
│   └── test_unit/                 # Unit tests for every component
│       ├── test_atlas_manager_filter.py
│       ├── test_atlas_manager_view.py
│       ├── test_atlas_progress_bar.py
│       ├── test_atlas_table_model.py
│       ├── test_atlas_viewer_view.py
│       ├── test_download_update_dialog.py
│       ├── test_formatting.py
│       ├── test_metadata_reading.py
│       ├── test_napari_atlas_representation.py
│       ├── test_structure_tree_model.py
│       └── test_structure_view.py
│
├── pyproject.toml                 # Build config, dependencies, tool settings
├── README.md                      # Project overview and installation guide
├── CITATION.cff                   # Citation metadata
├── LICENSE                        # BSD-3-Clause licence
└── MANIFEST.in                    # Files to include in source distribution
```

---

## 3. How the Plugin Works — High-Level Architecture

```
napari application
│
├── Plugin discovery via pyproject.toml entry point
│     brainrender-napari = "brainrender_napari:napari.yaml"
│
├── napari.yaml registers two napari widgets:
│     ┌──────────────────────────────────┐
│     │  BrainrenderViewerWidget         │  ← "Brainrender" panel
│     │  (visualise a local atlas)       │
│     └──────────────────────────────────┘
│     ┌──────────────────────────────────┐
│     │  BrainrenderManagerWidget        │  ← "Manage atlas versions" panel
│     │  (download / update atlases)     │
│     └──────────────────────────────────┘
│
├── Both widgets use:
│     AtlasTableModel ──► QSortFilterProxyModel ──► QTableView subclass
│     StructureTreeModel ──────────────────────────► QTreeView subclass
│
└── Rendering performed by:
      NapariAtlasRepresentation (dataclass)
        ├── viewer.add_image()   → reference layer
        ├── viewer.add_labels()  → annotation layer
        └── viewer.add_surface() → 3-D mesh layer
```

### Component responsibility summary

| Component | Responsibility |
|---|---|
| `napari.yaml` | Declares commands and widgets; napari reads this on startup. |
| `BrainrenderViewerWidget` | Orchestrates atlas selection and layer creation in the viewer. |
| `BrainrenderManagerWidget` | Orchestrates atlas download, update, and progress reporting. |
| `NapariAtlasRepresentation` | Knows how to turn `BrainGlobeAtlas` data into napari layers. |
| `AtlasTableModel` | Provides atlas data rows to any `QTableView` (used by both manager and viewer). |
| `StructureTreeModel` | Provides the hierarchical region tree to `StructureView`. |
| `AtlasViewerView` | Table of *local* atlases; emits signals on user interaction. |
| `AtlasManagerView` | Table of *all* atlases; starts downloads/updates in a worker thread. |
| `AtlasManagerFilter` | Search box that filters `AtlasManagerView` via a proxy model. |
| `AtlasProgressBar` | Displays and resets a `QProgressBar` during long operations. |
| `AtlasManagerDialog` | Confirmation dialog before a download or update starts. |
| `StructureView` | Tree of regions; emits a signal when user double-clicks a region. |
| `format_atlas_name()` | Converts `allen_mouse_100um` → `Allen Mouse (100 μm)`. |
| `format_bytes()` | Converts raw bytes → human-readable string (`1.43 MB`). |
| `read_atlas_metadata_from_file()` | Reads `metadata.json` from the local atlas directory. |
| `read_atlas_structures_from_file()` | Reads `structures.json` from the local atlas directory. |

---

## 4. Entry Points and Plugin Registration

### `brainrender_napari/__init__.py`

```python
__version__ = "0.0.1"
__all__ = "BrainrenderViewerWidget, BrainrenderManagerWidget"
```

Declares the package version. `__all__` is currently assigned a plain string rather than a tuple or list — this means Python interprets it as a sequence of individual characters rather than a sequence of module names. In practice this is harmless because the two classes are exported via the napari plugin manifest rather than `from brainrender_napari import *`, but it is worth noting as a latent bug.

### `brainrender_napari/napari.yaml`

This YAML file is the napari plugin manifest. It is referenced from `pyproject.toml`:

```toml
[project.entry-points."napari.manifest"]
brainrender-napari = "brainrender_napari:napari.yaml"
```

The manifest registers two *commands* and two *widgets* with napari:

| Widget | Command | Class |
|---|---|---|
| `brainrender` | `make_brainrender_viewer_widget` | `BrainrenderViewerWidget` |
| `brainrender manager` | `make_brainrender_manager_widget` | `BrainrenderManagerWidget` |

When a user opens one of these widgets from the napari *Plugins* menu, napari calls the corresponding command, which constructs the widget and injects the live `Viewer` object.

---

## 5. Main Widgets (Top-Level Components)

### 5.1 `BrainrenderViewerWidget`

**File:** `brainrender_napari/brainrender_viewer_widget.py`

**Purpose:** The "Brainrender" panel — lets users pick a locally downloaded atlas, add its images to the viewer, and browse/add 3-D region meshes.

```
BrainrenderViewerWidget (QWidget)
│
├── header_widget            — logo + tutorial / citation links
│
├── QGroupBox "Atlas Viewer"
│   └── AtlasViewerView      — table of downloaded atlases
│
└── QGroupBox "3D Atlas region meshes" (hidden until atlas selected)
    ├── QCheckBox "Show region names"
    └── StructureView        — tree of brain regions
```

#### `__init__(self, napari_viewer: Viewer) -> None`

Builds the layout, creates all child widgets, and connects signals to slots:

```
AtlasViewerView.add_atlas_requested        → _on_add_atlas_requested
AtlasViewerView.additional_reference_requested → _on_additional_reference_requested
AtlasViewerView.selected_atlas_changed     → _on_atlas_selection_changed
show_structure_names.clicked               → _on_show_structure_names_clicked
StructureView.add_structure_requested      → _on_add_structure_requested
```

#### `_on_add_atlas_requested(atlas_name: str) -> None`

Called when the user double-clicks an atlas row.

1. Creates `BrainGlobeAtlas(atlas_name)` — loads atlas from disk.
2. Creates `NapariAtlasRepresentation(bg_atlas, viewer)`.
3. Calls `add_to_viewer()` which adds reference + annotation layers.

#### `_on_additional_reference_requested(additional_reference_name: str) -> None`

Called from the right-click context menu on the atlas table.

1. Loads the selected atlas.
2. Creates `NapariAtlasRepresentation`.
3. Calls `add_additional_reference(additional_reference_name)`.

#### `_on_atlas_selection_changed(atlas_name: str) -> None`

Called whenever the selected row in the atlas table changes.

1. Calls `structure_view.refresh(atlas_name, show_structure_names)` to reload the region tree.
2. Shows or hides the "3D Atlas region meshes" group box depending on whether the atlas is downloaded.
3. Shows or hides the "Show region names" checkbox.

#### `_on_show_structure_names_clicked(self) -> None`

Re-calls `structure_view.refresh()` with the updated checkbox state so the tree switches between showing acronyms and full region names.

#### `_on_add_structure_requested(structure_name: str) -> None`

Called when the user double-clicks a region in the structure tree.

1. Loads the currently selected atlas.
2. Creates `NapariAtlasRepresentation`.
3. Calls `add_structure_to_viewer(structure_name)` to add the 3-D mesh.

---

### 5.2 `BrainrenderManagerWidget`

**File:** `brainrender_napari/brainrender_manager_widget.py`

**Purpose:** The "Manage atlas versions" panel — shows all BrainGlobe atlases (not just local ones), and lets users download or update them.

```
BrainrenderManagerWidget (QWidget)
│
├── header_widget               — logo + tutorial / citation links
│
└── QGroupBox "Atlas Manager"
    ├── AtlasManagerView        — table of all atlases (colour-coded)
    ├── AtlasManagerFilter      — search bar + column selector
    └── AtlasProgressBar        — progress bar (hidden unless active)
```

#### `__init__(self, napari_viewer: Viewer) -> None`

Builds the layout and wires progress tracking:

```
AtlasManagerView.progress_updated          → AtlasProgressBar.update_progress
AtlasManagerView.download_atlas_confirmed  → AtlasProgressBar.operation_completed
AtlasManagerView.update_atlas_confirmed    → AtlasProgressBar.operation_completed
```

The `napari_viewer` argument is accepted (required by the napari plugin API) but not used directly by this widget — it is stored as `self._viewer` for potential future use.

---

## 6. Core Engine — `NapariAtlasRepresentation`

**File:** `brainrender_napari/napari_atlas_representation.py`

**Purpose:** The heart of the rendering logic. Converts a `BrainGlobeAtlas` object into napari layers, handling scaling, colouring, and interactive tooltips.

```python
@dataclass
class NapariAtlasRepresentation:
    bg_atlas: BrainGlobeAtlas
    viewer: Viewer
    mesh_opacity: float = 0.4
    mesh_blending: str = "translucent_no_depth"
```

Being a Python `dataclass`, it has an auto-generated `__init__` for its fields, plus a custom `__post_init__` for setup that requires the fields to already be set.

### `__post_init__(self) -> None`

Runs immediately after the dataclass `__init__`.

- Creates a `QLabel` (`self._tooltip`) parented to the napari viewer window. This label is used as a custom floating tooltip — it is frameless, always-on-top, and transparent to input.
- Enables napari's built-in layer tooltip setting (`napari_settings.appearance.layer_tooltip_visibility = True`) so that the tooltip system is globally active.

```python
self._tooltip = QLabel(self.viewer.window.qt_viewer.parent())
self._tooltip.setWindowFlags(
    Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
)
```

### `add_to_viewer(self) -> None`

Adds the atlas to napari as two layers:

| Layer type | napari call | Visibility | Name |
|---|---|---|---|
| Image (reference) | `viewer.add_image()` | **hidden** | `{atlas_name}_reference` |
| Labels (annotation) | `viewer.add_labels()` | **visible** | `{atlas_name}_annotation` |

Both layers get `_on_mouse_move` registered as a `mouse_move_callbacks` handler so the tooltip follows the cursor.

> **Why is the reference hidden by default?**  
> The annotation layer (integer region IDs) is the primary way to interact with the atlas. The reference (grayscale anatomy) is available but starts hidden to keep the view uncluttered. Users can toggle visibility manually in napari.

### `add_structure_to_viewer(self, structure_name: str) -> None`

Adds a single brain region as a 3-D mesh layer.

1. Warns the user (via `show_info`) if the viewer is in 2-D mode — meshes are only visible in 3-D.
2. Calls `bg_atlas.mesh_from_structure(structure_name)` to get a `meshio.Mesh` object.
3. Computes `scale = [1.0 / resolution for resolution in self.bg_atlas.resolution]` to convert the mesh from micron-space to pixel-space (napari works in pixel-space).
4. Retrieves the RGB colour tuple from `bg_atlas.structures[structure_name]["rgb_triplet"]`.
5. Delegates to `_add_mesh()`.

### `_add_mesh(self, mesh: Mesh, scale: list, name: str, color=None) -> None`

Helper that calls `viewer.add_surface()`.

- Extracts `points` (vertex coordinates) and `cells` (triangle index arrays) from the `meshio.Mesh`.
- If a colour is provided, converts it from integer RGB (0–255) to normalised floats (0.0–1.0) and broadcasts it to every vertex via `np.repeat`.
- Applies `mesh_opacity` and `mesh_blending` from the dataclass fields.

```python
viewer_kwargs["vertex_colors"] = np.repeat(
    [[float(c) / 255 for c in color]], len(points), axis=0
)
self.viewer.add_surface((points, cells), scale=scale, **viewer_kwargs)
```

### `add_additional_reference(self, additional_reference_key: str) -> None`

Adds an optional secondary reference image (e.g. the CCF template for the Allen Mouse atlas).

- Calls `viewer.add_image()` using `bg_atlas.additional_references[additional_reference_key]`.
- Registers the mouse-move callback on the new layer.

### `_on_mouse_move(self, layer, event) -> None`

**This is the interactive tooltip callback** registered on every layer added by this class.

Conditions for showing the tooltip (all must be true):

1. `napari_settings.appearance.layer_tooltip_visibility` is `True` (user has not disabled tooltips).
2. `np.all(np.array(cursor_position) > 0)` — cursor is inside the image, not at origin.
3. `self.viewer.dims.ndisplay == 2` — viewer is in 2-D mode (tooltips do not make sense in 3-D perspective).

When all conditions are met:

1. Moves `self._tooltip` to 20 pixels right and 20 pixels below the OS-level cursor.
2. Calls `bg_atlas.structure_from_coords(cursor_position, microns=False, as_acronym=True)` to get the region acronym at the cursor.
3. Looks up the full region name and hemisphere.
4. Sets the tooltip text to `"{region name} | {Hemisphere}"` and shows the label.

Any `KeyError` (cursor in background region) or `IndexError` (cursor outside image bounds) is silently caught and the tooltip is hidden.

---

## 7. Data Models (Qt Model/View Framework)

Both models follow the [Qt Model/View architecture](https://doc.qt.io/qt-6/model-view-programming.html), which decouples data storage from visual presentation.

### 7.1 `AtlasTableModel`

**File:** `brainrender_napari/data_models/atlas_table_model.py`

**Inherits from:** `QAbstractTableModel`

**Purpose:** Provides all atlas data to any `QTableView`. It is shared between `AtlasViewerView` and `AtlasManagerView` by passing the *view class* (not an instance) as a constructor argument so that the model can call the correct static tooltip method.

#### `__init__(self, view_type: QTableView)`

- Validates that `view_type` has a `get_tooltip_text` classmethod (design contract).
- Stores the view type reference for tooltip delegation.
- Calls `refresh_data()` to populate the internal `_data` list.

#### `refresh_data(self)`

Builds `self._data` as a list of lists, one row per atlas:

```python
[raw_name, formatted_name, local_version_or_"n/a", latest_version]
```

Data sources:
- `get_all_atlases_lastversions()` — all atlases known to BrainGlobe API.
- `get_atlases_lastversions()` — locally available atlases with version info.
- `get_local_atlas_version(name)` — exact local version string.

#### `data(self, index, role=Qt.DisplayRole)`

Returns different values depending on the Qt *role*:

| Role | Return value |
|---|---|
| `DisplayRole` | Raw cell value from `self._data[row][column]` |
| `ToolTipRole` | Calls `view_type.get_tooltip_text(atlas_name)` |
| `BackgroundRole` | `QBrush` with a colour indicating download status (see below) |

**Colour-coding logic (BackgroundRole):**

```
local_version == "n/a"  →  grey   (atlas not downloaded)
local_version != latest_version  →  amber  (atlas outdated)
local_version == latest_version  →  None   (up-to-date; default background)
```

Both grey and amber have dark-theme and light-theme variants, detected via `get_settings().appearance.theme`.

#### `headerData(self, section, orientation, role)`

Returns column header strings for the horizontal header. Raises `ValueError` for unexpected section indices to catch programmer errors early.

---

### 7.2 `StructureTreeModel` and `StructureTreeItem`

**Files:**
- `brainrender_napari/data_models/structure_tree_model.py` (used by `StructureView`)
- `brainrender_napari/widgets/structure_view.py` (contains a parallel definition used locally)

> **Note:** `StructureTreeItem` and `StructureTreeModel` are defined in **both** `data_models/structure_tree_model.py` and `widgets/structure_view.py`. The `StructureView` widget imports from its own file. The versions are functionally identical.

#### `StructureTreeItem`

A node in the tree. Stores a 3-tuple `(acronym, name, id)` as `item_data`.

| Method | Description |
|---|---|
| `appendChild(item)` | Adds a child node. |
| `child(row)` | Returns the child at the given row index. |
| `childCount()` | Number of direct children. |
| `columnCount()` | Always 3 (acronym, name, id). |
| `data(column)` | Returns `item_data[column]`; returns `None` on `IndexError`. |
| `parent()` | Returns the parent `StructureTreeItem`. |
| `row()` | Returns this item's position in its parent's `child_items` list. |

#### `StructureTreeModel`

**Inherits from:** `QAbstractItemModel`

Builds a tree from a flat list of structure dicts (each dict has `id`, `acronym`, `name`, `structure_id_path`, `parent_structure_id`).

#### `__init__(self, data: List, parent=None)`

Creates a root `StructureTreeItem` with header columns `("acronym", "name", "id")`, then calls `build_structure_tree(data, root_item)`.

#### `build_structure_tree(self, structures: List, root: StructureTreeItem)`

**Algorithm:**

1. Calls `get_structures_tree(structures)` from `brainglobe-atlasapi` to get a `treelib.Tree` ordered by ID.
2. Builds a `structure_id_dict` mapping integer IDs to structure dicts.
3. Iterates through the tree using `tree.expand_tree()` (which yields nodes in depth-first order, guaranteeing parents before children).
4. For each node:
   - If `structure_id_path` length is 1 → top-level region → parent is root.
   - Otherwise → looks up the treelib parent and finds its already-inserted `StructureTreeItem`.
5. Creates the item, appends it to the parent, and records it in `inserted_items` for future children.

#### Required Qt interface methods

| Method | What it returns |
|---|---|
| `data(index, role)` | Cell text for `DisplayRole`; `None` otherwise. |
| `rowCount(parent)` | Number of children of the item at `parent`. |
| `columnCount(parent)` | Always 3. |
| `parent(index)` | `QModelIndex` pointing to the first column of the parent. |
| `index(row, column, parent)` | `QModelIndex` for the item at `(row, column)` under `parent`. |

---

## 8. Widgets (UI Components)

### 8.1 `AtlasViewerView`

**File:** `brainrender_napari/widgets/atlas_viewer_view.py`

**Inherits from:** `QTableView`

**Purpose:** Shows only *locally downloaded* atlases. Users double-click to add an atlas to the viewer, or right-click to add an additional reference image.

#### Signals

| Signal | Payload | Emitted when |
|---|---|---|
| `add_atlas_requested` | `str` (atlas name) | User double-clicks an atlas row |
| `no_atlas_available` | — | No local atlases exist at startup |
| `additional_reference_requested` | `str` (reference key) | User picks a reference from right-click menu |
| `selected_atlas_changed` | `str` (atlas name) | Selection changes in the table |

#### Initialisation behaviour

- Creates an `AtlasTableModel(AtlasViewerView)` — passes itself as the view type so the model delegates tooltips correctly.
- **Hides rows** for atlases that are not locally downloaded (iterates all rows on construction).
- Hides columns: `Raw name`, `Local version`, `Latest version` — only the friendly `Atlas` name is shown.
- Connects `selectionModel().currentChanged` → `_on_current_changed`.

#### `selected_atlas_name(self) -> str`

Returns the atlas name from column 0 of the current row. Asserts the result is in `get_downloaded_atlases()` — a contract check that prevents stale selections.

#### `_on_context_menu_requested(self, position) -> None`

1. Reads `metadata.json` for the selected atlas.
2. If `additional_references` key exists and is non-empty, builds a `QMenu` with one action per reference.
3. If the user selects an action, emits `additional_reference_requested` with the reference key.

#### `get_tooltip_text(cls, atlas_name: str) -> str` (classmethod)

Returns a multi-line tooltip including:
- Friendly atlas name + `(double-click to add to viewer)`.
- All metadata key-value pairs from `metadata.json`, tab-separated.

---

### 8.2 `AtlasManagerView`

**File:** `brainrender_napari/widgets/atlas_manager_view.py`

**Inherits from:** `QTableView`

**Purpose:** Shows *all* atlases (downloaded or not) colour-coded by status. Double-clicking initiates a download or update.

#### Signals

| Signal | Payload | Description |
|---|---|---|
| `download_atlas_confirmed` | `str` | Atlas name after successful download |
| `update_atlas_confirmed` | `str` | Atlas name after successful update |
| `progress_updated` | `int, int, str, object` | `(completed, total, atlas_name, operation_type)` |

#### Initialisation

Uses a `QSortFilterProxyModel` layered on top of `AtlasTableModel` so that `AtlasManagerFilter` can filter rows without touching the underlying data. The proxy is configured for case-insensitive filtering.

#### `_on_row_double_clicked(self) -> None`

**Decision logic:**

```
atlas downloaded?
├── YES → is it up to date?
│          ├── YES  → do nothing (tooltip already says "up-to-date")
│          └── NO   → show AtlasManagerDialog("Update")
│                      └── user confirms → _on_update_atlas_confirmed()
└── NO  → show AtlasManagerDialog("Download")
            └── user confirms → _on_download_atlas_confirmed()
```

#### `_on_download_atlas_confirmed(self) -> None`

1. Gets the atlas name.
2. Calls `_apply_in_thread(install_atlas, atlas_name, fn_update=...)`.
3. `fn_update` lambda emits `progress_updated` with `(completed, total, atlas_name, "Downloading")`.
4. On thread return: emits `download_atlas_confirmed` and calls `source_model.refresh_data()`.

#### `_on_update_atlas_confirmed(self) -> None`

Same pattern as download but uses `update_atlas` and emits `update_atlas_confirmed`.

#### `_apply_in_thread(self, apply: Callable, *args, **kwargs)` *(decorated with `@thread_worker`)*

```python
@thread_worker
def _apply_in_thread(self, apply: Callable, *args, **kwargs):
    return apply(*args, **kwargs)
```

The `@thread_worker` decorator (from `napari.qt`) runs the function body in a separate `QThread`-based worker, avoiding UI freezes during network operations. The returned worker object exposes `.returned` signal and `.start()` method.

#### `get_tooltip_text(cls, atlas_name: str) -> str` (classmethod)

- **Up-to-date** → `"Allen Mouse (100 μm) is up-to-date"`
- **Needs update** → `"Allen Mouse (100 μm) (double-click to update)"`
- **Not downloaded** → `"Allen Mouse (100 μm) (double-click to download)"`

---

### 8.3 `AtlasManagerFilter`

**File:** `brainrender_napari/widgets/atlas_manager_filter.py`

**Purpose:** A search widget that filters the atlas manager table in real time.

```
AtlasManagerFilter (QWidget)
│
├── QLineEdit  — search query ("Search..." placeholder)
└── QComboBox  — column selector ("Any", "Atlas", "Local version", "Latest version")
```

#### `apply(self)`

Called on every keystroke or column-selector change:

1. Reads `query_text` from the line edit.
2. Reads the selected column name from the combo box.
3. If `"Any"`, sets the proxy model's filter column to `-1` (all columns).
4. Otherwise, maps the column name to its index and sets it on the proxy.
5. Calls `proxy_model.setFilterFixedString(query_text)` — the proxy immediately hides non-matching rows.

---

### 8.4 `AtlasProgressBar`

**File:** `brainrender_napari/widgets/atlas_progress_bar.py`

**Purpose:** Displays a `QProgressBar` during downloads/updates and hides itself when done.

#### `update_progress(self, completed: int, total: int, atlas_name: str, operation_type: object)`

Connected to `AtlasManagerView.progress_updated`. Sets the progress bar's range and value, and updates the label text to e.g. `"Downloading Allen Mouse (100 μm): 3/10 files"`.

#### `operation_completed(self, atlas_name: str)`

Connected to `AtlasManagerView.download_atlas_confirmed` and `update_atlas_confirmed`. Resets the progress bar and hides it.

---

### 8.5 `AtlasManagerDialog`

**File:** `brainrender_napari/widgets/atlas_manager_dialog.py`

**Purpose:** A `QDialog` modal that asks the user to confirm a download or update. Warns that the operation may take a while.

```
AtlasManagerDialog (QDialog)
│
├── QLabel — "Are you sure? (It may take a while)"
├── ok_button (QPushButton "Yes") → dialog.accept()
└── cancel_button (QPushButton "No") → dialog.reject()
```

The dialog title is formatted as `"{action} {formatted_atlas_name} Atlas"` (e.g. `"Download Allen Mouse (100 μm) Atlas"`).

Validation: asserts the `atlas_name` is a valid key in `get_all_atlases_lastversions()`.

---

### 8.6 `StructureView`

**File:** `brainrender_napari/widgets/structure_view.py`

**Inherits from:** `QTreeView`

**Purpose:** Hierarchical tree view of brain regions for the currently selected atlas. Double-clicking a region requests its 3-D mesh.

#### Signals

| Signal | Payload | Emitted when |
|---|---|---|
| `add_structure_requested` | `str` (structure acronym) | User double-clicks a region row |

#### `refresh(self, selected_atlas_name: str, show_structure_names: bool = False)`

Called every time the user changes atlas selection or toggles the name checkbox:

1. If the atlas is downloaded:
   - Reads structures from `structures.json` via `read_atlas_structures_from_file()`.
   - Creates a new `StructureTreeModel` and sets it on the view.
   - Shows column 1 (full name) or hides it based on `show_structure_names`.
   - Always hides column 2 (numeric ID — internal use only).
   - Configures appearance: no header, no word wrap, expand to depth 0 (top-level regions visible by default).
   - Shows the tree.
2. If the atlas is not downloaded: hides the tree.
3. Resets `currentIndex` to prevent stale selections.

#### `selected_structure_acronym(self) -> str`

Gets column 0 (acronym) of the currently selected row. Asserts the index is valid.

#### Behaviour note

`setExpandsOnDoubleClick(False)` is set explicitly because double-click is already bound to `_on_row_double_clicked` (to emit a signal). Without this, a double-click would both add the mesh *and* toggle the tree expansion, which would be confusing.

The `expanded` signal is connected to `resizeColumnToContents(0)` so the acronym column widens automatically when subtrees are opened.

---

## 9. Utility Functions

### 9.1 `formatting.py`

**File:** `brainrender_napari/utils/formatting.py`

#### `format_atlas_name(name: str) -> str`

Converts a BrainGlobe snake_case atlas name to a human-friendly string.

| Input | Output |
|---|---|
| `allen_mouse_100um` | `Allen Mouse (100 μm)` |
| `princeton_mouse_20um` | `Princeton Mouse (20 μm)` |
| `osten_mouse_100um` | `Osten Mouse (100 μm)` |

**Algorithm:**
1. `name.split("_")` → list of parts.
2. Capitalise the first part.
3. Replace the last part with `"({resolution_digits} μm)"` by splitting on `"um"` and appending the Unicode micrometer sign (`\u03bc`).
4. `" ".join(formatted_name)`.

This function is called everywhere an atlas name needs to be shown to the user.

#### `format_bytes(num_bytes: float) -> str`

Converts a raw byte count to a human-readable string.

| Input | Output |
|---|---|
| `500` | `"500.00 B"` |
| `1500` | `"1.46 KB"` |
| `1_500_000` | `"1.43 MB"` |
| `1_500_000_000` | `"1.40 GB"` |
| `1_500_000_000_000` | `"1.36 TB"` |

Divides by 1024 at each step. Uses 2 decimal places.

---

### 9.2 `load_user_data.py`

**File:** `brainrender_napari/utils/load_user_data.py`

Both functions build a path to the local atlas directory using `config.get_brainglobe_dir()` and `get_local_atlas_version()`, then open and parse the JSON file.

#### `read_atlas_metadata_from_file(atlas_name: str) -> dict`

Path: `~/.brainglobe/{atlas_name}_v{version}/metadata.json`

Returns a dict with fields such as:
- `name`, `species`, `resolution`, `orientation`
- `atlas_link`, `author`, `citation`
- `additional_references` (list of extra reference keys)

Used by `AtlasViewerView.get_tooltip_text()` to display rich hover information, and by `_on_context_menu_requested()` to detect available additional references.

#### `read_atlas_structures_from_file(atlas_name: str) -> list`

Path: `~/.brainglobe/{atlas_name}_v{version}/structures.json`

Returns a list of structure dicts, each with:
- `id` (int), `acronym` (str), `name` (str)
- `rgb_triplet` (list of 3 ints, 0–255)
- `structure_id_path` (list of ancestor IDs)
- `parent_structure_id` (int)

Used by `StructureView.refresh()` to populate the region tree.

---

## 10. Signal-Slot Connection Map

### `BrainrenderViewerWidget` connections

```
AtlasViewerView
  .add_atlas_requested(str)           → BrainrenderViewerWidget._on_add_atlas_requested(str)
  .additional_reference_requested(str)→ BrainrenderViewerWidget._on_additional_reference_requested(str)
  .selected_atlas_changed(str)        → BrainrenderViewerWidget._on_atlas_selection_changed(str)

QCheckBox (show_structure_names)
  .clicked()                          → BrainrenderViewerWidget._on_show_structure_names_clicked()

StructureView
  .add_structure_requested(str)       → BrainrenderViewerWidget._on_add_structure_requested(str)
```

### `BrainrenderManagerWidget` connections

```
AtlasManagerView
  .progress_updated(int,int,str,obj)  → AtlasProgressBar.update_progress(int,int,str,obj)
  .download_atlas_confirmed(str)      → AtlasProgressBar.operation_completed(str)
  .update_atlas_confirmed(str)        → AtlasProgressBar.operation_completed(str)
```

### `AtlasManagerView` internal connections

```
QTableView.doubleClicked              → AtlasManagerView._on_row_double_clicked()
AtlasManagerDialog.ok_button.clicked  → AtlasManagerView._on_download_atlas_confirmed()
                                        or _on_update_atlas_confirmed()
thread_worker.returned                → emit download/update_atlas_confirmed + refresh_data()
```

### `AtlasViewerView` internal connections

```
QTableView.doubleClicked              → AtlasViewerView._on_row_double_clicked()
selectionModel().currentChanged       → AtlasViewerView._on_current_changed()
customContextMenuRequested            → AtlasViewerView._on_context_menu_requested()
```

### `StructureView` internal connections

```
QTreeView.doubleClicked               → StructureView._on_row_double_clicked()
QTreeView.expanded                    → resize_acronym_column() [lambda]
```

### `NapariAtlasRepresentation` layer callbacks

```
annotation_layer.mouse_move_callbacks → NapariAtlasRepresentation._on_mouse_move
reference_layer.mouse_move_callbacks  → NapariAtlasRepresentation._on_mouse_move
additional_reference.mouse_move_callbacks → NapariAtlasRepresentation._on_mouse_move
```

---

## 11. End-to-End Workflow Walkthroughs

### 11.1 Downloading an Atlas

```
User opens "Manage atlas versions" panel
  → BrainrenderManagerWidget constructed
  → AtlasManagerView.__init__() called
      → AtlasTableModel(AtlasManagerView) created
      → refresh_data() fetches all atlas names and versions from BrainGlobe API
      → Table rendered; not-downloaded atlases shown in grey

User double-clicks a grey (not downloaded) row
  → AtlasManagerView._on_row_double_clicked()
      → atlas NOT in get_downloaded_atlases()
      → AtlasManagerDialog("Download") shown

User clicks "Yes" in dialog
  → dialog.accept() called
  → AtlasManagerDialog.ok_button.clicked signal fired
  → AtlasManagerView._on_download_atlas_confirmed()
      → _apply_in_thread(install_atlas, atlas_name, fn_update=lambda...)
      → Worker starts in separate QThread

During download, fn_update fires repeatedly
  → progress_updated.emit(completed, total, atlas_name, "Downloading")
  → AtlasProgressBar.update_progress() updates bar and label

Download completes
  → worker.returned fires
  → download_atlas_confirmed.emit(atlas_name)
  → source_model.refresh_data() reloads atlas list
  → AtlasProgressBar.operation_completed() resets and hides bar
  → Newly downloaded atlas now shows in normal background colour
```

### 11.2 Visualising an Atlas

```
User opens "Brainrender" panel
  → BrainrenderViewerWidget constructed
  → AtlasViewerView.__init__() called
      → Rows for atlases not in get_downloaded_atlases() hidden
      → Only locally available atlases visible

User double-clicks an atlas row
  → AtlasViewerView._on_row_double_clicked()
  → add_atlas_requested.emit(atlas_name)
  → BrainrenderViewerWidget._on_add_atlas_requested(atlas_name)
      → BrainGlobeAtlas(atlas_name) created (reads from disk)
      → NapariAtlasRepresentation(bg_atlas, viewer) created
          → __post_init__: QLabel tooltip created, napari tooltips enabled
      → add_to_viewer() called
          → viewer.add_image(reference, visible=False)
          → viewer.add_labels(annotation)
          → mouse_move_callbacks registered on both layers
  → napari viewer now shows annotation layer with region colours

User moves cursor over annotation layer (2D mode)
  → _on_mouse_move(layer, event) fires
      → cursor_position obtained from viewer.cursor.position
      → structure_from_coords(cursor_position) → acronym
      → structures[acronym]["name"] → full region name
      → hemisphere_from_coords(cursor_position) → hemisphere
      → self._tooltip.setText("Primary visual cortex | Right")
      → self._tooltip.show() at cursor position + (20px, 20px)
```

### 11.3 Adding a 3D Brain Structure Mesh

```
User selects atlas in "Brainrender" panel
  → AtlasViewerView.selected_atlas_changed(atlas_name) emitted
  → BrainrenderViewerWidget._on_atlas_selection_changed(atlas_name)
      → structure_view.refresh(atlas_name)
          → read_atlas_structures_from_file(atlas_name)
          → StructureTreeModel(structures) built from structures.json
          → Tree expanded to depth 0 (top-level regions visible)
      → structure_tree_group.setVisible(True) — panel appears

User toggles "Show region names" checkbox
  → _on_show_structure_names_clicked()
  → structure_view.refresh(atlas_name, show_structure_names=True)
  → Column 1 (full name) shown/hidden

User double-clicks a region in the tree (e.g. "VISpm")
  → StructureView._on_row_double_clicked()
  → add_structure_requested.emit("VISpm")
  → BrainrenderViewerWidget._on_add_structure_requested("VISpm")
      → BrainGlobeAtlas(selected_atlas_name) created
      → NapariAtlasRepresentation created
      → add_structure_to_viewer("VISpm")
          → show_info if viewer in 2D mode
          → mesh = bg_atlas.mesh_from_structure("VISpm")
          → scale = [1/res for res in atlas.resolution]
          → color = atlas.structures["VISpm"]["rgb_triplet"]
          → _add_mesh(mesh, scale, name, color)
              → np.repeat([[r/255, g/255, b/255]], n_vertices, axis=0)
              → viewer.add_surface((points, cells), scale=scale, ...)
  → Surface layer with atlas-defined colour added to napari
  → Only visible in 3D mode (toggle with the square/cube icon)
```

### 11.4 Searching and Filtering Atlases

```
User types "allen" in the AtlasManagerFilter search box
  → QLineEdit.textChanged → AtlasManagerFilter.apply()
      → query_text = "allen"
      → selected_column = "Any" (default)
      → proxy_model.setFilterKeyColumn(-1)  # search all columns
      → proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
      → proxy_model.setFilterFixedString("allen")
  → Proxy model re-evaluates all rows
  → Only rows where any column contains "allen" remain visible
  → AtlasManagerView updates instantly (no data reload needed)

User changes column selector to "Atlas"
  → QComboBox.currentTextChanged → AtlasManagerFilter.apply()
      → column_index = source_model.column_headers.index("Atlas")
      → proxy_model.setFilterKeyColumn(column_index)
      → Filter re-applied to only the "Atlas" column
```

---

## 12. Design Patterns

### Model/View (Qt)

Both table widgets (`AtlasManagerView`, `AtlasViewerView`) and the tree widget (`StructureView`) follow Qt's Model/View pattern:

```
Data source (BrainGlobe API / local JSON files)
       ↓
  Data Model (AtlasTableModel / StructureTreeModel)
       ↓                         ↓
  [Proxy Model]              (direct)
       ↓
  View (QTableView / QTreeView subclass)
```

Keeping data models separate from views means:
- The same `AtlasTableModel` serves both `AtlasManagerView` and `AtlasViewerView`.
- Filtering via `QSortFilterProxyModel` requires no changes to the underlying model.
- Unit-testing models does not require instantiating Qt views.

### Signal-Slot (Event-Driven)

All inter-component communication uses Qt's signal-slot system. No component holds a direct reference to another component's internals. This makes each widget independently testable and replaceable.

### Thread Worker (`@thread_worker`)

Downloads and updates run in worker threads via napari's `@thread_worker` decorator. This prevents the Qt event loop from blocking, keeping the UI responsive. Progress is communicated back to the main thread via signals.

### Dataclass (`NapariAtlasRepresentation`)

Using a Python `dataclass` for `NapariAtlasRepresentation` gives:
- Automatic `__init__` generation.
- Clean `__post_init__` hook for side-effectful setup.
- Immutability of intent — the representation is configured once and then used.

### Proxy Model (Real-Time Filtering)

`QSortFilterProxyModel` wraps `AtlasTableModel` in `AtlasManagerView`. The proxy intercepts all data requests and row/column count queries, presenting a filtered view without copying or modifying the source data.

### Classmethod Contract (`get_tooltip_text`)

`AtlasTableModel` requires its `view_type` argument to have a `get_tooltip_text` classmethod. This is checked with an `assert` at construction time:

```python
assert hasattr(view_type, "get_tooltip_text"), ...
```

This is a lightweight interface contract: any view class that wants to use `AtlasTableModel` must provide its own tooltip logic.

---

## 13. Configuration and Project Setup

### `pyproject.toml` — Key Sections

```toml
[project]
name = "brainrender-napari"
requires-python = ">=3.11.0"

dependencies = [
    "brainglobe-atlasapi>=2.2.0",
    "brainglobe-utils>=0.4.3",
    "meshio",
    "napari>=0.6.1",
    "numpy",
    "qtpy",
]

[project.entry-points."napari.manifest"]
brainrender-napari = "brainrender_napari:napari.yaml"
```

- Python 3.11, 3.12, and 3.13 are supported.
- The napari plugin manifest is declared via the `napari.manifest` entry point group.

```toml
[tool.pytest.ini_options]
addopts = "--cov=brainrender_napari"
```

All test runs automatically compute code coverage for the `brainrender_napari` package.

```toml
[tool.ruff]
line-length = 79
lint.select = ["I", "E", "F"]
fix = true
```

Ruff checks import order (`I`), PEP 8 errors (`E`), and undefined names (`F`).

---

## 14. Testing Infrastructure

### `tests/conftest.py` — Shared Fixtures

#### `mock_brainglobe_user_folders` (autouse)

Patches `Path.home()` and BrainGlobe config constants to use `~/.brainglobe-tests` instead of `~/.brainglobe`. This protects real user data during local test runs. On GitHub Actions (where `CI=true`), the fixture is a no-op and the real folder is used.

#### `setup_preexisting_local_atlases` (autouse)

Ensures the test environment has three pre-downloaded atlases:
- `example_mouse_100um` v1.2
- `allen_mouse_100um` v1.2
- `osten_mouse_100um` v1.1

Also patches `metadata.json` for `example_mouse_100um` to include an `additional_references` field, enabling tests for that feature.

#### `double_click_on_view(qtbot, view, row)`

A factory fixture that returns a helper function. The helper:
1. Selects the given row.
2. Triggers a click then a double-click at the centre of the row's bounding rect via `qtbot`.

#### `mock_newer_atlas_version_available`

Temporarily renames a local atlas directory from `v1.2` to `v1.1`, simulating a scenario where a newer version is available. Restores the original name after the test.

### Test categories

| Test file | What it covers |
|---|---|
| `test_formatting.py` | `format_bytes` with various input magnitudes |
| `test_metadata_reading.py` | `read_atlas_metadata_from_file`, `read_atlas_structures_from_file` |
| `test_download_update_dialog.py` | `AtlasManagerDialog` title, button labels, valid/invalid atlas names |
| `test_atlas_progress_bar.py` | Progress updates, completion, hiding behaviour |
| `test_atlas_manager_filter.py` | Text search, column selection, case insensitivity |
| `test_atlas_table_model.py` | Data values, background colours, header data, tooltip delegation |
| `test_atlas_manager_view.py` | Download/update flow, signal emission, thread worker, dialog cancel |
| `test_atlas_viewer_view.py` | Layer-add signal, context menu, no-atlas state |
| `test_structure_view.py` | Tree refresh, column visibility, selection, double-click |
| `test_structure_tree_model.py` | Tree building, parent-child relationships, column counts |
| `test_napari_atlas_representation.py` | Layer addition, mesh scaling, tooltip conditions, colour conversion |
| `test_brainrender_manager_widget.py` | Full manager widget integration |
| `test_brainrender_viewer_widget.py` | Full viewer widget integration |

### Running the tests

```bash
# Run all tests with coverage
pytest

# Run only unit tests
pytest tests/test_unit/

# Run a specific test file
pytest tests/test_unit/test_napari_atlas_representation.py -v
```
