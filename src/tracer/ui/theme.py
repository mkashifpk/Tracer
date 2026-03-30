from __future__ import annotations


def app_stylesheet() -> str:
    return """
    QWidget {
        font-family: "Segoe UI";
        font-size: 10pt;
        color: #1f2937;
    }

    QMainWindow, QWidget {
        background: #eef3f8;
        color: #1f2937;
    }

    QMainWindow::separator {
        background: #d8e1ec;
        width: 1px;
        height: 1px;
    }

    QFrame#previewCard, QGroupBox, QListWidget, QTreeWidget, QPlainTextEdit, QScrollArea {
        background: #ffffff;
        border: 1px solid #d8e1ec;
        border-radius: 14px;
    }

    QGroupBox {
        margin-top: 10px;
        padding-top: 14px;
        font-weight: 600;
    }

    QGroupBox::title {
        left: 12px;
        padding: 0 4px 0 4px;
        color: #4b5563;
    }

    QLabel#sectionTitle {
        font-size: 11.5pt;
        font-weight: 600;
        color: #0f172a;
    }

    QLabel#mutedLabel {
        color: #64748b;
    }

    QLabel#developerName {
        font-size: 10.5pt;
        font-weight: 600;
        color: #0f172a;
    }

    QLabel {
        background: transparent;
    }

    QLabel[textFormat="2"], QLabel[textFormat="1"] {
        background: transparent;
    }

    QTreeWidget::item, QPlainTextEdit {
        background: #ffffff;
    }

    QTreeWidget {
        alternate-background-color: #f8fbff;
        selection-background-color: #dbeafe;
        selection-color: #0f172a;
        outline: none;
    }

    QHeaderView::section {
        background: #f7f9fc;
        color: #475569;
        border: none;
        border-bottom: 1px solid #d8e1ec;
        padding: 8px 10px;
        font-weight: 600;
    }

    QPushButton {
        min-height: 34px;
        padding: 6px 14px;
        border-radius: 10px;
        border: 1px solid #bfdbfe;
        background: #eff6ff;
        color: #1d4ed8;
        font-weight: 600;
    }

    QPushButton:hover {
        border-color: #60a5fa;
        background: #dbeafe;
    }

    QPushButton:disabled {
        color: #94a3b8;
        background: #f8fafc;
        border-color: #e2e8f0;
    }

    QPushButton:pressed {
        background: #bfdbfe;
    }

    QComboBox, QSpinBox, QDoubleSpinBox, QListWidget, QPlainTextEdit {
        min-height: 32px;
        padding: 4px 8px;
        border: 1px solid #d1d9e6;
        border-radius: 10px;
        background: #fbfdff;
        selection-background-color: #dbeafe;
    }

    QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QPlainTextEdit:hover {
        border-color: #93c5fd;
    }

    QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus, QTreeWidget:focus {
        border: 1px solid #3b82f6;
        outline: none;
    }

    QCheckBox {
        spacing: 8px;
    }

    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 5px;
        border: 1px solid #cbd5e1;
        background: #ffffff;
    }

    QCheckBox::indicator:checked {
        background: #2563eb;
        border: 1px solid #2563eb;
    }

    QSlider::groove:horizontal {
        height: 6px;
        border-radius: 3px;
        background: #dbe7f5;
    }

    QSlider::sub-page:horizontal {
        border-radius: 3px;
        background: #60a5fa;
    }

    QSlider::handle:horizontal {
        width: 18px;
        margin: -6px 0;
        border-radius: 9px;
        background: #2563eb;
        border: 2px solid #ffffff;
    }

    QProgressBar {
        border: 1px solid #d1d9e6;
        border-radius: 10px;
        text-align: center;
        min-height: 22px;
        background: #f8fbff;
        color: #1f2937;
    }

    QProgressBar::chunk {
        border-radius: 9px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                    stop:0 #38bdf8, stop:1 #2563eb);
    }

    QScrollBar:vertical {
        background: transparent;
        width: 12px;
        margin: 4px 2px 4px 2px;
    }

    QScrollBar::handle:vertical {
        min-height: 32px;
        border-radius: 6px;
        background: #cbd5e1;
    }

    QScrollBar::handle:vertical:hover {
        background: #94a3b8;
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
        height: 0;
    }

    QScrollBar:horizontal {
        background: transparent;
        height: 12px;
        margin: 2px 4px 2px 4px;
    }

    QScrollBar::handle:horizontal {
        min-width: 32px;
        border-radius: 6px;
        background: #cbd5e1;
    }

    QScrollBar::handle:horizontal:hover {
        background: #94a3b8;
    }

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: transparent;
        width: 0;
    }

    QStatusBar {
        background: #f7fafc;
        border-top: 1px solid #d8e1ec;
        color: #475569;
    }
    """
