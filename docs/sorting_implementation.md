# Sorting Functionality in brainrender-napari Tables

*A detailed guide covering the design, implementation, durability concerns, bug
analysis, and Python concepts behind the sorting feature.*

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture: Qt Model / View / Proxy](#architecture-qt-model--view--proxy)
3. [What Was Changed and Why](#what-was-changed-and-why)
4. [Full Implementation Reference](#full-implementation-reference)
5. [Durability Issues and Bug Analysis](#durability-issues-and-bug-analysis)
6. [Python Concepts Applied](#python-concepts-applied)
7. [Test Strategy](#test-strategy)
8. [Integration Checklist](#integration-checklist)

---

## Overview

Both table widgets in brainrender-napari — the **Atlas Manager** (`AtlasManagerView`) and the
**Atlas Viewer** (`AtlasViewerView`) — display atlas data in a `QTableView`.
Before this change, the rows were always in the order returned by the BrainGlobe Atlas API,
with no way to reorder them interactively.

The sorting feature lets users click any visible column header to sort rows alphabetically or
numerically, and click again to reverse the order. A sort indicator arrow appears in the header
automatically.

---

## Architecture: Qt Model / View / Proxy

Understanding Qt's Model/View architecture is essential. The three classes involved are:

```
┌─────────────────────┐       ┌────────────────────────┐       ┌──────────────┐
│   AtlasTableModel   │──────▶│  QSortFilterProxyModel │──────▶│ QTableView   │
│ (source of truth)   │       │  (sort + filter layer) │       │ (renders UI) │
└─────────────────────┘       └────────────────────────┘       └──────────────┘
  QAbstractTableModel              sits between                  reads from
  holds _data list                 model & view                  the proxy
```

### Why the proxy model is necessary

`QTableView` can technically sort its own rows, but only when the underlying model implements the
`sort()` method. `QAbstractTableModel` does **not** implement `sort()` by default.
`QSortFilterProxyModel` wraps any source model and provides a stable, reusable sort + filter layer
with no changes to the source data.

Key consequence: **the source model row index and the proxy row index are different after sorting**.
Every method that reads from or writes to the model must go through the proxy for `DisplayRole`
data, not query the source model directly.

---

## What Was Changed and Why

### `AtlasManagerView` — one line

```python
# brainrender_napari/widgets/atlas_manager_view.py

# Before
self.doubleClicked.connect(self._on_row_double_clicked)

# After
self.setSortingEnabled(True)          # ← the only change
self.doubleClicked.connect(self._on_row_double_clicked)
```

The view already owned a `QSortFilterProxyModel` (required for the search/filter widget
`AtlasManagerFilter`). Calling `setSortingEnabled(True)` instructs Qt to:

1. Make column headers clickable.
2. Call `proxy_model.sort(column, order)` on each header click.
3. Draw a sort indicator arrow in the active header section.

No changes to the data model, filter logic, or signal-slot wiring were needed.

---

### `AtlasViewerView` — proxy model + three targeted edits

The viewer view previously had **no proxy model at all**. It used a raw `hideRow()` loop to hide
atlases not yet downloaded. That approach is **fundamentally incompatible** with sorting:

```
Problem: hideRow() records which row *indices* should be invisible.
         After a sort, every row has a new index.
         The hidden rows are now the wrong rows.
```

The fix introduces a custom proxy model subclass that replaces `hideRow()`:

#### 1. New proxy subclass `_DownloadedAtlasProxyModel`

```python
class _DownloadedAtlasProxyModel(QSortFilterProxyModel):
    """Proxy model that filters to show only locally downloaded atlases."""

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex
    ) -> bool:
        atlas_name = self.sourceModel().data(
            self.sourceModel().index(source_row, 0)
        )
        return atlas_name in get_downloaded_atlases()
```

`filterAcceptsRow` is Qt's hook for row-level filtering. It is called against **source model rows**,
not proxy rows, so it remains correct regardless of the current sort order. It queries column 0
("Raw name") of the source model because that holds the canonical machine-readable atlas name
used by `get_downloaded_atlases()`.

#### 2. Updated `__init__`

```python
# Old approach
self.setModel(AtlasTableModel(AtlasViewerView))
# ... later ...
for row_index in range(self.model().rowCount()):
    index = self.model().index(row_index, 0)
    if self.model().data(index) not in get_downloaded_atlases():
        self.hideRow(row_index)

# New approach
self.source_model = AtlasTableModel(AtlasViewerView)
self.proxy_model = _DownloadedAtlasProxyModel()
self.proxy_model.setSourceModel(self.source_model)
self.setModel(self.proxy_model)
# No hideRow loop needed — proxy handles it
self.setSortingEnabled(True)
```

The `source_model` attribute is also exposed on the instance (as `AtlasManagerView` already did),
which lets tests and external code access `column_headers` without going through the proxy.

#### 3. Updated `selected_atlas_name()`

```python
# Old — queried the direct model, not the proxy
selected_atlas_name = self.model().data(selected_atlas_name_index)

# New — queries the proxy, which maps proxy index → source index transparently
selected_atlas_name = self.proxy_model.data(selected_atlas_name_index)
```

`self.model()` returns the proxy model (because `setModel(self.proxy_model)` was called), so
both lines ultimately produce the same value _in the absence of sorting_. However, querying
`self.proxy_model.data()` is semantically cleaner and matches the `AtlasManagerView` pattern.
The explicit reference to `self.proxy_model` also makes the data-flow obvious to future readers.

---

## Full Implementation Reference

### File: `brainrender_napari/widgets/atlas_viewer_view.py`

```python
from typing import Tuple

from brainglobe_atlasapi.list_atlases import get_downloaded_atlases
from qtpy.QtCore import QModelIndex, QSortFilterProxyModel, Qt, Signal
from qtpy.QtWidgets import QMenu, QTableView, QWidget

from brainrender_napari.data_models.atlas_table_model import AtlasTableModel
from brainrender_napari.utils.formatting import format_atlas_name
from brainrender_napari.utils.load_user_data import read_atlas_metadata_from_file


class _DownloadedAtlasProxyModel(QSortFilterProxyModel):
    """Proxy model that filters to show only locally downloaded atlases."""

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex
    ) -> bool:
        atlas_name = self.sourceModel().data(
            self.sourceModel().index(source_row, 0)
        )
        return atlas_name in get_downloaded_atlases()


class AtlasViewerView(QTableView):
    add_atlas_requested = Signal(str)
    no_atlas_available = Signal()
    additional_reference_requested = Signal(str)
    selected_atlas_changed = Signal(str)

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)

        self.source_model = AtlasTableModel(AtlasViewerView)
        self.proxy_model = _DownloadedAtlasProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.setModel(self.proxy_model)

        self.setEnabled(True)
        self.verticalHeader().hide()
        self.resizeColumnsToContents()

        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu_requested)

        self.setSortingEnabled(True)
        self.doubleClicked.connect(self._on_row_double_clicked)
        self.selectionModel().currentChanged.connect(self._on_current_changed)

        for column_header in ["Raw name", "Local version", "Latest version"]:
            index_to_hide = self.source_model.column_headers.index(column_header)
            self.hideColumn(index_to_hide)

        if len(get_downloaded_atlases()) == 0:
            self.no_atlas_available.emit()

    def selected_atlas_name(self) -> str:
        selected_index: QModelIndex = self.selectionModel().currentIndex()
        assert selected_index.isValid()
        selected_atlas_name_index: QModelIndex = selected_index.siblingAtColumn(0)
        selected_atlas_name = self.proxy_model.data(selected_atlas_name_index)
        assert selected_atlas_name in get_downloaded_atlases()
        return selected_atlas_name

    # ... rest unchanged ...
```

### File: `brainrender_napari/widgets/atlas_manager_view.py`

The only change is `self.setSortingEnabled(True)` added after `self.setSelectionMode(...)`.

---

## Durability Issues and Bug Analysis

The following issues were identified by reading the code carefully and reasoning about failure
modes.

---

### Issue 1 — `hideRow()` is sorting-incompatible *(fixed)*

| | |
|---|---|
| **Symptom** | After sorting, previously hidden rows re-appear or wrong rows are hidden. |
| **Root cause** | `hideRow(n)` stores the visual row index `n`. When a sort re-orders rows, the stored indices no longer correspond to the intended rows. |
| **Fix** | Replace `hideRow()` with `_DownloadedAtlasProxyModel.filterAcceptsRow()`, which is evaluated per *source* row, not per *proxy* row. It is sort-order-independent. |

---

### Issue 2 — `selected_atlas_name()` must query the proxy, not the source model

| | |
|---|---|
| **Symptom** | After sorting, double-clicking a row downloads/opens the *wrong* atlas. |
| **Root cause** | If `self.model().data(index)` is called with a *proxy* index, and `self.model()` returns the proxy, Qt internally calls `mapToSource` behind the scenes. This is correct. However, calling `self.source_model.data(proxy_index)` directly would be **undefined behaviour** — the source model interprets proxy row numbers as source row numbers, which are different after sorting. |
| **Fix** | Always use `self.proxy_model.data(proxy_index)` (or `self.model().data(proxy_index)` since `model()` returns the proxy). Never pass a proxy `QModelIndex` to `self.source_model`. |

---

### Issue 3 — `filterAcceptsRow` calls `get_downloaded_atlases()` on every row on every sort

| | |
|---|---|
| **Symptom** | Sluggish UI when sorting a large atlas list because `get_downloaded_atlases()` performs a filesystem scan on every call. |
| **Root cause** | Qt calls `filterAcceptsRow` for every source row each time the sort order changes. The current atlas list has ~40 atlases; at this scale the cost is imperceptible. |
| **When it matters** | If the atlas list grows significantly (hundreds of entries) or if `get_downloaded_atlases()` becomes slow. |
| **Mitigation** | Cache the downloaded-atlas set inside the proxy, invalidate it on `source_model.refresh_data()`. Example: |

```python
class _DownloadedAtlasProxyModel(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self._downloaded: set[str] = set()

    def refresh_downloaded_cache(self) -> None:
        self._downloaded = set(get_downloaded_atlases())
        self.invalidateFilter()   # re-run filterAcceptsRow for all rows

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        atlas_name = self.sourceModel().data(
            self.sourceModel().index(source_row, 0)
        )
        return atlas_name in self._downloaded
```

Then call `proxy_model.refresh_downloaded_cache()` whenever `source_model.refresh_data()` is
called (e.g., after a download or update completes).

---

### Issue 4 — `setSortingEnabled(True)` resets the sort on every `refresh_data()`

| | |
|---|---|
| **Symptom** | After downloading or updating an atlas, the table jumps back to the default (unsorted) order. |
| **Root cause** | If `refresh_data()` is ever refactored to call `beginResetModel()` / `endResetModel()`, Qt resets the proxy sort state. |
| **Current status** | Not a present problem because `refresh_data()` mutates `_data` in place without the reset signals. |
| **Mitigation** | Save and restore sort state around data refreshes: |

```python
def _restore_sort_after_refresh(self):
    col = self.horizontalHeader().sortIndicatorSection()
    order = self.horizontalHeader().sortIndicatorOrder()
    self.source_model.refresh_data()
    self.sortByColumn(col, order)
```

---

### Issue 5 — `AtlasTableModel.data()` does not guard against an invalid index

| | |
|---|---|
| **Symptom** | `IndexError` if `data()` is called with an out-of-range row. |
| **Root cause** | `self._data[index.row()][index.column()]` assumes `index` is valid and in range. |
| **Mitigation** | Add an early return for invalid indexes: |

```python
def data(self, index: QModelIndex, role=Qt.DisplayRole):
    if not index.isValid():
        return None
    if not (0 <= index.row() < len(self._data)):
        return None
    # ... rest of method ...
```

---

### Issue 6 — Sort is lexicographic, not semantic, for version strings

| | |
|---|---|
| **Symptom** | Sorting "Local version" or "Latest version" orders `"1.10"` before `"1.2"` because `"10" < "2"` lexicographically. |
| **Root cause** | `QSortFilterProxyModel` uses Qt's default string comparison. Version strings are not zero-padded. |
| **Current status** | Not a problem today because version numbers use single-digit minor versions. |
| **Mitigation** | Override `lessThan()` in the proxy to use `packaging.version` for version columns: |

```python
from packaging.version import Version, InvalidVersion

class _DownloadedAtlasProxyModel(QSortFilterProxyModel):
    _VERSION_COLUMNS = {"Local version", "Latest version"}

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        col_name = self.sourceModel().column_headers[left.column()]
        if col_name in self._VERSION_COLUMNS:
            left_val = self.sourceModel().data(left) or "0"
            right_val = self.sourceModel().data(right) or "0"
            try:
                return Version(left_val) < Version(right_val)
            except InvalidVersion:
                pass
        return super().lessThan(left, right)
```

---

### Issue 7 — Column hiding uses source model indices

| | |
|---|---|
| **Note** | `hideColumn(n)` takes a **source model column index**, not a proxy column index. `QSortFilterProxyModel` does not re-order columns by default, so source and proxy column indices are the same. If column re-ordering is ever enabled, this assumption must be revisited. |
| **Current status** | Not a problem at present. |

---

### Issue 8 — `no_atlas_available` signal fires before connections are made

| | |
|---|---|
| **Symptom** | If no atlas is downloaded, the `no_atlas_available` signal fires in `__init__` before any observer connects to it, so the signal is silently lost. |
| **Root cause** | Python/Qt signal connections are set up *after* `__init__` returns. |
| **Mitigation** | Emit via `QTimer.singleShot(0, self.no_atlas_available)` to defer to the next event-loop iteration, giving observers time to connect: |

```python
from qtpy.QtCore import QTimer

if len(get_downloaded_atlases()) == 0:
    QTimer.singleShot(0, self.no_atlas_available)
```

---

## Python Concepts Applied

### 1. Inheritance and Method Overriding

`_DownloadedAtlasProxyModel` **extends** `QSortFilterProxyModel` and **overrides** only
`filterAcceptsRow`. This follows the **Open/Closed Principle**: the base class is open for
extension, closed for modification.

```python
class _DownloadedAtlasProxyModel(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent):
        # Only this method is overridden; sort() and lessThan() come from the base
        ...
```

Python resolves method calls through the **Method Resolution Order (MRO)**. When Qt internally
calls `proxy.filterAcceptsRow(row, parent)`, Python's MRO finds the overridden version in
`_DownloadedAtlasProxyModel` first, before falling through to `QSortFilterProxyModel`.

---

### 2. Name Mangling and Private-by-Convention

The class is named `_DownloadedAtlasProxyModel` with a **leading underscore**. In Python this is a
convention meaning "module-private" — not enforced by the runtime, but signals to tools and
readers that this class is an implementation detail of the module, not part of its public API.

Double underscores (`__ClassName`) trigger true **name mangling** inside a class body, but for
module-level names a single underscore is the idiomatic choice.

---

### 3. Qt Signals and Slots — Python's `Signal` descriptor

Qt's publish/subscribe mechanism is exposed in Python via `qtpy.QtCore.Signal`. A `Signal`
declared at class level is a **descriptor** — it behaves differently when accessed on the class
versus on an instance:

```python
class AtlasViewerView(QTableView):
    add_atlas_requested = Signal(str)   # class-level descriptor
    # ...
    def _on_row_double_clicked(self):
        self.add_atlas_requested.emit("some_atlas")  # instance-level emit
```

Sorting does not add or remove signals. All existing signals continue to work because the proxy
model preserves the selection — when the user clicks a row after sorting, `currentChanged` fires
with a **proxy index**, and `selected_atlas_name()` correctly maps it back to source data via
`proxy_model.data(proxy_index)`.

---

### 4. `QModelIndex` — value semantics and index validity

`QModelIndex` objects in Qt are **value types** that carry `(row, column, internal_pointer)`.
A proxy index and its corresponding source index have the same `(row, column)` coordinates only
when the sort order is the identity permutation. After sorting, proxy row 0 may map to source row 7.

The proxy handles this transparently: `proxy_model.data(proxy_index)` calls
`proxy_model.mapToSource(proxy_index)` internally and then queries the source model with the
correct source index.

**Key rule:** never pass a proxy `QModelIndex` to the source model's `data()` method directly.
Always let the proxy translate via `proxy.data()`, `proxy.mapToSource()`, or `proxy.index()`.

---

### 5. Template Method Pattern — `filterAcceptsRow` as a hook

Qt uses a **Template Method** pattern. `QSortFilterProxyModel` defines the algorithm:
*"for each source row, call `filterAcceptsRow`; include the row only if it returns `True`"*.
Subclasses fill in the hook. This pattern is common in both Qt and Python's standard library
(e.g., `unittest.TestCase.setUp`, `logging.Handler.emit`).

```python
# Qt's internal logic (conceptually)
for source_row in range(source_model.rowCount()):
    if self.filterAcceptsRow(source_row, QModelIndex()):
        add_to_visible_rows(source_row)
```

---

### 6. `set` membership for O(1) lookup

`get_downloaded_atlases()` returns a `list[str]`. The expression:

```python
return atlas_name in get_downloaded_atlases()
```

performs a linear scan — O(n) per call. Because `filterAcceptsRow` is called once per source
row per invalidation, this is O(n²) overall. Converting to a `set` reduces the inner check to
O(1) (hash lookup):

```python
downloaded: set[str] = set(get_downloaded_atlases())
return atlas_name in downloaded  # O(1)
```

At the current scale (~40 atlases) this makes no measurable difference, but it is the correct
pattern for membership testing.

---

### 7. Type annotations — modern built-in generics

The codebase uses modern Python 3.9+ built-in generic syntax (`list[str]`, `dict[str, str]`)
rather than `typing.List` / `typing.Dict`. This requires no imports from `typing` for basic
container types. `Callable` and `Tuple` still come from `typing` because they are conventional
in Qt-facing code.

---

### 8. `assert` vs explicit exceptions

`selected_atlas_name()` uses `assert` to guard against invalid indices:

```python
assert selected_index.isValid()
assert selected_atlas_name in get_downloaded_atlases()
```

`assert` statements are **removed at runtime when Python is run with the `-O` (optimise) flag**.
For production GUI code, raising `ValueError` or `RuntimeError` explicitly is safer. The current
use is acceptable because:

- napari does not run Python with optimisation flags.
- The guards protect against programming errors (calling the method when no row is selected),
  not user-input errors.

If these methods were part of a public library API, explicit exceptions would be preferred.

---

## Test Strategy

### What the new tests verify

| Test | Widget | What it checks |
|---|---|---|
| `test_sorting_enabled_manager_view` | Manager | `isSortingEnabled()` returns `True` |
| `test_sort_atlas_manager_view` | Manager | Ascending order is alphabetical; descending is its reverse |
| `test_sorting_enabled_viewer_view` | Viewer | `isSortingEnabled()` returns `True` |
| `test_sort_atlas_viewer_view` | Viewer | Same alphabetical assertions |
| `test_atlas_viewer_view_only_shows_downloaded_atlases` | Viewer | Every visible proxy row is a downloaded atlas |

### Why row numbers changed in existing tests

Before this change, `AtlasViewerView` used a bare `AtlasTableModel` showing all ~40 atlases, with
certain rows hidden via `hideRow()`. Existing tests referenced source-model rows such as row 4
(`allen_mouse_100um`) and row 14 (`osten_mouse_100um`).

After this change, the proxy model only exposes the 3 pre-downloaded test atlases. The proxy
re-numbers them 0, 1, 2 in API-return order. Tests now reference proxy rows 0, 1, 2.

### Running the tests

```bash
# Run only the sorting-related tests
pytest tests/test_unit/test_atlas_manager_view.py::test_sorting_enabled_manager_view \
       tests/test_unit/test_atlas_manager_view.py::test_sort_atlas_manager_view \
       tests/test_unit/test_atlas_viewer_view.py::test_sorting_enabled_viewer_view \
       tests/test_unit/test_atlas_viewer_view.py::test_sort_atlas_viewer_view \
       tests/test_unit/test_atlas_viewer_view.py::test_atlas_viewer_view_only_shows_downloaded_atlases \
       -v

# Run the full unit suite
pytest tests/test_unit/ -v
```

---

## Integration Checklist

Use this checklist when reviewing or extending the sorting feature.

- [ ] Both `AtlasManagerView` and `AtlasViewerView` call `setSortingEnabled(True)` in `__init__`.
- [ ] `AtlasViewerView` uses `_DownloadedAtlasProxyModel` (not raw `hideRow()`).
- [ ] `selected_atlas_name()` in both views queries `self.proxy_model.data(proxy_index)`.
- [ ] Column hiding (`hideColumn(n)`) uses `source_model.column_headers.index(name)` for the index.
- [ ] `AtlasManagerFilter.apply()` still targets `atlas_manager_view.proxy_model` — unaffected by
      sort (filter and sort are both handled by the same proxy instance).
- [ ] If `AtlasTableModel.refresh_data()` is ever refactored to emit `beginResetModel()` /
      `endResetModel()`, add sort-state restoration (see Issue 4).
- [ ] If `filterAcceptsRow` performance becomes a concern, introduce the cache pattern (Issue 3).
- [ ] If version-string sorting produces unexpected results, override `lessThan()` (Issue 6).
- [ ] Any new column added to `column_headers` in `AtlasTableModel` is automatically sortable;
      no changes needed in the view unless the column should be hidden.
