from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from tracer.models.preview_result import PreviewResult


class PreviewGraphicsView(QGraphicsView):
    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._placeholder_text = self._scene.addText(placeholder)
        self._fit_enabled = True

        self.setScene(self._scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def set_pixmap(self, pixmap: QPixmap | None, placeholder: str | None = None) -> None:
        if pixmap is None or pixmap.isNull():
            self._pixmap_item.setPixmap(QPixmap())
            self._placeholder_text.setPlainText(placeholder or self._placeholder_text.toPlainText())
            self._placeholder_text.setVisible(True)
            self._fit_enabled = True
            self.fit_in_view()
            return

        self._pixmap_item.setPixmap(pixmap)
        self._placeholder_text.setVisible(False)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        if self._fit_enabled:
            self.fit_in_view()

    def zoom_in(self) -> None:
        self._fit_enabled = False
        self.scale(1.2, 1.2)

    def zoom_out(self) -> None:
        self._fit_enabled = False
        self.scale(1 / 1.2, 1 / 1.2)

    def reset_zoom(self) -> None:
        self._fit_enabled = False
        self.resetTransform()

    def fit_in_view(self) -> None:
        self._fit_enabled = True
        self.resetTransform()
        if not self._pixmap_item.pixmap().isNull():
            super().fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._fit_enabled:
            self.fit_in_view()


class PreviewPanel(QWidget):
    export_requested = Signal()
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.original_compare_view = PreviewGraphicsView("Original preview")
        self.mask_compare_view = PreviewGraphicsView("Processed mask preview")
        self.svg_compare_view = PreviewGraphicsView("Traced SVG preview")
        self.original_before_view = PreviewGraphicsView("Original preview")
        self.svg_before_view = PreviewGraphicsView("Traced SVG preview")

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Compare")
        self.mode_combo.addItem("Before / After")

        self.zoom_in_button = QPushButton("Zoom +")
        self.zoom_out_button = QPushButton("Zoom -")
        self.actual_size_button = QPushButton("100%")
        self.fit_button = QPushButton("Fit")
        self.refresh_button = QPushButton("Refresh")
        self.export_button = QPushButton("Export Preview SVG")
        self.export_button.setEnabled(False)

        self.status_label = QLabel("Select a file to generate a preview.")
        self.meta_label = QLabel("Preview: -")
        self.meta_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        self.meta_label.setWordWrap(True)
        self.middle_card_title = QLabel("Mask")
        self.middle_card_title.setObjectName("sectionTitle")

        self._stack = QStackedWidget()
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        compare_split = QSplitter(Qt.Orientation.Horizontal)
        compare_split.addWidget(self._build_card("Original", self.original_compare_view))
        compare_split.addWidget(self._build_card(self.middle_card_title, self.mask_compare_view))
        compare_split.addWidget(self._build_card("SVG", self.svg_compare_view))
        compare_split.setStretchFactor(0, 1)
        compare_split.setStretchFactor(1, 1)
        compare_split.setStretchFactor(2, 1)

        before_after_split = QSplitter(Qt.Orientation.Horizontal)
        before_after_split.addWidget(self._build_card("Before", self.original_before_view))
        before_after_split.addWidget(self._build_card("After", self.svg_before_view))
        before_after_split.setStretchFactor(0, 1)
        before_after_split.setStretchFactor(1, 1)

        self._stack.addWidget(compare_split)
        self._stack.addWidget(before_after_split)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Mode"))
        toolbar.addWidget(self.mode_combo)
        toolbar.addSpacing(12)
        toolbar.addWidget(self.zoom_in_button)
        toolbar.addWidget(self.zoom_out_button)
        toolbar.addWidget(self.actual_size_button)
        toolbar.addWidget(self.fit_button)
        toolbar.addWidget(self.refresh_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.export_button)

        footer = QHBoxLayout()
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.meta_label)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self._stack, 1)
        layout.addLayout(footer)

    def _connect_signals(self) -> None:
        self.mode_combo.currentIndexChanged.connect(self._stack.setCurrentIndex)
        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self.actual_size_button.clicked.connect(self.reset_zoom)
        self.fit_button.clicked.connect(self.fit_to_window)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.export_button.clicked.connect(self.export_requested.emit)

    def _build_card(self, title: str | QLabel, view: QWidget) -> QWidget:
        frame = QFrame()
        frame.setObjectName("previewCard")

        title_label = title if isinstance(title, QLabel) else QLabel(title)
        if title_label.objectName() == "":
            title_label.setObjectName("sectionTitle")

        layout = QVBoxLayout(frame)
        layout.addWidget(title_label)
        layout.addWidget(view, 1)
        return frame

    def set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)
        if busy:
            self.status_label.setText("Refreshing preview...")

    def set_source_image(self, image_path: Path | None) -> None:
        if image_path is None or not image_path.exists():
            self.original_compare_view.set_pixmap(None, "Original preview")
            self.original_before_view.set_pixmap(None, "Original preview")
            self.clear_generated_previews()
            self.meta_label.setText("Preview: -")
            return

        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self.original_compare_view.set_pixmap(None, "Could not load image")
            self.original_before_view.set_pixmap(None, "Could not load image")
            self.clear_generated_previews()
            self.meta_label.setText(f"Preview: {image_path.name}")
            return

        self.original_compare_view.set_pixmap(pixmap)
        self.original_before_view.set_pixmap(pixmap)
        self.meta_label.setText(f"Preview: {image_path.name} | {pixmap.width()} x {pixmap.height()}")

    def set_preview_result(self, result: PreviewResult) -> None:
        self.set_busy(False)
        if not result.source_loaded and not result.mask_available and not result.svg_available and not result.error:
            self.clear_generated_previews()
            self.status_label.setText("Select a file to generate a preview.")
            self.export_button.setEnabled(False)
            return

        if result.error:
            self.mask_compare_view.set_pixmap(None, "Processed mask preview")
            self.svg_compare_view.set_pixmap(None, "Traced SVG preview")
            self.svg_before_view.set_pixmap(None, "Traced SVG preview")
            self.middle_card_title.setText("Mask")
            self.status_label.setText(result.error)
            self.export_button.setEnabled(False)
            return

        self.middle_card_title.setText(result.processing_label)
        mask_pixmap = self._pixmap_from_bytes(result.mask_png_bytes)
        svg_pixmap = self._pixmap_from_svg(result.svg_text, result.width, result.height)

        self.mask_compare_view.set_pixmap(mask_pixmap, "Processed mask preview")
        self.svg_compare_view.set_pixmap(svg_pixmap, "Traced SVG preview")
        self.svg_before_view.set_pixmap(svg_pixmap, "Traced SVG preview")

        self.status_label.setText(result.warning or "Preview ready")
        self.export_button.setEnabled(result.svg_available)

    def clear_generated_previews(self) -> None:
        self.middle_card_title.setText("Mask")
        self.mask_compare_view.set_pixmap(None, "Processed mask preview")
        self.svg_compare_view.set_pixmap(None, "Traced SVG preview")
        self.svg_before_view.set_pixmap(None, "Traced SVG preview")

    def zoom_in(self) -> None:
        for view in self._all_views():
            view.zoom_in()

    def zoom_out(self) -> None:
        for view in self._all_views():
            view.zoom_out()

    def reset_zoom(self) -> None:
        for view in self._all_views():
            view.reset_zoom()

    def fit_to_window(self) -> None:
        for view in self._all_views():
            view.fit_in_view()

    def _all_views(self) -> list[PreviewGraphicsView]:
        return [
            self.original_compare_view,
            self.mask_compare_view,
            self.svg_compare_view,
            self.original_before_view,
            self.svg_before_view,
        ]

    def _pixmap_from_bytes(self, payload: bytes) -> QPixmap | None:
        if not payload:
            return None
        pixmap = QPixmap()
        if pixmap.loadFromData(payload, "PNG"):
            return pixmap
        return None

    def _pixmap_from_svg(self, svg_text: str, width: int, height: int) -> QPixmap | None:
        if not svg_text:
            return None

        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
        if not renderer.isValid():
            return None

        render_width = max(width, 1)
        render_height = max(height, 1)
        image = QImage(render_width, render_height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(image)
        renderer.render(painter)
        painter.end()

        return QPixmap.fromImage(image)
