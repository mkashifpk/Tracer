from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QTimer, Qt, QThread
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from tracer.models.batch_job import BatchJob, BatchProgress, BatchSummary
from tracer.models.file_item import FileItem
from tracer.models.preview_result import PreviewResult
from tracer.models.trace_settings import TraceSettings
from tracer.models.window_settings import WindowSettings
from tracer.services.batch_processing_manager import BatchProcessingManager
from tracer.services.config_manager import ConfigManager
from tracer.services.file_scanner import FileScanner
from tracer.services.preset_manager import PresetManager
from tracer.services.preview_service import PreviewService
from tracer.ui.batch_worker import BatchWorker
from tracer.ui.log_panel import LogPanel
from tracer.ui.preview_panel import PreviewPanel
from tracer.ui.preview_worker import PreviewWorker
from tracer.ui.settings_panel import SettingsPanel


class MainWindow(QMainWindow):
    def __init__(self, config_manager: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.app_settings, self.trace_settings, self.window_settings = self.config_manager.load()

        self.file_scanner = FileScanner()
        self.preview_service = PreviewService()
        self.batch_manager = BatchProcessingManager()
        self.preset_manager = PresetManager()
        self.preset_manager.load_custom_presets()

        self.scanned_files: list[FileItem] = []
        self.file_items_by_path: dict[str, QTreeWidgetItem] = {}
        self.current_preview_path: Path | None = None
        self.current_preview_result: PreviewResult | None = None
        self.batch_thread: QThread | None = None
        self.batch_worker: BatchWorker | None = None
        self.preview_thread: QThread | None = None
        self.preview_worker: PreviewWorker | None = None
        self._preview_pending = False

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._queue_preview_refresh)

        self.input_label = QLabel("Input folder: Not selected")
        self.output_label = QLabel("Output folder: Not selected")
        self.backend_label = QLabel()
        self.current_file_label = QLabel("Current file: -")
        self.input_label.setWordWrap(True)
        self.output_label.setWordWrap(True)
        self.current_file_label.setWordWrap(True)
        self.file_tree = QTreeWidget()
        self.file_tree.setColumnCount(5)
        self.file_tree.setHeaderLabels(["File", "Type", "Size", "Alpha", "Status"])
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setUniformRowHeights(True)

        self.preview_panel = PreviewPanel()
        self.settings_panel = SettingsPanel(
            settings=self.trace_settings,
            existing_output_mode=self.app_settings.existing_output_mode,
        )
        self.log_panel = LogPanel()
        self.settings_scroll = QScrollArea()
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.settings_scroll.setWidget(self.settings_panel)

        self.select_input_button = QPushButton("Input Folder")
        self.select_output_button = QPushButton("Output Folder")
        self.start_batch_button = QPushButton("Start Batch")
        self.cancel_batch_button = QPushButton("Stop Batch")
        self.cancel_batch_button.setEnabled(False)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.export_log_combo = QComboBox()
        self.export_log_combo.addItem("No log export", userData="none")
        self.export_log_combo.addItem("TXT log", userData="txt")
        self.export_log_combo.addItem("CSV log", userData="csv")

        self.setWindowTitle("Tracer - Turn bitmap images into SVGs")
        self.resize(1460, 900)
        self._build_ui()
        self._connect_signals()
        self._apply_loaded_settings()

    def _build_ui(self) -> None:
        folder_group = QGroupBox("Folders")
        folder_layout = QVBoxLayout(folder_group)
        folder_layout.addWidget(self.backend_label)
        folder_layout.addWidget(self.input_label)
        folder_layout.addWidget(self.output_label)

        folder_buttons = QHBoxLayout()
        folder_buttons.addWidget(self.select_input_button)
        folder_buttons.addWidget(self.select_output_button)
        folder_layout.addLayout(folder_buttons)

        batch_group = QGroupBox("Batch")
        batch_form = QFormLayout(batch_group)
        batch_form.addRow("Export log", self.export_log_combo)
        batch_form.addRow("Current file", self.current_file_label)
        batch_form.addRow("Progress", self.progress_bar)

        batch_buttons = QHBoxLayout()
        batch_buttons.addWidget(self.start_batch_button)
        batch_buttons.addWidget(self.cancel_batch_button)
        batch_form.addRow(batch_buttons)

        files_group = QGroupBox("Files")
        files_layout = QVBoxLayout(files_group)
        files_layout.addWidget(self.file_tree)

        logs_group = QGroupBox("Log")
        logs_layout = QVBoxLayout(logs_group)
        logs_layout.addWidget(self.log_panel)

        left_top = QWidget()
        left_top_layout = QVBoxLayout(left_top)
        left_top_layout.setContentsMargins(0, 0, 0, 0)
        left_top_layout.addWidget(folder_group)
        left_top_layout.addWidget(batch_group)
        left_top_layout.addWidget(files_group, 1)

        self.left_split = QSplitter(Qt.Orientation.Vertical)
        self.left_split.addWidget(left_top)
        self.left_split.addWidget(logs_group)
        self.left_split.setStretchFactor(0, 3)
        self.left_split.setStretchFactor(1, 1)

        center_widget = self.preview_panel
        right_widget = self.settings_scroll

        self.main_split = QSplitter(Qt.Orientation.Horizontal)
        self.main_split.addWidget(self.left_split)
        self.main_split.addWidget(center_widget)
        self.main_split.addWidget(right_widget)
        self.main_split.setStretchFactor(0, 2)
        self.main_split.setStretchFactor(1, 3)
        self.main_split.setStretchFactor(2, 1)

        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.addWidget(self.main_split)
        self.setCentralWidget(container)

        header = self.file_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, self.file_tree.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

        self.statusBar().showMessage("Ready")

    def _connect_signals(self) -> None:
        self.select_input_button.clicked.connect(self._select_input_folder)
        self.select_output_button.clicked.connect(self._select_output_folder)
        self.file_tree.currentItemChanged.connect(self._schedule_preview_refresh)
        self.settings_panel.settings_changed.connect(self._on_trace_settings_changed)
        self.settings_panel.existing_output_mode_changed.connect(self._on_existing_output_mode_changed)
        self.settings_panel.trace_preset_selected.connect(self._apply_trace_preset)
        self.settings_panel.save_preset_requested.connect(self._save_custom_preset)
        self.settings_panel.import_preset_requested.connect(self._import_custom_preset)
        self.settings_panel.export_preset_requested.connect(self._export_custom_preset)
        self.settings_panel.reset_requested.connect(self._reset_to_defaults)
        self.preview_panel.export_requested.connect(self._export_current_preview)
        self.preview_panel.refresh_requested.connect(self._refresh_preview_now)
        self.start_batch_button.clicked.connect(self._start_batch)
        self.cancel_batch_button.clicked.connect(self._cancel_batch)
        self.export_log_combo.currentIndexChanged.connect(self._on_export_log_format_changed)

    def _apply_loaded_settings(self) -> None:
        self.resize(self.window_settings.width, self.window_settings.height)
        self._set_combo_value(self.export_log_combo, self.app_settings.export_log_format)
        self._refresh_backend_label()

        if self.app_settings.input_folder:
            self.input_label.setText(f"Input folder: {self.app_settings.input_folder}")
            self._scan_input_folder(Path(self.app_settings.input_folder))
        if self.app_settings.output_folder:
            self.output_label.setText(f"Output folder: {self.app_settings.output_folder}")
        self.settings_panel.set_settings(self.trace_settings)
        self.settings_panel.set_existing_output_mode(self.app_settings.existing_output_mode)
        self._refresh_preset_selector()
        QTimer.singleShot(0, self._restore_window_layout)

    def _select_input_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if not selected:
            return
        self.app_settings.input_folder = selected
        self.input_label.setText(f"Input folder: {selected}")
        self._scan_input_folder(Path(selected))
        self._append_log(f"Selected input folder: {selected}")
        self._save_settings()

    def _select_output_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if not selected:
            return
        self.app_settings.output_folder = selected
        self.output_label.setText(f"Output folder: {selected}")
        self._append_log(f"Selected output folder: {selected}")
        self._save_settings()

    def _scan_input_folder(self, folder: Path) -> None:
        self.file_tree.clear()
        self.file_items_by_path.clear()
        self.scanned_files = self.file_scanner.scan(folder)

        for file_item in self.scanned_files:
            tree_item = QTreeWidgetItem(
                [
                    file_item.filename,
                    file_item.extension.upper().lstrip("."),
                    f"{file_item.width} x {file_item.height}",
                    "Yes" if file_item.has_alpha else "No",
                    file_item.status,
                ]
            )
            tree_item.setData(0, Qt.ItemDataRole.UserRole, str(file_item.path))
            tree_item.setToolTip(0, file_item.message or file_item.status)
            self.file_tree.addTopLevelItem(tree_item)
            self.file_items_by_path[str(file_item.path)] = tree_item

        self.file_tree.resizeColumnToContents(0)
        self.file_tree.resizeColumnToContents(1)
        self.file_tree.resizeColumnToContents(2)
        self.file_tree.resizeColumnToContents(3)

        self.statusBar().showMessage(f"Found {len(self.scanned_files)} supported files")
        self._append_log(f"Scanned folder: {folder} | {len(self.scanned_files)} supported files")
        if self.file_tree.topLevelItemCount() > 0:
            self.file_tree.setCurrentItem(self.file_tree.topLevelItem(0))

    def _schedule_preview_refresh(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None = None) -> None:
        if current is None:
            self.current_preview_path = None
            self.current_preview_result = None
            self.preview_panel.set_source_image(None)
            self.preview_panel.set_preview_result(PreviewResult(False, False, False))
            self._refresh_backend_label()
            return

        source_path = Path(current.data(0, Qt.ItemDataRole.UserRole))
        self.current_preview_path = source_path
        self._refresh_backend_label()
        self.preview_panel.set_source_image(source_path)
        self.preview_panel.set_busy(True)
        self.preview_timer.start(self.app_settings.preview_debounce_ms)

    def _queue_preview_refresh(self) -> None:
        if self.current_preview_path is None:
            return
        if self.preview_thread is not None:
            self._preview_pending = True
            return
        self._start_preview_worker(self.current_preview_path, self.trace_settings)

    def _refresh_preview_now(self) -> None:
        self.preview_timer.stop()
        self._queue_preview_refresh()

    def _on_trace_settings_changed(self, settings: TraceSettings) -> None:
        self.trace_settings = settings
        self._refresh_backend_label()
        self._refresh_preset_selector()
        self._save_settings()
        if self.current_preview_path is not None:
            self.preview_timer.start(self.app_settings.preview_debounce_ms)

    def _on_existing_output_mode_changed(self, mode: str) -> None:
        self.app_settings.existing_output_mode = mode
        self.app_settings.overwrite_existing = mode == "overwrite"
        self._append_log(f"Existing output mode set to: {mode}")
        self._save_settings()

    def _on_export_log_format_changed(self, *_args: object) -> None:
        self.app_settings.export_log_format = self.export_log_combo.currentData()
        self._save_settings()

    def _reset_to_defaults(self) -> None:
        if self.batch_thread is not None:
            QMessageBox.information(self, "Busy", "Stop the current batch before resetting settings.")
            return

        self.app_settings, self.trace_settings, self.window_settings = self.config_manager.reset()
        self.preset_manager.load_custom_presets()
        self.settings_panel.set_settings(self.trace_settings)
        self.settings_panel.set_existing_output_mode(self.app_settings.existing_output_mode)
        self._refresh_preset_selector()
        self._set_combo_value(self.export_log_combo, self.app_settings.export_log_format)
        self.input_label.setText("Input folder: Not selected")
        self.output_label.setText("Output folder: Not selected")
        self.current_file_label.setText("Current file: -")
        self.progress_bar.setValue(0)
        self.file_tree.clear()
        self.file_items_by_path.clear()
        self.scanned_files = []
        self.current_preview_path = None
        self.current_preview_result = None
        self.preview_panel.set_source_image(None)
        self.preview_panel.set_preview_result(PreviewResult(False, False, False))
        self._refresh_backend_label()
        self.resize(self.window_settings.width, self.window_settings.height)
        self._restore_window_layout()
        self._append_log("Settings reset to defaults")

    def _apply_trace_preset(self, preset_id: str) -> None:
        preset = self.preset_manager.get_preset(preset_id)
        if preset is None:
            return
        self.trace_settings = preset.settings.copy()
        self.settings_panel.set_settings(self.trace_settings)
        self.settings_panel.set_selected_trace_preset(preset.preset_id)
        self._refresh_backend_label()
        self._append_log(f"Applied preset: {preset.name}")
        self._save_settings()
        if self.current_preview_path is not None:
            self.preview_timer.start(self.app_settings.preview_debounce_ms)

    def _save_custom_preset(self) -> None:
        name, accepted = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not accepted:
            return
        if not name.strip():
            QMessageBox.warning(self, "Preset name required", "Enter a preset name before saving.")
            return
        description, _accepted_description = QInputDialog.getText(
            self,
            "Preset Description",
            "Description (optional):",
        )
        try:
            preset = self.preset_manager.save_custom_preset(
                name=name,
                description=description,
                settings=self.trace_settings,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Preset save failed", str(exc))
            return

        self._refresh_preset_selector(selected_preset_id=preset.preset_id)
        self._append_log(f"Saved custom preset: {preset.name}")

    def _import_custom_preset(self) -> None:
        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Preset",
            str(Path.home()),
            "Preset JSON (*.json)",
        )
        if not source_path:
            return
        try:
            preset = self.preset_manager.import_preset(Path(source_path))
        except ValueError as exc:
            QMessageBox.warning(self, "Import failed", str(exc))
            return

        self.trace_settings = preset.settings.copy()
        self.settings_panel.set_settings(self.trace_settings)
        self._refresh_backend_label()
        self._refresh_preset_selector(selected_preset_id=preset.preset_id)
        self._append_log(f"Imported preset: {preset.name}")
        self._save_settings()
        if self.current_preview_path is not None:
            self.preview_timer.start(self.app_settings.preview_debounce_ms)

    def _export_custom_preset(self) -> None:
        preset_id = self.settings_panel.current_trace_preset_id()
        preset = self.preset_manager.get_preset(preset_id)
        if preset is None or preset.is_builtin:
            QMessageBox.information(
                self,
                "Custom preset required",
                "Select a saved custom preset before exporting it.",
            )
            return

        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Preset",
            str(Path.home() / f"{self._sanitize_preset_filename(preset.name)}.json"),
            "Preset JSON (*.json)",
        )
        if not target_path:
            return

        try:
            self.preset_manager.export_preset(preset.preset_id, Path(target_path))
        except ValueError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return

        self._append_log(f"Exported preset: {preset.name} -> {target_path}")

    def _export_current_preview(self) -> None:
        if self.current_preview_path is None or self.current_preview_result is None or not self.current_preview_result.svg_available:
            QMessageBox.information(self, "Preview unavailable", "Generate a valid preview before exporting.")
            return

        default_folder = self.app_settings.output_folder or str(self.current_preview_path.parent)
        default_path = str(Path(default_folder) / f"{self.current_preview_path.stem}.svg")
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Preview SVG",
            default_path,
            "SVG files (*.svg)",
        )
        if not target_path:
            return

        try:
            self.batch_manager.exporter.export(Path(target_path), self.current_preview_result.svg_text, self.trace_settings)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))
            self._append_log(f"Preview export failed: {exc}")
            return

        self._append_log(f"Preview exported: {target_path}")
        self.statusBar().showMessage(f"Preview exported to {target_path}")

    def _start_batch(self) -> None:
        if not self.app_settings.input_folder or not self.app_settings.output_folder:
            QMessageBox.warning(self, "Missing folders", "Select both input and output folders before export.")
            return

        output_folder = Path(self.app_settings.output_folder)
        try:
            output_folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Output folder error", f"Could not create output folder:\n{exc}")
            return

        source_paths = [item.path for item in self.scanned_files if item.status != "Unsupported"]
        if not source_paths:
            QMessageBox.information(self, "No files", "No supported PNG or JPG files were found in the selected folder.")
            return

        jobs = self.batch_manager.create_jobs(
            source_paths=source_paths,
            output_folder=output_folder,
            existing_output_mode=self.app_settings.existing_output_mode,
        )
        self._set_batch_ui_state(True)
        self._reset_tree_statuses(jobs)
        self.progress_bar.setValue(0)
        self.current_file_label.setText("Starting batch...")
        self._append_log(f"Starting batch: {len(jobs)} files")

        self.batch_thread = QThread(self)
        self.batch_worker = BatchWorker(
            batch_manager=self.batch_manager,
            jobs=jobs,
            settings=self.trace_settings,
            log_format=self.app_settings.export_log_format,
            max_workers=self.app_settings.max_workers,
        )
        self.batch_worker.moveToThread(self.batch_thread)

        self.batch_thread.started.connect(self.batch_worker.run)
        self.batch_worker.progress_changed.connect(self._on_batch_progress)
        self.batch_worker.jobs_finished.connect(self._on_batch_jobs_finished)
        self.batch_worker.completed.connect(self._on_batch_completed)
        self.batch_worker.failed.connect(self._on_batch_failed)
        self.batch_worker.completed.connect(self.batch_thread.quit)
        self.batch_worker.failed.connect(self.batch_thread.quit)
        self.batch_thread.finished.connect(self._cleanup_batch_thread)

        self.batch_thread.start()
        self.statusBar().showMessage("Batch processing started")

    def _cancel_batch(self) -> None:
        if self.batch_worker is None:
            return
        self.batch_worker.cancel()
        self.current_file_label.setText("Cancelling...")
        self._append_log("Batch cancel requested")

    def _on_batch_progress(self, progress: BatchProgress) -> None:
        self.progress_bar.setValue(progress.percent)
        self.current_file_label.setText(progress.current_file or "-")
        self.statusBar().showMessage(
            f"Processed {progress.completed_jobs}/{progress.total_jobs} | "
            f"Exported {progress.exported_jobs} | Skipped {progress.skipped_jobs} | "
            f"Failed {progress.failed_jobs} | Cancelled {progress.cancelled_jobs}"
        )

    def _on_batch_jobs_finished(self, jobs: list[BatchJob]) -> None:
        if not jobs:
            return

        log_lines: list[str] = []
        self.file_tree.setUpdatesEnabled(False)
        try:
            for job in jobs:
                tree_item = self.file_items_by_path.get(str(job.source_path))
                if tree_item is not None:
                    tree_item.setText(4, job.status)
                    tree_item.setToolTip(0, job.warning or job.error or job.status)

                detail = job.warning or job.error or "OK"
                log_lines.append(f"{job.status}: {job.source_path.name} -> {job.output_path.name} | {detail}")
        finally:
            self.file_tree.setUpdatesEnabled(True)

        self.log_panel.append_lines(log_lines)

    def _on_batch_completed(self, summary: BatchSummary) -> None:
        self._set_batch_ui_state(False)
        self.progress_bar.setValue(100 if summary.total_jobs else 0)
        self.current_file_label.setText("Completed")
        self.statusBar().showMessage("Batch processing completed")
        self._append_log("Batch finished")
        if summary.log_export_error:
            self._append_log(f"Batch log export warning: {summary.log_export_error}")
        QMessageBox.information(self, "Batch Summary", self._summary_text(summary))

    def _on_batch_failed(self, error_message: str) -> None:
        self._set_batch_ui_state(False)
        self.current_file_label.setText("Failed")
        self.statusBar().showMessage("Batch processing failed")
        self._append_log(f"Batch failed: {error_message}")
        QMessageBox.critical(self, "Batch failed", error_message)

    def _cleanup_batch_thread(self) -> None:
        if self.batch_worker is not None:
            self.batch_worker.deleteLater()
            self.batch_worker = None
        if self.batch_thread is not None:
            self.batch_thread.deleteLater()
            self.batch_thread = None

    def _start_preview_worker(self, image_path: Path, settings: TraceSettings) -> None:
        self.preview_panel.set_busy(True)
        self.statusBar().showMessage(f"Refreshing preview for {image_path.name}")

        self.preview_thread = QThread(self)
        self.preview_worker = PreviewWorker(
            image_path=image_path,
            settings=settings,
            preview_service=self.preview_service,
        )
        self.preview_worker.moveToThread(self.preview_thread)

        self.preview_thread.started.connect(self.preview_worker.run)
        self.preview_worker.completed.connect(self._on_preview_completed)
        self.preview_worker.failed.connect(self._on_preview_failed)
        self.preview_worker.completed.connect(self.preview_thread.quit)
        self.preview_worker.failed.connect(self.preview_thread.quit)
        self.preview_thread.finished.connect(self._cleanup_preview_thread)

        self.preview_thread.start()

    def _on_preview_completed(self, source_path: str, result: PreviewResult) -> None:
        path = Path(source_path)
        if self.current_preview_path is not None and path == self.current_preview_path:
            self.current_preview_result = result
            self.preview_panel.set_preview_result(result)
            if result.error:
                self._append_log(f"Preview failed for {path.name}: {result.error}")
            else:
                self._append_log(f"Preview refreshed for {path.name}")
            self.statusBar().showMessage(f"Preview updated for {path.name}")

    def _on_preview_failed(self, source_path: str, error_message: str) -> None:
        path = Path(source_path)
        if self.current_preview_path is not None and path == self.current_preview_path:
            self.current_preview_result = PreviewResult(
                source_loaded=False,
                mask_available=False,
                svg_available=False,
                error=error_message,
            )
            self.preview_panel.set_preview_result(self.current_preview_result)
            self.statusBar().showMessage(f"Preview failed for {path.name}")
            self._append_log(f"Preview failed for {path.name}: {error_message}")

    def _cleanup_preview_thread(self) -> None:
        if self.preview_worker is not None:
            self.preview_worker.deleteLater()
            self.preview_worker = None
        if self.preview_thread is not None:
            self.preview_thread.deleteLater()
            self.preview_thread = None
        if self._preview_pending and self.current_preview_path is not None:
            self._preview_pending = False
            self._queue_preview_refresh()

    def _reset_tree_statuses(self, jobs: list[BatchJob]) -> None:
        jobs_by_path = {str(job.source_path): job for job in jobs}
        for file_item in self.scanned_files:
            tree_item = self.file_items_by_path.get(str(file_item.path))
            if tree_item is None:
                continue
            job = jobs_by_path.get(str(file_item.path))
            if job is None:
                tree_item.setText(4, "Skipped")
            else:
                tree_item.setText(4, job.status)

    def _set_batch_ui_state(self, running: bool) -> None:
        self.select_input_button.setEnabled(not running)
        self.select_output_button.setEnabled(not running)
        self.start_batch_button.setEnabled(not running)
        self.cancel_batch_button.setEnabled(running)
        self.export_log_combo.setEnabled(not running)
        self.settings_scroll.setEnabled(not running)

    def _summary_text(self, summary: BatchSummary) -> str:
        lines = [
            f"Output folder: {summary.output_folder}",
            f"Total files: {summary.total_jobs}",
            f"Exported: {summary.exported_jobs}",
            f"Skipped: {summary.skipped_jobs}",
            f"Failed: {summary.failed_jobs}",
            f"Cancelled: {summary.cancelled_jobs}",
        ]
        if summary.log_path is not None:
            lines.append(f"Log file: {summary.log_path}")
        if summary.log_export_error:
            lines.append(f"Log export warning: {summary.log_export_error}")
        return "\n".join(lines)

    def _append_log(self, message: str) -> None:
        self.log_panel.append_line(message)

    def _refresh_backend_label(self) -> None:
        backend_name = self.preview_service.backend_name(self.trace_settings, self.current_preview_path)
        mode_label = self.trace_settings.trace_mode.capitalize()
        self.backend_label.setText(f"Backend: {backend_name} | Mode: {mode_label}")

    def _refresh_preset_selector(self, selected_preset_id: str | None = None) -> None:
        matched_preset_id = selected_preset_id or self.preset_manager.match_preset_id(self.trace_settings)
        self.settings_panel.set_available_presets(
            presets=self.preset_manager.all_presets(),
            selected_preset_id=matched_preset_id,
        )

    def _save_settings(self) -> None:
        self._capture_window_settings()
        self.config_manager.save(self.app_settings, self.trace_settings, self.window_settings)

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _sanitize_preset_filename(self, value: str) -> str:
        return re.sub(r'[<>:"/\\\\|?*]+', "-", value).strip().strip(".") or "tracer-preset"

    def _capture_window_settings(self) -> None:
        self.window_settings.width = max(900, self.width())
        self.window_settings.height = max(600, self.height())
        if hasattr(self, "main_split"):
            sizes = self.main_split.sizes()
            if len(sizes) == 3:
                self.window_settings.main_splitter_sizes = sizes
        if hasattr(self, "left_split"):
            sizes = self.left_split.sizes()
            if len(sizes) == 2:
                self.window_settings.left_splitter_sizes = sizes

    def _restore_window_layout(self) -> None:
        if hasattr(self, "main_split"):
            self.main_split.setSizes(self.window_settings.main_splitter_sizes)
        if hasattr(self, "left_split"):
            self.left_split.setSizes(self.window_settings.left_splitter_sizes)

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self._save_settings()
        super().closeEvent(event)
