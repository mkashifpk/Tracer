from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tracer.models.app_settings import ExistingOutputMode
from tracer.models.trace_preset import TracePreset
from tracer.models.trace_settings import TraceSettings


class LabeledSlider(QWidget):
    value_changed = Signal(int)

    def __init__(
        self,
        minimum: int,
        maximum: int,
        suffix: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._suffix = suffix

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.value_label = QLabel()
        self.value_label.setMinimumWidth(48)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.value_label)

        self.slider.valueChanged.connect(self._on_value_changed)
        self._on_value_changed(self.slider.value())

    def set_value(self, value: int) -> None:
        self.slider.setValue(value)

    def value(self) -> int:
        return self.slider.value()

    def _on_value_changed(self, value: int) -> None:
        self.value_label.setText(f"{value}{self._suffix}")
        self.value_changed.emit(value)


class SettingsPanel(QWidget):
    settings_changed = Signal(object)
    existing_output_mode_changed = Signal(str)
    trace_preset_selected = Signal(str)
    save_preset_requested = Signal()
    import_preset_requested = Signal()
    export_preset_requested = Signal()
    reset_requested = Signal()

    def __init__(
        self,
        settings: TraceSettings,
        existing_output_mode: ExistingOutputMode = "skip",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._existing_output_mode = existing_output_mode
        self._preset_descriptions: dict[str, str] = {}

        self.trace_preset_combo = QComboBox()
        self.trace_mode_combo = QComboBox()
        self.trace_mode_combo.addItem("Auto", userData="auto")
        self.trace_mode_combo.addItem("Monochrome (Potrace)", userData="monochrome")
        self.trace_mode_combo.addItem("Color (VTracer)", userData="color")
        self.quality_preset_combo = QComboBox()
        self.quality_preset_combo.addItem("Low", userData="low")
        self.quality_preset_combo.addItem("Balanced", userData="balanced")
        self.quality_preset_combo.addItem("High", userData="high")
        self.preset_hint = QLabel()
        self.preset_hint.setObjectName("mutedLabel")
        self.preset_hint.setWordWrap(True)
        self.mode_hint = QLabel()
        self.mode_hint.setObjectName("mutedLabel")
        self.mode_hint.setWordWrap(True)
        self.save_preset_button = QPushButton("Save Preset")
        self.import_preset_button = QPushButton("Import Preset")
        self.export_preset_button = QPushButton("Export Preset")

        self.threshold_slider = LabeledSlider(0, 255)
        self.invert_checkbox = QCheckBox("Invert colors")
        self.min_artifact_spin = QSpinBox()
        self.min_artifact_spin.setRange(0, 100000)

        self.smoothing_slider = LabeledSlider(0, 100, suffix="%")
        self.simplification_slider = LabeledSlider(1, 300)
        self.simplification_hint = QLabel()
        self.simplification_hint.setObjectName("mutedLabel")
        self.simplification_hint.setWordWrap(True)

        self.ignore_transparency_checkbox = QCheckBox("Ignore transparency")
        self.merge_shapes_checkbox = QCheckBox("Merge nearby shapes")
        self.resize_checkbox = QCheckBox("Resize before trace")
        self.resize_max_dimension_spin = QSpinBox()
        self.resize_max_dimension_spin.setRange(64, 20000)

        self.fill_only_checkbox = QCheckBox("Fill only output")
        self.stroke_output_checkbox = QCheckBox("Stroke output")

        self.existing_output_combo = QComboBox()
        self.existing_output_combo.addItem("Skip existing", userData="skip")
        self.existing_output_combo.addItem("Overwrite existing", userData="overwrite")
        self.reset_button = QPushButton("Reset To Defaults")
        self.developer_name_label = QLabel("Muhammad Kashif")
        self.developer_name_label.setObjectName("developerName")
        self.developer_email_label = QLabel('<a href="mailto:mkashifiqbalpk@gmail.com">mkashifiqbalpk@gmail.com</a>')
        self.developer_email_label.setObjectName("mutedLabel")
        self.developer_email_label.setOpenExternalLinks(True)
        self.developer_email_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)

        self._build_ui()
        self.set_settings(settings)
        self.set_existing_output_mode(existing_output_mode)
        self._connect_signals()

    def _build_ui(self) -> None:
        preset_group = QGroupBox("Presets")
        preset_form = QFormLayout()
        preset_form.addRow("Tracing preset", self.trace_preset_combo)
        preset_form.addRow("", self.preset_hint)
        preset_buttons = QHBoxLayout()
        preset_buttons.addWidget(self.save_preset_button)
        preset_buttons.addWidget(self.import_preset_button)
        preset_buttons.addWidget(self.export_preset_button)
        preset_form.addRow(preset_buttons)
        preset_group.setLayout(preset_form)

        tracing_group = QGroupBox("Tracing")
        tracing_form = QFormLayout()
        tracing_form.addRow("Trace mode", self.trace_mode_combo)
        tracing_form.addRow("", self.mode_hint)
        tracing_form.addRow("Quality preset", self.quality_preset_combo)
        tracing_form.addRow("Threshold", self.threshold_slider)
        tracing_form.addRow("", self.invert_checkbox)
        tracing_form.addRow("Min artifact area", self.min_artifact_spin)
        tracing_form.addRow("Smoothing strength", self.smoothing_slider)
        tracing_form.addRow("Simplification", self.simplification_slider)
        tracing_form.addRow("", self.simplification_hint)
        tracing_group.setLayout(tracing_form)

        image_group = QGroupBox("Image Handling")
        image_form = QFormLayout()
        image_form.addRow("", self.ignore_transparency_checkbox)
        image_form.addRow("", self.merge_shapes_checkbox)
        image_form.addRow("", self.resize_checkbox)
        image_form.addRow("Resize max dimension", self.resize_max_dimension_spin)
        image_group.setLayout(image_form)

        export_group = QGroupBox("Export")
        export_form = QFormLayout()
        export_form.addRow("", self.fill_only_checkbox)
        export_form.addRow("", self.stroke_output_checkbox)
        export_form.addRow("Existing SVGs", self.existing_output_combo)
        export_form.addRow("", self.reset_button)
        export_group.setLayout(export_form)

        developer_group = QGroupBox("Developer")
        developer_layout = QVBoxLayout()
        developer_layout.addWidget(self.developer_name_label)
        developer_layout.addWidget(self.developer_email_label)
        developer_group.setLayout(developer_layout)

        layout = QVBoxLayout(self)
        layout.addWidget(preset_group)
        layout.addWidget(tracing_group)
        layout.addWidget(image_group)
        layout.addWidget(export_group)
        layout.addWidget(developer_group)
        layout.addStretch()

    def _connect_signals(self) -> None:
        self.trace_preset_combo.currentIndexChanged.connect(self._emit_trace_preset_selected)
        self.save_preset_button.clicked.connect(self.save_preset_requested.emit)
        self.import_preset_button.clicked.connect(self.import_preset_requested.emit)
        self.export_preset_button.clicked.connect(self.export_preset_requested.emit)

        controls = [
            self.trace_mode_combo,
            self.quality_preset_combo,
            self.threshold_slider,
            self.invert_checkbox,
            self.min_artifact_spin,
            self.smoothing_slider,
            self.simplification_slider,
            self.ignore_transparency_checkbox,
            self.merge_shapes_checkbox,
            self.resize_checkbox,
            self.resize_max_dimension_spin,
            self.fill_only_checkbox,
            self.stroke_output_checkbox,
        ]
        for control in controls:
            signal = getattr(control, "value_changed", None)
            if signal is None:
                signal = getattr(control, "valueChanged", None)
            if signal is None:
                signal = getattr(control, "toggled", None)
            if signal is None:
                signal = getattr(control, "currentIndexChanged", None)
            signal.connect(self._emit_settings)

        self.existing_output_combo.currentIndexChanged.connect(self._emit_existing_output_mode)
        self.reset_button.clicked.connect(self.reset_requested.emit)

    def set_available_presets(
        self,
        presets: list[TracePreset],
        selected_preset_id: str | None = None,
    ) -> None:
        self._preset_descriptions = {preset.preset_id: preset.description for preset in presets}
        self.trace_preset_combo.blockSignals(True)
        self.trace_preset_combo.clear()
        self.trace_preset_combo.addItem("Current Settings", userData="")
        self.trace_preset_combo.insertSeparator(self.trace_preset_combo.count())

        builtin_presets = [preset for preset in presets if preset.is_builtin]
        custom_presets = [preset for preset in presets if not preset.is_builtin]

        for preset in builtin_presets:
            self.trace_preset_combo.addItem(f"{preset.name} [Built-in]", userData=preset.preset_id)
        if custom_presets:
            self.trace_preset_combo.insertSeparator(self.trace_preset_combo.count())
            for preset in custom_presets:
                self.trace_preset_combo.addItem(f"{preset.name} [Custom]", userData=preset.preset_id)

        self.trace_preset_combo.blockSignals(False)
        self.set_selected_trace_preset(selected_preset_id)

    def set_selected_trace_preset(self, preset_id: str | None) -> None:
        self.trace_preset_combo.blockSignals(True)
        self._set_combo_data(self.trace_preset_combo, preset_id or "")
        self.trace_preset_combo.blockSignals(False)
        self._update_preset_hint()

    def set_settings(self, settings: TraceSettings) -> None:
        self._settings = settings
        controls = [
            self.trace_mode_combo,
            self.quality_preset_combo,
            self.threshold_slider.slider,
            self.invert_checkbox,
            self.min_artifact_spin,
            self.smoothing_slider.slider,
            self.simplification_slider.slider,
            self.ignore_transparency_checkbox,
            self.merge_shapes_checkbox,
            self.resize_checkbox,
            self.resize_max_dimension_spin,
            self.fill_only_checkbox,
            self.stroke_output_checkbox,
        ]
        for control in controls:
            control.blockSignals(True)

        self._set_combo_data(self.trace_mode_combo, settings.trace_mode)
        self._set_combo_data(self.quality_preset_combo, settings.quality_preset)
        self.threshold_slider.set_value(settings.threshold)
        self.invert_checkbox.setChecked(settings.invert_colors)
        self.min_artifact_spin.setValue(settings.min_artifact_area)
        self.smoothing_slider.set_value(settings.smoothing_strength)
        self.simplification_slider.set_value(self._encode_simplification(settings.path_simplification_tolerance))
        self.ignore_transparency_checkbox.setChecked(settings.ignore_transparent_pixels)
        self.merge_shapes_checkbox.setChecked(settings.merge_nearby_shapes)
        self.resize_checkbox.setChecked(settings.resize_before_trace)
        self.resize_max_dimension_spin.setValue(settings.resize_max_dimension)
        self.fill_only_checkbox.setChecked(settings.fill_only_output)
        self.stroke_output_checkbox.setChecked(settings.stroke_output)

        for control in controls:
            control.blockSignals(False)
        self._update_simplification_hint()
        self._update_mode_controls()

    def current_settings(self) -> TraceSettings:
        return TraceSettings(
            trace_mode=self.trace_mode_combo.currentData(),
            quality_preset=self.quality_preset_combo.currentData(),
            threshold=self.threshold_slider.value(),
            invert_colors=self.invert_checkbox.isChecked(),
            min_artifact_area=self.min_artifact_spin.value(),
            smoothing_strength=self.smoothing_slider.value(),
            path_simplification_tolerance=self._decode_simplification(self.simplification_slider.value()),
            resize_before_trace=self.resize_checkbox.isChecked(),
            resize_max_dimension=self.resize_max_dimension_spin.value(),
            ignore_transparent_pixels=self.ignore_transparency_checkbox.isChecked(),
            merge_nearby_shapes=self.merge_shapes_checkbox.isChecked(),
            fill_only_output=self.fill_only_checkbox.isChecked(),
            stroke_output=self.stroke_output_checkbox.isChecked(),
            stroke_width=self._settings.stroke_width,
            color_precision=self._settings.color_precision,
            color_layer_difference=self._settings.color_layer_difference,
            color_filter_speckle=self._settings.color_filter_speckle,
            color_corner_threshold=self._settings.color_corner_threshold,
            color_length_threshold=self._settings.color_length_threshold,
            color_max_iterations=self._settings.color_max_iterations,
            color_splice_threshold=self._settings.color_splice_threshold,
            color_path_precision=self._settings.color_path_precision,
        )

    def set_existing_output_mode(self, mode: ExistingOutputMode) -> None:
        self._existing_output_mode = mode
        self.existing_output_combo.blockSignals(True)
        self._set_combo_data(self.existing_output_combo, mode)
        self.existing_output_combo.blockSignals(False)

    def current_existing_output_mode(self) -> ExistingOutputMode:
        return self.existing_output_combo.currentData()

    def current_trace_preset_id(self) -> str | None:
        value = self.trace_preset_combo.currentData()
        return value or None

    def _emit_settings(self, *_args: object) -> None:
        self._update_simplification_hint()
        self._update_mode_controls()
        self._update_preset_hint()
        self.settings_changed.emit(self.current_settings())

    def _emit_existing_output_mode(self, *_args: object) -> None:
        self.existing_output_mode_changed.emit(self.current_existing_output_mode())

    def _emit_trace_preset_selected(self, *_args: object) -> None:
        self._update_preset_hint()
        preset_id = self.current_trace_preset_id()
        if preset_id:
            self.trace_preset_selected.emit(preset_id)

    def _update_simplification_hint(self) -> None:
        value = self._decode_simplification(self.simplification_slider.value())
        self.simplification_hint.setText(f"Simplification tolerance: {value:.2f}")

    def _update_preset_hint(self) -> None:
        preset_id = self.current_trace_preset_id()
        if preset_id:
            description = self._preset_descriptions.get(preset_id, "").strip()
            if description:
                self.preset_hint.setText(description)
            else:
                self.preset_hint.setText("Preset will overwrite the tracing controls shown below.")
            self.export_preset_button.setEnabled(preset_id.startswith("custom:"))
            return
        self.preset_hint.setText("Current settings are editable and not locked to a saved preset.")
        self.export_preset_button.setEnabled(False)

    def _update_mode_controls(self) -> None:
        trace_mode = self.trace_mode_combo.currentData()
        is_color_mode = trace_mode == "color"
        self.threshold_slider.setEnabled(not is_color_mode)
        self.invert_checkbox.setEnabled(not is_color_mode)

        if trace_mode == "color":
            self.mode_hint.setText(
                "Color mode uses VTracer and keeps colored fills. Threshold and invert are ignored in this mode."
            )
        elif trace_mode == "monochrome":
            self.mode_hint.setText(
                "Monochrome mode uses Potrace when available for the cleanest black-and-white vector tracing."
            )
        else:
            self.mode_hint.setText(
                "Auto mode routes black-and-white artwork to Potrace and colorful artwork to VTracer."
            )

    def _encode_simplification(self, value: float) -> int:
        return max(1, min(300, int(round(value * 100))))

    def _decode_simplification(self, raw_value: int) -> float:
        return raw_value / 100.0

    def _set_combo_data(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
