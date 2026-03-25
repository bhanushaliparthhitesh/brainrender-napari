import pytest
from qtpy.QtCore import QModelIndex, Qt

from brainrender_napari.utils.formatting import format_atlas_name
from brainrender_napari.widgets.atlas_viewer_view import (
    AtlasViewerView,
)


@pytest.fixture
def atlas_viewer_view(qtbot) -> AtlasViewerView:
    """Fixture to provide a valid atlas table view.

    Depends on qtbot fixture to provide the qt event loop.
    """
    return AtlasViewerView()


@pytest.mark.parametrize(
    "row, expected_atlas_name",
    [
        (0, "example_mouse_100um"),
        (1, "allen_mouse_100um"),
    ],
)
def test_atlas_view_valid_selection(
    row, expected_atlas_name, atlas_viewer_view
):
    """Checks selected_atlas_name for valid current indices"""
    model_index = atlas_viewer_view.model().index(row, 0)
    atlas_viewer_view.setCurrentIndex(model_index)
    assert atlas_viewer_view.selected_atlas_name() == expected_atlas_name


def test_atlas_view_invalid_selection(atlas_viewer_view):
    """Checks that selected_atlas_name throws an assertion error
    if current index is invalid."""
    with pytest.raises(AssertionError):
        atlas_viewer_view.setCurrentIndex(QModelIndex())
        atlas_viewer_view.selected_atlas_name()


def test_atlas_viewer_view_only_shows_downloaded_atlases(atlas_viewer_view):
    """Checks that the atlas viewer view only shows locally downloaded atlases.
    Non-downloaded atlases are filtered out by the proxy model.
    """
    from brainglobe_atlasapi.list_atlases import get_downloaded_atlases

    downloaded = get_downloaded_atlases()
    for row in range(atlas_viewer_view.model().rowCount()):
        index = atlas_viewer_view.model().index(row, 0)
        atlas_name = atlas_viewer_view.model().data(index)
        assert atlas_name in downloaded


def test_hover_atlas_viewer_view(atlas_viewer_view, mocker):
    """Check tooltip is called when hovering over view"""
    index = atlas_viewer_view.model().index(2, 1)

    get_tooltip_text_mock = mocker.patch(
        "brainrender_napari.widgets"
        ".atlas_viewer_view.AtlasViewerView.get_tooltip_text"
    )

    atlas_viewer_view.model().data(index, Qt.ToolTipRole)

    get_tooltip_text_mock.assert_called_once()


@pytest.mark.parametrize(
    "row,expected_atlas_name",
    [
        (0, "example_mouse_100um"),
        (1, "allen_mouse_100um"),
        (2, "osten_mouse_100um"),
    ],
)
def test_double_click_on_locally_available_atlas_row(
    atlas_viewer_view, double_click_on_view, qtbot, row, expected_atlas_name
):
    """Check for a few locally available low-res atlases that double-clicking
    them on the atlas table view emits a signal with their expected names.
    """
    model_index = atlas_viewer_view.model().index(row, 1)
    atlas_viewer_view.setCurrentIndex(model_index)

    with qtbot.waitSignal(
        atlas_viewer_view.add_atlas_requested
    ) as add_atlas_requested_signal:
        double_click_on_view(atlas_viewer_view, model_index)

    assert add_atlas_requested_signal.args == [expected_atlas_name]


def test_additional_reference_menu(atlas_viewer_view, qtbot, mocker):
    """Checks callback to additional reference menu calls QMenu exec
    and emits expected signal"""
    atlas_viewer_view.selectRow(
        0
    )  # example atlas + mock additional reference is in row 0
    from qtpy.QtCore import QPoint
    from qtpy.QtWidgets import QAction

    x = atlas_viewer_view.rowViewportPosition(0)
    y = atlas_viewer_view.columnViewportPosition(1)
    position = QPoint(x, y)
    qmenu_exec_mock = mocker.patch(
        "brainrender_napari.widgets.atlas_viewer_view.QMenu.exec"
    )
    qmenu_exec_mock.return_value = QAction("reference")

    with qtbot.waitSignal(
        atlas_viewer_view.additional_reference_requested
    ) as additional_reference_requested_signal:
        atlas_viewer_view.customContextMenuRequested.emit(position)

    qmenu_exec_mock.assert_called_once()
    assert additional_reference_requested_signal.args == ["reference"]


def test_get_tooltip():
    """Check tooltip on an example in the downloaded test data"""
    tooltip_text = AtlasViewerView.get_tooltip_text("example_mouse_100um")
    assert format_atlas_name("example_mouse_100um") in tooltip_text
    assert "add to viewer" in tooltip_text


def test_get_tooltip_invalid_name():
    """Check tooltip on non-existent test data"""
    with pytest.raises(ValueError) as e:
        _ = AtlasViewerView.get_tooltip_text("wrong_atlas_name")
        assert "invalid atlas name" in e


def test_sorting_enabled_viewer_view(atlas_viewer_view):
    """Check that column-header sorting is enabled on the atlas viewer view."""
    assert atlas_viewer_view.isSortingEnabled()


def test_sort_atlas_viewer_view(atlas_viewer_view):
    """Check that sorting by Atlas column changes the row order."""
    atlas_col = atlas_viewer_view.source_model.column_headers.index("Atlas")

    atlas_viewer_view.sortByColumn(atlas_col, Qt.AscendingOrder)
    names_asc = [
        atlas_viewer_view.model().data(
            atlas_viewer_view.model().index(row, atlas_col)
        )
        for row in range(atlas_viewer_view.model().rowCount())
    ]

    atlas_viewer_view.sortByColumn(atlas_col, Qt.DescendingOrder)
    names_desc = [
        atlas_viewer_view.model().data(
            atlas_viewer_view.model().index(row, atlas_col)
        )
        for row in range(atlas_viewer_view.model().rowCount())
    ]

    assert names_asc == sorted(names_asc)
    assert names_asc == list(reversed(names_desc))
