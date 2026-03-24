# Plan: Filter Atlas Tables by Species in `brainrender-napari`

> **Goal:** Allow users to filter the atlas table by species using a minimal, surgical, production-quality approach that integrates cleanly with the existing Qt Model/View architecture.

---

## Table of Contents

1. [Codebase Overview](#1-codebase-overview)
2. [Data Architecture & Flow](#2-data-architecture--flow)
3. [Atlas Name Convention & Species Extraction](#3-atlas-name-convention--species-extraction)
4. [All Relevant Existing Functions](#4-all-relevant-existing-functions)
5. [New Functions Required](#5-new-functions-required)
6. [Potential Bugs in Existing Code](#6-potential-bugs-in-existing-code)
7. [Step-by-Step Implementation Plan (Minimal Code)](#7-step-by-step-implementation-plan-minimal-code)
8. [Python & Qt Concepts Required](#8-python--qt-concepts-required)
9. [Testing Strategy](#9-testing-strategy)
10. [Edge Cases & Robustness](#10-edge-cases--robustness)
11. [Summary Diagram](#11-summary-diagram)

---

## 1. Codebase Overview

The project is a [napari](https://napari.org/) plugin that provides two main widgets:

| Widget | File | Purpose |
|---|---|---|
| `BrainrenderManagerWidget` | `brainrender_manager_widget.py` | Download / update atlases |
| `BrainrenderViewerWidget` | `brainrender_viewer_widget.py` | View downloaded atlases |

The plugin follows the **Qt Model/View** architecture. A brief dependency map of all relevant files:

```
BrainrenderManagerWidget
 ├── AtlasManagerView           (widgets/atlas_manager_view.py)
 │    ├── AtlasTableModel       (data_models/atlas_table_model.py)
 │    └── QSortFilterProxyModel (Qt built-in – already in use)
 └── AtlasManagerFilter         (widgets/atlas_manager_filter.py)
      └── AtlasManagerView (reference)

BrainrenderViewerWidget
 └── AtlasViewerView            (widgets/atlas_viewer_view.py)
      └── AtlasTableModel       (data_models/atlas_table_model.py)

Shared Utilities
 └── utils/formatting.py        (format_atlas_name, format_bytes)
 └── utils/load_user_data.py    (read_atlas_metadata_from_file, read_atlas_structures_from_file)
```

---

## 2. Data Architecture & Flow

### How atlas data enters the UI

```
brainglobe-atlasapi (external library)
    │
    ├── get_all_atlases_lastversions()  →  {name: latest_version, ...}
    ├── get_atlases_lastversions()      →  {name: {version, updated}, ...}
    └── get_local_atlas_version(name)  →  "1.2"
         │
         ▼
AtlasTableModel._data  (list[list[str]])
    ├── column 0: Raw name        (e.g. "allen_mouse_100um")  ← hidden in UI
    ├── column 1: Atlas           (e.g. "Allen mouse (100 μm)")
    ├── column 2: Local version   (e.g. "1.2" or "n/a")
    └── column 3: Latest version  (e.g. "1.2")
         │
         ▼
QSortFilterProxyModel
    │  • wraps AtlasTableModel
    │  • setFilterFixedString(query)
    │  • setFilterKeyColumn(col_index)   ← column to match against
    │  • setFilterCaseSensitivity(Qt.CaseInsensitive)
         │
         ▼
AtlasManagerView / AtlasViewerView   (QTableView)
    │  • displays the (filtered) rows
         │
         ▼
AtlasManagerFilter
    • QLineEdit  → query text
    • QComboBox  → which column to search in ("Any", "Atlas", "Local version", …)
```

### Key insight

`QSortFilterProxyModel` already provides all the filtering machinery we need. We only have to:

1. Surface the **species** data as a column in `AtlasTableModel`.
2. Let `AtlasManagerFilter` expose a **species dropdown** that sets the proxy filter.

No new filtering framework is required.

---

## 3. Atlas Name Convention & Species Extraction

BrainGlobe atlas names follow the convention:

```
{provider}_{species[_qualifier]}_{resolution}um
```

Examples:

| Raw name | Provider | Species | Qualifier | Resolution |
|---|---|---|---|---|
| `allen_mouse_100um` | allen | **mouse** | — | 100 µm |
| `allen_human_500um` | allen | **human** | — | 500 µm |
| `mpin_zfish_1um` | mpin | **zfish** | — | 1 µm |
| `azba_zfish_4um` | azba | **zfish** | — | 4 µm |
| `osten_mouse_100um` | osten | **mouse** | — | 100 µm |
| `kim_dev_mouse_10um` | kim | **mouse** | dev | 10 µm |
| `whs_sd_rat_39um` | whs | **rat** | sd | 39 µm |
| `admba_developing_mouse_11.4um` | admba | **mouse** | developing | 11.4 µm |
| `bogovic_drosophila_38um` | bogovic | **drosophila** | — | 38 µm |
| `sj_zebrafish_73um` | sj | **zebrafish** | — | 73 µm |
| `bhann_mouse_5um` | bhann | **mouse** | — | 5 µm |
| `perens_lsfm_mouse_20um` | perens | **mouse** | lsfm | 20 µm |
| `princeton_mouse_20um` | princeton | **mouse** | — | 20 µm |
| `kyle_rat_11.4um` | kyle | **rat** | — | 11.4 µm |

**Pattern observed:** strip the resolution suffix (last `_<number>[.<number>]um` token) → the very **last** remaining underscore-separated token is always the species.

```
"allen_mouse_100um"
  → strip "_100um"  → "allen_mouse"
  → split("_")[-1]  → "mouse"  ✓

"kim_dev_mouse_10um"
  → strip "_10um"   → "kim_dev_mouse"
  → split("_")[-1]  → "mouse"  ✓

"admba_developing_mouse_11.4um"
  → strip "_11.4um" → "admba_developing_mouse"
  → split("_")[-1]  → "mouse"  ✓
```

This heuristic is **robust** across all known BrainGlobe atlas names.

---

## 4. All Relevant Existing Functions

### 4.1 `utils/formatting.py`

#### `format_atlas_name(name: str) -> str`

```python
def format_atlas_name(name: str) -> str:
    """Format an atlas name nicely.
    Assumes input in the form of atlas_name_in_snake_case_RESOLUTIONum,
    e.g. allen_mouse_100um"""
    formatted_name: list[str] = name.split("_")
    formatted_name[0] = formatted_name[0].capitalize()
    formatted_name[-1] = f"({formatted_name[-1].split('um')[0]} \u03bcm)"
    return " ".join(formatted_name)
```

**What it does:** Turns `allen_mouse_100um` into `"Allen mouse (100 μm)"`.
**Relevance:** The same split-by-underscore approach is used as a starting point for species extraction.

---

### 4.2 `data_models/atlas_table_model.py`

#### `AtlasTableModel.__init__`

```python
def __init__(self, view_type: QTableView):
    super().__init__()
    self.column_headers: list[str] = [
        "Raw name",
        "Atlas",
        "Local version",
        "Latest version",
    ]
    assert hasattr(view_type, "get_tooltip_text"), ...
    self.view_type: QTableView = view_type
    self.refresh_data()
```

**Relevance:** `column_headers` defines the column schema. Adding `"Species"` here propagates to all views automatically.

#### `AtlasTableModel.refresh_data`

```python
def refresh_data(self):
    all_atlases: dict[str, str] = get_all_atlases_lastversions()
    local_atlases = get_atlases_lastversions().keys()
    data = []
    for name, latest_version in all_atlases.items():
        if name in local_atlases:
            data.append([
                name,
                format_atlas_name(name),
                get_local_atlas_version(name),
                latest_version,
            ])
        else:
            data.append([name, format_atlas_name(name), "n/a", latest_version])
    self._data = data
```

**Relevance:** Every row is assembled here. Species must be added to each row in this method.

#### `AtlasTableModel.data`

```python
def data(self, index: QModelIndex, role=Qt.DisplayRole):
    if role == Qt.DisplayRole:
        return self._data[index.row()][index.column()]
    if role == Qt.ToolTipRole:
        hovered_atlas_name = self._data[index.row()][0]
        return self.view_type.get_tooltip_text(hovered_atlas_name)
    if role == Qt.BackgroundRole:
        ...
    return None
```

**Relevance:** `DisplayRole` already serves data by column index, so adding a species column requires no changes here beyond adding the data in `refresh_data`.

#### `AtlasTableModel.columnCount`

```python
def columnCount(self, index: QModelIndex = QModelIndex()) -> int:
    return len(self._data[0])
```

**Relevance:** Returns length of the first row — will automatically reflect the new species column once added.

---

### 4.3 `widgets/atlas_manager_filter.py`

#### `AtlasManagerFilter.setup_ui`

```python
def setup_ui(self) -> None:
    self.layout = QHBoxLayout(self)
    self.query_field = QLineEdit(self)
    self.query_field.setPlaceholderText("Search...")
    self.query_field.textChanged.connect(self.apply)
    self.layout.addWidget(QLabel("Query:"))
    self.layout.addWidget(self.query_field)

    self.column_field = QComboBox()
    self.column_field.addItems(
        self.atlas_manager_view.source_model.column_headers
    )
    self.column_field.insertItem(0, "Any")
    for col in self.atlas_manager_view.hidden_columns:
        self.column_field.removeItem(self.column_field.findText(col))
    self.column_field.setCurrentIndex(0)
    self.column_field.currentIndexChanged.connect(self.apply)
    self.layout.addWidget(QLabel("Column:"))
    self.layout.addWidget(self.column_field)
```

**Relevance:** This is where a **Species** QComboBox (or updated column selector) will be added.

#### `AtlasManagerFilter.apply`

```python
def apply(self) -> None:
    query = self.query_field.text()
    column = self.column_field.currentText()

    if column == "Any":
        self.atlas_manager_view.proxy_model.setFilterKeyColumn(-1)
    else:
        column_index = (
            self.atlas_manager_view.source_model.column_headers.index(column)
        )
        self.atlas_manager_view.proxy_model.setFilterKeyColumn(column_index)

    self.atlas_manager_view.proxy_model.setFilterFixedString(query)
```

**Relevance:** This method drives the proxy model. It will need updating or extending to handle species-specific filtering.

---

### 4.4 `widgets/atlas_manager_view.py`

#### `AtlasManagerView.__init__` — `hidden_columns`

```python
self.hidden_columns = ["Raw name"]  # hide raw name
for col in self.hidden_columns:
    self.hideColumn(self.source_model.column_headers.index(col))
```

**Relevance:** The Species column should also be hidden from direct display (it acts as a filter key, not a display column). Add `"Species"` to `hidden_columns`.

#### `AtlasManagerView.selected_atlas_name`

```python
def selected_atlas_name(self) -> str:
    selected_index: QModelIndex = self.selectionModel().currentIndex()
    assert selected_index.isValid()
    selected_atlas_name_index: QModelIndex = selected_index.siblingAtColumn(0)
    selected_atlas_name = self.proxy_model.data(selected_atlas_name_index)
    return selected_atlas_name
```

**Relevance:** Column 0 is the raw name. If columns are added **before** position 0 this would break. Species must be appended **at the end**.

---

### 4.5 `widgets/atlas_viewer_view.py`

#### `AtlasViewerView.__init__` — column hiding

```python
for column_header in ["Raw name", "Local version", "Latest version"]:
    index_to_hide = self.model().column_headers.index(column_header)
    self.hideColumn(index_to_hide)
```

**Relevance:** Species must also be added to this hide list so it doesn't clutter the viewer table.

---

### 4.6 `utils/load_user_data.py`

#### `read_atlas_metadata_from_file(atlas_name: str)`

```python
def read_atlas_metadata_from_file(atlas_name: str):
    """Reads atlas metadata stored in a `.json` in the BrainGlobe directory."""
    brainglobe_dir = config.get_brainglobe_dir()
    with open(
        brainglobe_dir / f"{atlas_name}_v{get_local_atlas_version(atlas_name)}" / "metadata.json",
    ) as metadata_file:
        return json.loads(metadata_file.read())
```

**Relevance:** Downloaded atlases have a `metadata.json` that contains a `"species"` field with the **canonical** species name (e.g. `"Mus musculus"` for mouse). This is an authoritative alternative to name-based extraction — but it only works for **downloaded** atlases. Because we want to filter **all** atlases (including remote ones not yet downloaded), name-based extraction is preferred for the new `"Species"` column.

---

## 5. New Functions Required

### 5.1 `extract_species_from_name(atlas_name: str) -> str`

**File:** `brainrender_napari/utils/formatting.py`

**Purpose:** Parse the species token from a BrainGlobe atlas name.

```python
import re

def extract_species_from_name(atlas_name: str) -> str:
    """Extract the species from a BrainGlobe atlas name.

    Atlas names follow the convention:
        {provider}_{species[_qualifier]}_{resolution}um
    e.g. allen_mouse_100um → 'mouse'
         kim_dev_mouse_10um → 'mouse'
         admba_developing_mouse_11.4um → 'mouse'

    Strategy:
        1. Strip the resolution suffix (last _<number>[.<number>]um token).
        2. The final underscore-separated token is the species.

    Args:
        atlas_name: Raw atlas name string, e.g. 'allen_mouse_100um'.

    Returns:
        Species string in lower-case, e.g. 'mouse'.
    """
    name_without_resolution = re.sub(r"_\d+(\.\d+)?um$", "", atlas_name)
    return name_without_resolution.split("_")[-1]
```

**Why `re.sub` instead of `rsplit`?**
- `rsplit("_", 1)` would split on the last `_`, giving `"100um"` as the suffix — not the clean species token.
- `re.sub` is explicit and handles decimal resolutions like `11.4um` correctly.
- `split("_")[-1]` on the trimmed name unambiguously returns the species.

---

### 5.2 Updated `AtlasTableModel.refresh_data` (modified, not new)

After adding the import and calling `extract_species_from_name`:

```python
# In data_models/atlas_table_model.py

from brainrender_napari.utils.formatting import extract_species_from_name, format_atlas_name

def refresh_data(self):
    all_atlases: dict[str, str] = get_all_atlases_lastversions()
    local_atlases = get_atlases_lastversions().keys()
    data = []
    for name, latest_version in all_atlases.items():
        species = extract_species_from_name(name)
        if name in local_atlases:
            data.append([
                name,
                format_atlas_name(name),
                get_local_atlas_version(name),
                latest_version,
                species,            # ← new column
            ])
        else:
            data.append([
                name,
                format_atlas_name(name),
                "n/a",
                latest_version,
                species,            # ← new column
            ])
    self._data = data
```

And in `__init__`, update `column_headers`:

```python
self.column_headers: list[str] = [
    "Raw name",
    "Atlas",
    "Local version",
    "Latest version",
    "Species",          # ← new
]
```

---

### 5.3 Species Dropdown in `AtlasManagerFilter` (modified, not new)

Add a dedicated `species_field` QComboBox populated dynamically from the model data:

```python
# In widgets/atlas_manager_filter.py

def setup_ui(self) -> None:
    ...
    # --- existing query + column widgets (unchanged) ---

    # Species filter
    self.species_field = QComboBox()
    self.species_field.addItem("All")   # sentinel: no species filter
    species_col = self.atlas_manager_view.source_model.column_headers.index("Species")
    all_species = sorted({
        row[species_col]
        for row in self.atlas_manager_view.source_model._data
    })
    self.species_field.addItems(all_species)
    self.species_field.setCurrentIndex(0)
    self.species_field.currentIndexChanged.connect(self.apply)

    self.layout.addWidget(QLabel("Species:"))
    self.layout.addWidget(self.species_field)
```

---

### 5.4 Updated `AtlasManagerFilter.apply` — multi-criteria filtering

> **Key challenge:** `QSortFilterProxyModel` supports only a single filter at a time. Combining a text query AND a species filter requires overriding `filterAcceptsRow`.

**Approach A – Subclass `QSortFilterProxyModel` (cleanest, most Pythonic):**

```python
# New class, can live in atlas_manager_filter.py or a separate file

from qtpy.QtCore import QSortFilterProxyModel, Qt

class SpeciesFilterProxyModel(QSortFilterProxyModel):
    """Proxy model supporting simultaneous text-query and species filtering."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._species_filter: str = ""   # empty = "All"

    def set_species_filter(self, species: str) -> None:
        """Set the species to filter by. Empty string means no filter."""
        self._species_filter = species
        self.invalidateFilter()          # triggers re-filtering

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        """Returns True if the row passes both the text query and species filter."""
        # 1. Apply the built-in text-query filter first
        if not super().filterAcceptsRow(source_row, source_parent):
            return False

        # 2. Apply species filter
        if self._species_filter:
            source_model = self.sourceModel()
            species_col = source_model.column_headers.index("Species")
            species_index = source_model.index(source_row, species_col, source_parent)
            row_species = source_model.data(species_index, Qt.DisplayRole)
            if row_species != self._species_filter:
                return False

        return True
```

Then in `AtlasManagerView.__init__`, replace:
```python
self.proxy_model = QSortFilterProxyModel()
```
with:
```python
from brainrender_napari.widgets.atlas_manager_filter import SpeciesFilterProxyModel
self.proxy_model = SpeciesFilterProxyModel()
```

And update `AtlasManagerFilter.apply`:
```python
def apply(self) -> None:
    query = self.query_field.text()
    column = self.column_field.currentText()
    species = self.species_field.currentText()

    # Text-query filter (existing logic, unchanged)
    if column == "Any":
        self.atlas_manager_view.proxy_model.setFilterKeyColumn(-1)
    else:
        column_index = (
            self.atlas_manager_view.source_model.column_headers.index(column)
        )
        self.atlas_manager_view.proxy_model.setFilterKeyColumn(column_index)
    self.atlas_manager_view.proxy_model.setFilterFixedString(query)

    # Species filter (new)
    species_value = "" if species == "All" else species
    self.atlas_manager_view.proxy_model.set_species_filter(species_value)
```

**Approach B – Encode species in the text query (simplest, zero new classes):**
Skip the new proxy class. Hide the species column but let "Any" column search include it. The existing QComboBox for columns already lets users pick "Species". Just exposing the Species column via the existing filter is technically sufficient — but less user-friendly than a dedicated dropdown.

> **Recommendation:** Use **Approach A** for the manager widget (full filtering). For the viewer widget (`AtlasViewerView`), species filtering is less critical (it shows only downloaded atlases, typically few). If needed, the same `SpeciesFilterProxyModel` can be applied there too.

---

## 6. Potential Bugs in Existing Code

### Bug 1 — `columnCount` crashes if `_data` is empty

```python
# atlas_table_model.py, line 85
def columnCount(self, index: QModelIndex = QModelIndex()) -> int:
    return len(self._data[0])  # ← IndexError if _data is []
```

**When it triggers:** If `get_all_atlases_lastversions()` returns an empty dict (no network, API change), `self._data` will be `[]` and `self._data[0]` raises `IndexError`.

**Fix:**
```python
def columnCount(self, index: QModelIndex = QModelIndex()) -> int:
    return len(self.column_headers)   # always reliable
```

---

### Bug 2 — `AtlasManagerFilter.column_field` out-of-sync after adding "Species" column

Currently `column_field` is populated from `source_model.column_headers` and then items in `hidden_columns` are removed. When we add `"Species"` to both `column_headers` and `hidden_columns`, the removal logic will correctly omit it from the text-query dropdown — but only if `hidden_columns` is updated before `AtlasManagerFilter` is constructed.

**Constructor order matters:** `AtlasManagerView.__init__` must append `"Species"` to `self.hidden_columns` before the `AtlasManagerFilter` widget is created in `BrainrenderManagerWidget.__init__`.

```python
# atlas_manager_view.py
self.hidden_columns = ["Raw name", "Species"]   # ← add "Species" here
```

---

### Bug 3 — `selected_atlas_name` column 0 assumption

```python
# atlas_manager_view.py
selected_atlas_name_index: QModelIndex = selected_index.siblingAtColumn(0)
```

This assumes column 0 is always the raw atlas name. Because we are **appending** the new Species column at the end (index 4), column 0 remains the raw name and this is safe. **If any future developer inserts a column before index 0, this will silently return wrong data.** The fix is to look up the column by name:

```python
raw_name_col = self.source_model.column_headers.index("Raw name")
selected_atlas_name_index = selected_index.siblingAtColumn(raw_name_col)
```

---

### Bug 4 — `extract_species_from_name` with malformed names

If an atlas name does not end in `_<number>um` (e.g., a future atlas with a different convention), `re.sub` will leave the name unchanged and `split("_")[-1]` will return the last underscore token, which may not be the species.

**Mitigation:** Add input validation in the function:

```python
def extract_species_from_name(atlas_name: str) -> str:
    name_without_resolution = re.sub(r"_\d+(\.\d+)?um$", "", atlas_name)
    if name_without_resolution == atlas_name:
        # Regex did not match — fallback: return empty string
        return "unknown"
    return name_without_resolution.split("_")[-1]
```

---

### Bug 5 — Species dropdown not refreshed after atlas download

When a user downloads an atlas, `AtlasTableModel.refresh_data()` is called (see `atlas_manager_view.py` line 99). However, the species dropdown in `AtlasManagerFilter` is **populated once at construction time** and will not add newly available species. This is not a critical bug (species set doesn't change with downloads), but it is a latent consistency issue for future multi-species atlas additions at runtime.

**Mitigation (optional):** Call `self.atlas_manager_filter._refresh_species_dropdown()` after `refresh_data()`. A `_refresh_species_dropdown` method can be added to `AtlasManagerFilter`.

---

### Bug 6 — `SpeciesFilterProxyModel.filterAcceptsRow` circular dependency

`SpeciesFilterProxyModel` must be imported by `AtlasManagerView` (to replace `QSortFilterProxyModel`), but `AtlasManagerFilter` also uses `AtlasManagerView`. If `SpeciesFilterProxyModel` is defined in `atlas_manager_filter.py`, this creates a **circular import**:

```
atlas_manager_view.py  →  atlas_manager_filter.py (SpeciesFilterProxyModel)
atlas_manager_filter.py →  atlas_manager_view.py  (AtlasManagerView)
```

**Fix:** Define `SpeciesFilterProxyModel` in a **separate file**, e.g.:

```
brainrender_napari/data_models/species_filter_proxy_model.py
```

Both `atlas_manager_view.py` and `atlas_manager_filter.py` can then import from it without a cycle.

---

## 7. Step-by-Step Implementation Plan (Minimal Code)

All changes are listed in dependency order (each step builds on the previous).

---

### Step 1 — Add `extract_species_from_name` to formatting utilities

**File:** `brainrender_napari/utils/formatting.py`

Add one import at the top:
```python
import re
```

Add one new function:
```python
def extract_species_from_name(atlas_name: str) -> str:
    """Extract the species token from a BrainGlobe atlas name."""
    name_without_resolution = re.sub(r"_\d+(\.\d+)?um$", "", atlas_name)
    if name_without_resolution == atlas_name:
        return "unknown"
    return name_without_resolution.split("_")[-1]
```

**Lines added: ~8. No other files affected.**

---

### Step 2 — Add "Species" column to `AtlasTableModel`

**File:** `brainrender_napari/data_models/atlas_table_model.py`

1. Update the import at the top:
   ```python
   from brainrender_napari.utils.formatting import extract_species_from_name, format_atlas_name
   ```

2. Add `"Species"` to `column_headers` in `__init__`:
   ```python
   self.column_headers: list[str] = [
       "Raw name", "Atlas", "Local version", "Latest version", "Species"
   ]
   ```

3. In `refresh_data`, append `extract_species_from_name(name)` to each row.

4. Fix the `columnCount` bug (see §6, Bug 1):
   ```python
   def columnCount(self, index: QModelIndex = QModelIndex()) -> int:
       return len(self.column_headers)
   ```

**Lines changed/added: ~6.**

---

### Step 3 — Create `SpeciesFilterProxyModel` (avoids circular imports)

**New file:** `brainrender_napari/data_models/species_filter_proxy_model.py`

```python
from qtpy.QtCore import QSortFilterProxyModel, Qt


class SpeciesFilterProxyModel(QSortFilterProxyModel):
    """Proxy model that supports simultaneous text-query and species filtering."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._species_filter: str = ""

    def set_species_filter(self, species: str) -> None:
        self._species_filter = species
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        if not super().filterAcceptsRow(source_row, source_parent):
            return False
        if self._species_filter:
            source_model = self.sourceModel()
            species_col = source_model.column_headers.index("Species")
            idx = source_model.index(source_row, species_col, source_parent)
            if source_model.data(idx, Qt.DisplayRole) != self._species_filter:
                return False
        return True
```

**Lines added: ~20. New file, no existing code changed.**

---

### Step 4 — Swap proxy model in `AtlasManagerView`

**File:** `brainrender_napari/widgets/atlas_manager_view.py`

1. Update import:
   ```python
   from brainrender_napari.data_models.species_filter_proxy_model import SpeciesFilterProxyModel
   ```

2. In `__init__`, replace:
   ```python
   self.proxy_model = QSortFilterProxyModel()
   ```
   with:
   ```python
   self.proxy_model = SpeciesFilterProxyModel()
   ```

3. Add `"Species"` to `hidden_columns`:
   ```python
   self.hidden_columns = ["Raw name", "Species"]
   ```

**Lines changed: 3.**

---

### Step 5 — Add species dropdown to `AtlasManagerFilter`

**File:** `brainrender_napari/widgets/atlas_manager_filter.py`

In `setup_ui`, after the existing column selector widgets:

```python
# Species filter dropdown
self.species_field = QComboBox()
self.species_field.addItem("All")
species_col = self.atlas_manager_view.source_model.column_headers.index("Species")
all_species = sorted({row[species_col] for row in self.atlas_manager_view.source_model._data})
self.species_field.addItems(all_species)
self.species_field.setCurrentIndex(0)
self.species_field.currentIndexChanged.connect(self.apply)
self.layout.addWidget(QLabel("Species:"))
self.layout.addWidget(self.species_field)
```

In `apply`:

```python
def apply(self) -> None:
    query = self.query_field.text()
    column = self.column_field.currentText()
    species = self.species_field.currentText()

    if column == "Any":
        self.atlas_manager_view.proxy_model.setFilterKeyColumn(-1)
    else:
        column_index = self.atlas_manager_view.source_model.column_headers.index(column)
        self.atlas_manager_view.proxy_model.setFilterKeyColumn(column_index)
    self.atlas_manager_view.proxy_model.setFilterFixedString(query)

    self.atlas_manager_view.proxy_model.set_species_filter(
        "" if species == "All" else species
    )
```

**Lines changed/added: ~15.**

---

### Step 6 — Hide "Species" in `AtlasViewerView`

**File:** `brainrender_napari/widgets/atlas_viewer_view.py`

In `__init__`, add `"Species"` to the column-hiding list:

```python
for column_header in ["Raw name", "Local version", "Latest version", "Species"]:
    index_to_hide = self.model().column_headers.index(column_header)
    self.hideColumn(index_to_hide)
```

**Lines changed: 1.**

---

### Step 7 — Write tests

**New/updated test files:**

| File | Tests to add |
|---|---|
| `tests/test_unit/test_formatting.py` | `test_extract_species_from_name` with parametrize |
| `tests/test_unit/test_atlas_table_model.py` | Column count = 5, species data populated |
| `tests/test_unit/test_atlas_manager_filter.py` | Species dropdown appears; filtering by species works |
| `tests/test_unit/test_species_filter_proxy_model.py` (new) | `filterAcceptsRow` with and without species filter |

---

### Total Lines Changed / Added

| File | Change type | Approx. lines |
|---|---|---|
| `utils/formatting.py` | Add function | +10 |
| `data_models/atlas_table_model.py` | Add column | +6 |
| `data_models/species_filter_proxy_model.py` | New file | +22 |
| `widgets/atlas_manager_view.py` | Swap proxy + hidden_columns | +4 |
| `widgets/atlas_manager_filter.py` | Add species UI + apply logic | +15 |
| `widgets/atlas_viewer_view.py` | Hide new column | +1 |
| Tests | New/updated tests | ~60 |
| **Total** | | **~118** |

---

## 8. Python & Qt Concepts Required

### Python Concepts

| Concept | Used where |
|---|---|
| **Regular expressions (`re` module)** | `extract_species_from_name` — `re.sub` to strip resolution suffix |
| **Set comprehension** | `{row[species_col] for row in ...}` — unique species extraction |
| **`sorted()` on sets** | Deterministic ordering of species in dropdown |
| **List indexing** | `split("_")[-1]` — last token extraction |
| **Type hints** | `str`, `list[str]`, `dict[str, str]` — used throughout the codebase |
| **`dataclass` / `list[list[str]]`** | `_data` structure — 2D list used as table data |
| **Method overriding** | `SpeciesFilterProxyModel.filterAcceptsRow` overrides Qt base class |
| **`@classmethod`** | `get_tooltip_text` — no instance state needed |
| **Module-level constants** | Avoid magic strings by using `column_headers.index("Species")` |

### Qt / qtpy Concepts

| Concept | Used where |
|---|---|
| **`QAbstractTableModel`** | `AtlasTableModel` — custom tabular data model |
| **`QSortFilterProxyModel`** | Base of `SpeciesFilterProxyModel` — wraps source model, applies filter |
| **`filterAcceptsRow`** | Override point for multi-criteria filtering |
| **`invalidateFilter()`** | Tell proxy to re-evaluate all rows after filter state change |
| **`QComboBox`** | Species dropdown widget |
| **Signal/Slot (`currentIndexChanged.connect`)** | Reactive filtering on species change |
| **`setFilterKeyColumn(-1)`** | Tell proxy to match against all columns |
| **`setFilterFixedString`** | Plain-text filter (no regex) |
| **`setFilterCaseSensitivity(Qt.CaseInsensitive)`** | Case-insensitive matching |
| **`QModelIndex.siblingAtColumn(n)`** | Navigate within same row to a different column |
| **`hideColumn(n)`** | Hide a column in `QTableView` without removing it from model |
| **`QTableView.SelectionBehavior.SelectRows`** | Whole-row selection |
| **`proxy.data(index)`** | Get data through proxy (respects row-mapping after filtering) |

### Testing Concepts

| Concept | Used where |
|---|---|
| **`pytest.mark.parametrize`** | Test multiple atlas name → species pairs in one test |
| **`pytest-qt` (`qtbot`)** | Interact with Qt widgets without a display server |
| **`mocker.Mock`** | Mock `get_tooltip_text` in model tests (already in use) |
| **`monkeypatch`** | Override filesystem paths (already in `conftest.py`) |
| **`QSortFilterProxyModel.rowCount()`** | Assert filtered row count in filter tests |

---

## 9. Testing Strategy

### Unit Tests

#### `test_extract_species_from_name`

```python
import pytest
from brainrender_napari.utils.formatting import extract_species_from_name

@pytest.mark.parametrize("atlas_name, expected_species", [
    ("allen_mouse_100um",            "mouse"),
    ("allen_human_500um",            "human"),
    ("mpin_zfish_1um",               "zfish"),
    ("kim_dev_mouse_10um",           "mouse"),
    ("whs_sd_rat_39um",              "rat"),
    ("admba_developing_mouse_11.4um","mouse"),
    ("bogovic_drosophila_38um",      "drosophila"),
    ("sj_zebrafish_73um",            "zebrafish"),
    ("example_mouse_100um",          "mouse"),
])
def test_extract_species_from_name(atlas_name, expected_species):
    assert extract_species_from_name(atlas_name) == expected_species


def test_extract_species_from_name_malformed():
    """Malformed names without resolution suffix return 'unknown'."""
    assert extract_species_from_name("no_resolution") == "unknown"
```

---

#### `test_atlas_table_model_has_species_column`

```python
def test_model_has_species_column(atlas_table_model):
    assert "Species" in atlas_table_model.column_headers
    assert atlas_table_model.columnCount() == 5


def test_model_species_data_populated(atlas_table_model):
    species_col = atlas_table_model.column_headers.index("Species")
    for row_idx in range(atlas_table_model.rowCount()):
        idx = atlas_table_model.index(row_idx, species_col)
        species = atlas_table_model.data(idx)
        assert species and species != ""   # non-empty string
```

---

#### `test_species_filter_proxy_model`

```python
from brainrender_napari.data_models.species_filter_proxy_model import SpeciesFilterProxyModel
from brainrender_napari.widgets.atlas_manager_view import AtlasManagerView

def test_species_filter_shows_only_mouse(qtbot):
    view = AtlasManagerView()
    proxy: SpeciesFilterProxyModel = view.proxy_model
    proxy.set_species_filter("mouse")
    for row in range(proxy.rowCount()):
        species_col = view.source_model.column_headers.index("Species")
        idx = proxy.index(row, species_col)
        assert proxy.data(idx) == "mouse"

def test_species_filter_all_clears_filter(qtbot):
    view = AtlasManagerView()
    proxy: SpeciesFilterProxyModel = view.proxy_model
    total_rows = proxy.rowCount()
    proxy.set_species_filter("mouse")
    assert proxy.rowCount() < total_rows
    proxy.set_species_filter("")
    assert proxy.rowCount() == total_rows
```

---

#### `test_atlas_manager_filter_species_dropdown`

```python
from brainrender_napari.widgets.atlas_manager_filter import AtlasManagerFilter
from brainrender_napari.widgets.atlas_manager_view import AtlasManagerView

def test_species_dropdown_present(qtbot):
    view = AtlasManagerView()
    filt = AtlasManagerFilter(atlas_manager_view=view)
    assert hasattr(filt, "species_field")
    # "All" is always the first item
    assert filt.species_field.itemText(0) == "All"
    # At least one species is present
    assert filt.species_field.count() > 1

def test_species_dropdown_filters_table(qtbot):
    view = AtlasManagerView()
    filt = AtlasManagerFilter(atlas_manager_view=view)
    total_rows = view.proxy_model.rowCount()

    mouse_index = filt.species_field.findText("mouse")
    filt.species_field.setCurrentIndex(mouse_index)

    assert view.proxy_model.rowCount() < total_rows
    assert view.proxy_model.rowCount() > 0
```

---

### Integration Tests

Add to `tests/test_integration/test_brainrender_manager_widget.py`:

```python
def test_manager_widget_has_species_filter(make_napari_viewer):
    viewer = make_napari_viewer()
    widget = BrainrenderManagerWidget(napari_viewer=viewer)
    assert hasattr(widget.atlas_manager_filter, "species_field")
```

---

## 10. Edge Cases & Robustness

| Scenario | Expected behaviour |
|---|---|
| Atlas name has no resolution suffix (e.g., future format) | `extract_species_from_name` returns `"unknown"` |
| All atlases are the same species | Dropdown shows "All" + one species; filter still works |
| Species filter + text query both active | `SpeciesFilterProxyModel.filterAcceptsRow` applies both; only rows satisfying **both** are shown |
| User clears species back to "All" | `set_species_filter("")` → `invalidateFilter()` → all rows reappear |
| `get_all_atlases_lastversions()` returns empty dict | `columnCount` returns `len(self.column_headers)` (Bug 1 fix); no crash |
| Atlas downloaded after widget construction | Species dropdown remains valid (set of species doesn't change with download) |
| Dark / light theme toggling | `BackgroundRole` logic is unchanged; species column uses default background |
| `AtlasViewerView` (viewer widget) | `"Species"` added to its hide list; viewer is unaffected functionally |

---

## 11. Summary Diagram

```
utils/formatting.py
 └── extract_species_from_name(name) ──────────────┐
                                                    │
data_models/atlas_table_model.py                    │
 └── AtlasTableModel                                │
      ├── column_headers = [..., "Species"]         │
      └── refresh_data()  ←── uses ────────────────┘
           └── _data rows have species as col[4]

data_models/species_filter_proxy_model.py  (NEW)
 └── SpeciesFilterProxyModel(QSortFilterProxyModel)
      ├── set_species_filter(species)
      │    └── invalidateFilter()
      └── filterAcceptsRow(row, parent)
           ├── parent.filterAcceptsRow(...)  [text query]
           └── check species column          [species filter]

widgets/atlas_manager_view.py
 └── AtlasManagerView(QTableView)
      ├── source_model = AtlasTableModel(...)
      ├── proxy_model  = SpeciesFilterProxyModel()  ← was QSortFilterProxyModel
      └── hidden_columns = ["Raw name", "Species"]  ← added "Species"

widgets/atlas_manager_filter.py
 └── AtlasManagerFilter(QWidget)
      ├── query_field   (QLineEdit)
      ├── column_field  (QComboBox)
      ├── species_field (QComboBox)  ← NEW
      └── apply()
           ├── proxy.setFilterFixedString(query)
           ├── proxy.setFilterKeyColumn(col)
           └── proxy.set_species_filter(species)   ← NEW

widgets/atlas_viewer_view.py
 └── AtlasViewerView
      └── hideColumn("Species")  ← added to existing hide list

BrainrenderManagerWidget
 ├── AtlasManagerView
 └── AtlasManagerFilter  (now shows species dropdown)
```

---

*End of plan. Total production code estimate: ~58 lines changed / added across 6 files + 1 new file of 22 lines.*
