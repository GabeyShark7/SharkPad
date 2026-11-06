from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QColorDialog, QLabel, QFrame, QFileDialog, QMessageBox)
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QImage, QPainterPath, QKeySequence, QShortcut, QBitmap
from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal
import os

pad_size_width = 450
pad_size_height = 400

# Canvas paper color and default ink for each theme
LIGHT_BG = QColor("#ffffff")
DARK_BG = QColor("#1e1e1e")
LIGHT_INK = QColor(Qt.black)
DARK_INK = QColor(Qt.white)


def swap_default_ink(pixmap, to_dark):
    """
    Return a copy of a drawing layer with the default ink flipped:
    black -> white when going dark, white -> black when going light.
    Colored strokes are left alone. Works on premultiplied ARGB, so the
    antialiased edges of each stroke flip along with it.
    """
    import numpy as np

    img = pixmap.toImage().convertToFormat(QImage.Format_ARGB32_Premultiplied)
    w, h = img.width(), img.height()
    bpl = img.bytesPerLine()
    buf = np.frombuffer(img.constBits(), dtype=np.uint8, count=bpl * h).reshape(h, bpl)
    px = buf[:, : w * 4].reshape(h, w, 4).copy()  # BGRA byte order
    b, g, r, a = (px[..., i].astype(np.int16) for i in range(4))

    painted = a > 0
    if to_dark:
        # premultiplied black is (0, 0, 0, a)
        mask = painted & (r <= 8) & (g <= 8) & (b <= 8)
        px[..., 0][mask] = px[..., 3][mask]
        px[..., 1][mask] = px[..., 3][mask]
        px[..., 2][mask] = px[..., 3][mask]
    else:
        # premultiplied white is (a, a, a, a)
        mask = painted & (abs(r - a) <= 8) & (abs(g - a) <= 8) & (abs(b - a) <= 8)
        px[..., 0][mask] = 0
        px[..., 1][mask] = 0
        px[..., 2][mask] = 0

    out = QImage(px.tobytes(), w, h, w * 4, QImage.Format_ARGB32_Premultiplied).copy()
    return QPixmap.fromImage(out)

class ColorButton(QPushButton):
    """A button that displays a color"""
    def __init__(self, color, callback=None):
        super().__init__()
        self.color = QColor(color)  # Make a copy of the color
        self.setFixedSize(30, 30)
        self.update_color(self.color)
        if callback:
            self.clicked.connect(lambda: callback(self.color))
    
    def update_color(self, color):
        self.color = QColor(color)
        self.setStyleSheet(f"background-color: {color.name()}; border: 2px solid #555;")

class ImageObject:
    """Represents an image on the canvas"""
    def __init__(self, pixmap, x, y):
        self.pixmap = pixmap
        self.x = x
        self.y = y
        self.width = pixmap.width()
        self.height = pixmap.height()
        self.selected = False
    
    def get_rect(self):
        return QRect(self.x, self.y, self.width, self.height)
    
    def contains_point(self, point):
        return self.get_rect().contains(point)
    
    def move(self, dx, dy):
        self.x += dx
        self.y += dy
    
    def resize(self, new_width, new_height):
        self.width = max(20, new_width)
        self.height = max(20, new_height)

class DrawingCanvas(QLabel):
    """Canvas widget for drawing and managing images"""
    changed = Signal()
    MAX_UNDO = 50

    def __init__(self, width=pad_size_width, height=pad_size_height):
        super().__init__()
        self.setFixedSize(width, height)
        # Clicking the canvas focuses it, so Ctrl+Z undoes drawing instead of typing
        self.setFocusPolicy(Qt.ClickFocus)
        self.setAccessibleName("Drawing canvas")
        self.undo_stack = []
        self.redo_stack = []
        self._pending_snapshot = None
        self.modified = False
        self.canvas_width = width
        self.canvas_height = height
        
        self.drawing = False
        self.last_point = QPoint()
        self.dark = False
        self.background_color = QColor(LIGHT_BG)
        self.current_color = QColor(LIGHT_INK)
        self.pen_width = 3
        self.eraser_mode = False
        self.has_drawn = False
        
        # Mode: 'draw' or 'select'
        self.mode = 'draw'
        
        # Image management
        self.images = []  # List of ImageObject instances
        self.selected_image = None
        self.dragging_image = False
        self.resizing_image = False
        self.drag_start_pos = None
        self.resize_corner = None
        
        # Drawing layer (transparent with premultiplied alpha)
        self.drawing_layer = QPixmap(width, height)
        self.drawing_layer.fill(Qt.transparent)
        
        self.update_canvas()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            
            self._pending_snapshot = self._snapshot()

            if self.mode == 'select':
                # Select mode - interact with images
                clicked_image = None
                for img in reversed(self.images):  # Check from top to bottom
                    if img.contains_point(pos):
                        clicked_image = img
                        break
                
                # Deselect all images first
                for img in self.images:
                    img.selected = False
                
                if clicked_image:
                    clicked_image.selected = True
                    self.selected_image = clicked_image
                    
                    # Check if clicking on resize corner (bottom-right)
                    corner_rect = QRect(
                        clicked_image.x + clicked_image.width - 10,
                        clicked_image.y + clicked_image.height - 10,
                        10, 10
                    )
                    if corner_rect.contains(pos):
                        self.resizing_image = True
                        self.drag_start_pos = pos
                    else:
                        self.dragging_image = True
                        self.drag_start_pos = pos
                    
                    self.update_canvas()
                else:
                    self.selected_image = None
                    self.update_canvas()
            
            else:  # Draw mode
                # Always draw, ignore images
                self.drawing = True
                self.last_point = pos
    
    def mouseMoveEvent(self, event):
        pos = event.pos()
        
        if self.dragging_image and self.selected_image and self.drag_start_pos:
            # Move the image
            self._commit_pending()
            dx = pos.x() - self.drag_start_pos.x()
            dy = pos.y() - self.drag_start_pos.y()
            self.selected_image.move(dx, dy)
            self.drag_start_pos = pos
            self.update_canvas()
            self.has_drawn = True
        
        elif self.resizing_image and self.selected_image and self.drag_start_pos:
            # Resize the image
            self._commit_pending()
            dx = pos.x() - self.drag_start_pos.x()
            dy = pos.y() - self.drag_start_pos.y()
            new_width = self.selected_image.width + dx
            new_height = self.selected_image.height + dy
            self.selected_image.resize(new_width, new_height)
            self.drag_start_pos = pos
            self.update_canvas()
            self.has_drawn = True
        
        elif self.drawing and event.buttons() & Qt.LeftButton:
            # Draw on the drawing layer
            self._commit_pending()
            painter = QPainter(self.drawing_layer)
            if self.eraser_mode:
                painter.setCompositionMode(QPainter.CompositionMode_Clear)
                painter.setPen(QPen(Qt.transparent, 15, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            else:
                painter.setPen(QPen(self.current_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            
            painter.drawLine(self.last_point, pos)
            painter.end()
            self.last_point = pos
            self.update_canvas()
            self.has_drawn = True
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = False
            self.dragging_image = False
            self.resizing_image = False
            self.drag_start_pos = None
            self._pending_snapshot = None

    def _snapshot(self):
        images = [(i.pixmap, i.x, i.y, i.width, i.height) for i in self.images]
        return self.drawing_layer.copy(), images, self.dark

    def _push_undo(self, snapshot=None):
        self.undo_stack.append(snapshot or self._snapshot())
        if len(self.undo_stack) > self.MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def _commit_pending(self):
        """Save the state from before this mouse action, once it actually changes something."""
        if self._pending_snapshot is not None:
            self._push_undo(self._pending_snapshot)
            self._pending_snapshot = None
            self._mark_changed()

    def _mark_changed(self):
        self.modified = True
        self.changed.emit()

    def _restore(self, snapshot):
        layer, images, dark = snapshot
        if dark != self.dark:
            layer = swap_default_ink(layer, to_dark=self.dark)
        self.drawing_layer = layer.copy()
        self.images = []
        for pixmap, x, y, w, h in images:
            obj = ImageObject(pixmap, x, y)
            obj.width, obj.height = w, h
            self.images.append(obj)
        self.selected_image = None
        self.has_drawn = True
        self.update_canvas()
        self._mark_changed()

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self._snapshot())
        self._restore(self.undo_stack.pop())
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self._snapshot())
        self._restore(self.redo_stack.pop())
        return True

    def reset_history(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.modified = False
        self.changed.emit()

    def load_image(self, filepath):
        """Load a saved drawing (white paper becomes transparent again)."""
        img = QImage(filepath)
        if img.isNull():
            return False
        pixmap = QPixmap.fromImage(img.convertToFormat(QImage.Format_ARGB32))
        pixmap.setMask(QBitmap.fromImage(img.createMaskFromColor(QColor(Qt.white).rgb(), Qt.MaskOutColor)))
        layer = QPixmap(self.canvas_width, self.canvas_height)
        layer.fill(Qt.transparent)
        painter = QPainter(layer)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        self.images.clear()
        self.selected_image = None
        self.drawing_layer = swap_default_ink(layer, to_dark=True) if self.dark else layer
        self.has_drawn = True
        self.update_canvas()
        return True
    
    def set_dark(self, dark):
        """Switch the canvas between light and dark paper."""
        if dark == self.dark:
            return
        old_ink = DARK_INK if self.dark else LIGHT_INK
        self.dark = dark
        self.background_color = QColor(DARK_BG if dark else LIGHT_BG)

        # Keep existing default-ink strokes visible on the new background
        self.drawing_layer = swap_default_ink(self.drawing_layer, to_dark=dark)

        # If the pen is still on the default ink, switch it too
        if not self.eraser_mode and self.current_color.rgb() == old_ink.rgb():
            self.current_color = QColor(DARK_INK if dark else LIGHT_INK)

        self.update_canvas()

    def update_canvas(self):
        """Redraw the entire canvas with images and drawing layer"""
        final_pixmap = QPixmap(self.canvas_width, self.canvas_height)
        final_pixmap.fill(self.background_color)
        
        painter = QPainter(final_pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        corner_size = 10
        
        # Draw all images with proper transparency
        for img in self.images:
            # Scale maintaining aspect ratio and transparency
            scaled_pixmap = img.pixmap.scaled(
                img.width, img.height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            # Draw image (transparency is automatically handled)
            painter.drawPixmap(img.x, img.y, scaled_pixmap)
            
            # Draw selection rectangle
            if img.selected:
                painter.setPen(QPen(QColor("#d32f2f"), 2, Qt.DashLine))
                painter.drawRect(img.get_rect())
                
                # Draw resize handle (bottom-right corner)
                painter.setBrush(QColor("#d32f2f"))
                painter.setPen(Qt.NoPen)
                painter.drawRect(
                    img.x + img.width - corner_size,
                    img.y + img.height - corner_size,
                    corner_size, corner_size
                )
        
        # Draw the drawing layer on top
        painter.drawPixmap(0, 0, self.drawing_layer)
        painter.end()
        
        self.setPixmap(final_pixmap)
    
    def add_image(self, filepath):
        """Add an image to the canvas with full transparency support"""
        # Load image file
        pixmap = QPixmap(filepath)
        if pixmap.isNull():
            return False
        
        # Check if image has alpha channel and preserve it
        if pixmap.hasAlpha():
            # Image has transparency - convert to format that preserves it
            img = pixmap.toImage()
            img = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
            pixmap = QPixmap.fromImage(img)
        
        # Scale down if too large (preserve aspect ratio and transparency)
        max_size = 200
        if pixmap.width() > max_size or pixmap.height() > max_size:
            pixmap = pixmap.scaled(
                max_size, max_size, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
        
        # Place in center
        x = (self.canvas_width - pixmap.width()) // 2
        y = (self.canvas_height - pixmap.height()) // 2
        
        self._push_undo()
        img_obj = ImageObject(pixmap, x, y)
        self.images.append(img_obj)
        self._mark_changed()
        self.update_canvas()
        self.has_drawn = True
        return True
    
    def delete_selected_image(self):
        """Delete the currently selected image"""
        if self.selected_image and self.selected_image in self.images:
            self._push_undo()
            self.images.remove(self.selected_image)
            self.selected_image = None
            self.update_canvas()
            self._mark_changed()
            return True
        return False
    
    def bring_to_front(self):
        """Bring selected image to front (top layer)"""
        if self.selected_image and self.selected_image in self.images:
            self._push_undo()
            self._mark_changed()
            self.images.remove(self.selected_image)
            self.images.append(self.selected_image)  # Add to end = top layer
            self.update_canvas()
            return True
        return False
    
    def send_to_back(self):
        """Send selected image to back (bottom layer)"""
        if self.selected_image and self.selected_image in self.images:
            self._push_undo()
            self._mark_changed()
            self.images.remove(self.selected_image)
            self.images.insert(0, self.selected_image)  # Add to start = bottom layer
            self.update_canvas()
            return True
        return False
    
    def bring_forward(self):
        """Bring selected image one layer forward"""
        if self.selected_image and self.selected_image in self.images:
            index = self.images.index(self.selected_image)
            if index < len(self.images) - 1:  # Not already at top
                self._push_undo()
                self._mark_changed()
                self.images[index], self.images[index + 1] = self.images[index + 1], self.images[index]
                self.update_canvas()
                return True
        return False
    
    def send_backward(self):
        """Send selected image one layer backward"""
        if self.selected_image and self.selected_image in self.images:
            index = self.images.index(self.selected_image)
            if index > 0:  # Not already at bottom
                self._push_undo()
                self._mark_changed()
                self.images[index], self.images[index - 1] = self.images[index - 1], self.images[index]
                self.update_canvas()
                return True
        return False
    
    def set_color(self, color):
        self.current_color = color
        self.eraser_mode = False
    
    def set_eraser(self):
        self.eraser_mode = True
    
    def set_mode(self, mode):
        """Set mode to 'draw' or 'select'"""
        self.mode = mode
        if mode == 'draw':
            # Deselect all images when switching to draw mode
            for img in self.images:
                img.selected = False
            self.selected_image = None
            self.update_canvas()
    
    def clear_canvas(self, undoable=False):
        """Clear everything. Only "Clear All" is undoable; starting a new or
        opened note also forgets the old drawing's undo history."""
        if undoable:
            self._push_undo()
        self.images.clear()
        self.selected_image = None
        self.drawing_layer.fill(Qt.transparent)
        self.update_canvas()
        self.has_drawn = False
        if undoable:
            self._mark_changed()
        else:
            self.reset_history()
    
    def save_image(self, filepath):
        """Save the entire canvas as an image with transparency preserved"""
        final_pixmap = QPixmap(self.canvas_width, self.canvas_height)
        final_pixmap.fill(Qt.white)
        
        painter = QPainter(final_pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        # Draw all images without selection indicators (transparency preserved)
        for img in self.images:
            scaled_pixmap = img.pixmap.scaled(
                img.width, img.height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            painter.drawPixmap(img.x, img.y, scaled_pixmap)
        
        # Draw the drawing layer. Always export as black ink on white paper,
        # so saved drawings look the same no matter which theme was active.
        layer = swap_default_ink(self.drawing_layer, to_dark=False) if self.dark else self.drawing_layer
        painter.drawPixmap(0, 0, layer)
        painter.end()
        
        return final_pixmap.save(filepath, "PNG")

class DrawingPad(QWidget):
    """Drawing pad widget with color picker and tools"""
    def __init__(self):
        super().__init__()
        self.recent_colors = []
        self.max_recent_colors = 5
        self.draw_mode_btn = None
        self.select_mode_btn = None
        self.init_ui()
        # Shortcuts are now set up in main.py at window level
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        title = QLabel("Drawing Pad")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Canvas
        self.canvas = DrawingCanvas()
        layout.addWidget(self.canvas)
        
        # Mode selection
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet("font-size: 11px; margin-top: 5px; font-weight: bold;")
        layout.addWidget(mode_label)
        
        mode_layout = QHBoxLayout()
        self.draw_mode_btn = QPushButton("Draw\n(Ctrl+Shift+D)")
        self.draw_mode_btn.setCheckable(True)
        self.draw_mode_btn.setChecked(True)
        self.draw_mode_btn.clicked.connect(lambda: self.set_mode('draw'))
        self.draw_mode_btn.setStyleSheet("QPushButton:checked { background-color: #d32f2f; color: white; font-weight: bold; }")
        mode_layout.addWidget(self.draw_mode_btn)
        
        self.select_mode_btn = QPushButton("Select\n(Ctrl+Shift+A)")
        self.select_mode_btn.setCheckable(True)
        self.select_mode_btn.clicked.connect(lambda: self.set_mode('select'))
        self.select_mode_btn.setStyleSheet("QPushButton:checked { background-color: #d32f2f; color: white; font-weight: bold; }")
        mode_layout.addWidget(self.select_mode_btn)
        layout.addLayout(mode_layout)
        
        # Upload Image button
        upload_btn = QPushButton("Upload Image\n(Ctrl+Shift+U)")
        upload_btn.clicked.connect(self.upload_image)
        layout.addWidget(upload_btn)
        
        # Color picker button
        color_btn = QPushButton("Pick Color\n(Ctrl+Shift+C)")
        color_btn.clicked.connect(self.pick_color)
        layout.addWidget(color_btn)
        
        # Recent colors label
        recent_label = QLabel("Recent Colors:")
        recent_label.setStyleSheet("font-size: 11px; margin-top: 5px;")
        layout.addWidget(recent_label)
        
        # Recent colors container
        self.recent_colors_layout = QHBoxLayout()
        self.recent_colors_layout.setSpacing(5)
        layout.addLayout(self.recent_colors_layout)
        
        # Tools
        tools_layout = QHBoxLayout()
        
        eraser_btn = QPushButton("Eraser\n(Ctrl+Shift+E)")
        eraser_btn.clicked.connect(self.canvas.set_eraser)
        tools_layout.addWidget(eraser_btn)
        
        clear_btn = QPushButton("Clear All")
        clear_btn.setToolTip("Clear the drawing pad (Ctrl+Z brings it back)")
        clear_btn.clicked.connect(self.clear_all)
        tools_layout.addWidget(clear_btn)
        
        layout.addLayout(tools_layout)
        
        # Layer controls
        layer_label = QLabel("Layer Controls:")
        layer_label.setStyleSheet("font-size: 11px; margin-top: 5px; font-weight: bold;")
        layout.addWidget(layer_label)
        
        layer_layout1 = QHBoxLayout()
        bring_front_btn = QPushButton("To Front\n(Ctrl+Shift+])")
        bring_front_btn.clicked.connect(self.bring_to_front)
        layer_layout1.addWidget(bring_front_btn)
        
        send_back_btn = QPushButton("To Back\n(Ctrl+Shift+[)")
        send_back_btn.clicked.connect(self.send_to_back)
        layer_layout1.addWidget(send_back_btn)
        layout.addLayout(layer_layout1)
        
        layer_layout2 = QHBoxLayout()
        forward_btn = QPushButton("Forward\n(Ctrl+])")
        forward_btn.clicked.connect(self.bring_forward)
        layer_layout2.addWidget(forward_btn)
        
        backward_btn = QPushButton("Backward\n(Ctrl+[)")
        backward_btn.clicked.connect(self.send_backward)
        layer_layout2.addWidget(backward_btn)
        layout.addLayout(layer_layout2)
        
        # Delete image button
        delete_img_btn = QPushButton("Delete Image\n(Ctrl+Shift+Del)")
        delete_img_btn.clicked.connect(self.delete_image)
        layout.addWidget(delete_img_btn)
        
        layout.addStretch()
    
    def upload_image(self):
        """Upload an image to the canvas"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Upload Image", "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )
        if filepath:
            if self.canvas.add_image(filepath):
                QMessageBox.information(self, "Success", "Image uploaded! Click Select mode to move/resize.")
            else:
                QMessageBox.warning(self, "Error", "Could not load image.")
    
    def delete_image(self):
        """Delete the selected image"""
        if self.canvas.delete_selected_image():
            pass  # Silent deletion
        else:
            QMessageBox.information(self, "No Selection", "No image selected. Switch to Select mode and click an image first.")
    
    def clear_all(self):
        """Clear everything with confirmation"""
        reply = QMessageBox.question(
            self, "Clear All",
            "Clear all images and drawings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.canvas.clear_canvas(undoable=True)
    
    def pick_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.canvas.set_color(color)
            self.add_recent_color(color)
    
    def add_recent_color(self, color):
        # Remove if color already exists
        self.recent_colors = [c for c in self.recent_colors if c.name() != color.name()]
        
        # Add to front
        self.recent_colors.insert(0, color)
        
        # Keep only last 5
        if len(self.recent_colors) > self.max_recent_colors:
            self.recent_colors.pop()
        
        # Update UI
        self.update_recent_colors_ui()
    
    def update_recent_colors_ui(self):
        # Clear existing buttons
        while self.recent_colors_layout.count():
            item = self.recent_colors_layout.takeAt(0)
            if item.widget():
                # Hide first so the old swatch doesn't linger on screen
                # until Qt gets around to deleting it
                item.widget().hide()
                item.widget().deleteLater()
        
        # Add color buttons with callback
        for color in self.recent_colors:
            btn = ColorButton(color, self.select_recent_color)
            self.recent_colors_layout.addWidget(btn)
    
    def select_recent_color(self, color):
        """Select a color from recent colors"""
        self.canvas.set_color(color)
    
    def bring_to_front(self):
        """Bring selected image to front"""
        self.canvas.bring_to_front()
    
    def send_to_back(self):
        """Send selected image to back"""
        self.canvas.send_to_back()
    
    def bring_forward(self):
        """Bring selected image one layer forward"""
        self.canvas.bring_forward()
    
    def send_backward(self):
        """Send selected image one layer backward"""
        self.canvas.send_backward()
    
    def set_mode(self, mode):
        """Switch between draw and select mode"""
        self.canvas.set_mode(mode)
        if mode == 'draw':
            self.draw_mode_btn.setChecked(True)
            self.select_mode_btn.setChecked(False)
        else:
            self.draw_mode_btn.setChecked(False)
            self.select_mode_btn.setChecked(True)
    
    def has_drawing(self):
        """Check if anything has been drawn"""
        return self.canvas.has_drawn
    
    def save_drawing(self, filepath):
        """Save the drawing to a file"""
        ok = self.canvas.save_image(filepath)
        if ok:
            self.canvas.modified = False
            self.canvas.changed.emit()
        return ok

    def load_drawing(self, filepath):
        """Load a drawing saved next to a note"""
        ok = self.canvas.load_image(filepath)
        self.canvas.reset_history()
        return ok

def create_drawing_pad():
    """Factory function to create a drawing pad"""
    return DrawingPad()