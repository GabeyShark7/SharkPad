from PySide6.QtWidgets import QFileDialog, QMessageBox
import os

def new_file(editor, parent, current_file, drawing_pad=None):
    """Clear the editor to start a new file, prompting to save if needed."""
    if editor.document().isModified() or (drawing_pad and drawing_pad.has_drawing()):
        reply = QMessageBox.question(
            parent,
            "Unsaved Changes",
            "Do you want to save changes to the current file?",
            QMessageBox.StandardButton.Save | 
            QMessageBox.StandardButton.Discard | 
            QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Save:
            current_file = save_file(editor, parent, current_file, drawing_pad)
        elif reply == QMessageBox.StandardButton.Cancel:
            return current_file  # Do nothing
    
    # If Discard, we just continue
    editor.clear()
    if drawing_pad:
        drawing_pad.canvas.clear_canvas()
    return None  # No current file after starting new

def open_file(editor, parent, current_file, drawing_pad=None):
    """Open a file dialog and load file content into the editor."""
    if editor.document().isModified() or (drawing_pad and drawing_pad.has_drawing()):
        reply = QMessageBox.question(
            parent,
            "Unsaved Changes",
            "Do you want to save changes to the current file?",
            QMessageBox.StandardButton.Save | 
            QMessageBox.StandardButton.Discard | 
            QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Save:
            current_file = save_file(editor, parent, current_file, drawing_pad)
        elif reply == QMessageBox.StandardButton.Cancel:
            return current_file  # Cancel opening
    
    file_path, _ = QFileDialog.getOpenFileName(parent, "Open File", "", "Text Files (*.txt);;All Files (*)")
    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            editor.setPlainText(f.read())
        
        # Clear drawing when opening a new text file
        if drawing_pad:
            drawing_pad.canvas.clear_canvas()
        
        return file_path
    return current_file

def save_file(editor, parent, current_file=None, drawing_pad=None):
    """Save text and drawing together in a user-named folder."""
    has_drawing = drawing_pad and drawing_pad.has_drawing()

    # Always ask for folder if no current file yet
    if not current_file:
        folder_path = QFileDialog.getExistingDirectory(parent, "Select or Create Folder to Save Project")
        if not folder_path:
            return None  # User canceled

        # Ask for project/file name
        project_name, ok = QFileDialog.getSaveFileName(
            parent,
            "Name Your File",
            folder_path,
            "Text Files (*.txt)"
        )
        if not project_name:
            return None  # User canceled

        # Ensure .txt extension
        if not project_name.endswith(".txt"):
            project_name += ".txt"

        current_file = project_name

    # Save text file
    with open(current_file, "w", encoding="utf-8") as f:
        f.write(editor.toPlainText())
    editor.document().setModified(False)

    # Save drawing if present
    if has_drawing:
        folder = os.path.dirname(current_file)
        base_name = os.path.splitext(os.path.basename(current_file))[0]
        drawing_path = os.path.join(folder, f"{base_name}_drawing.png")
        drawing_pad.save_drawing(drawing_path)

    QMessageBox.information(
        parent,
        "Saved",
        f"Saved:\n{os.path.basename(current_file)}" +
        (f"\n{os.path.basename(drawing_path)}" if has_drawing else "")
    )

    return current_file
