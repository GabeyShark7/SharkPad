from PySide6.QtGui import QColor, QTextCharFormat, QTextFormat
from PySide6.QtWidgets import QTextEdit

LAYER_ORDER = ["line", "instruct", "qa", "find", "speech", "spell", "autocorrect"]
READING_GUIDE_COLOR = QColor(255, 193, 7, 70)


def set_selection_layer(editor, name, selections):
    layers = getattr(editor, "_selection_layers", None)
    if layers is None:
        layers = {}
        editor._selection_layers = layers
    layers[name] = list(selections)
    combined = []
    for key in LAYER_ORDER:
        combined.extend(layers.get(key, []))
    editor.setExtraSelections(combined)


def make_selection(cursor, fmt):
    sel = QTextEdit.ExtraSelection()
    sel.cursor = cursor
    sel.format = fmt
    return sel


def update_reading_guide(editor, enabled):
    """Tint the line the cursor is on, like a reading ruler."""
    if not enabled:
        set_selection_layer(editor, "line", [])
        return
    fmt = QTextCharFormat()
    fmt.setBackground(READING_GUIDE_COLOR)
    fmt.setProperty(QTextFormat.FullWidthSelection, True)
    c = editor.textCursor()
    c.clearSelection()
    set_selection_layer(editor, "line", [make_selection(c, fmt)])
