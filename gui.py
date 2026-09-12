"""
Moderne grafische Benutzeroberfläche (PyQt6) für die PDF-Seitennummerierung
mit nativer Drag & Drop-Unterstützung, Live-Vorschau und Logo-Entfernung.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QPoint, QRect, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent, QFont, QIcon, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import pymupdf
from pdf_processor import (
    HARDCODED_STYLE,
    PageNumberStyle,
    add_page_numbers,
    render_page_preview,
)


class ProcessingWorker(QObject):
    """Hintergrund-Worker für die PDF-Verarbeitung, um die UI flüssig zu halten."""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        input_pdf: str,
        output_pdf: str,
        start_number: int,
        remove_logo: bool,
        remove_old_pagination: bool,
        replace_anhang: bool = True,
        anhang_letter: str = "C",
    ):
        super().__init__()
        self.input_pdf = input_pdf
        self.output_pdf = output_pdf
        self.start_number = start_number
        self.remove_logo = remove_logo
        self.remove_old_pagination = remove_old_pagination
        self.replace_anhang = replace_anhang
        self.anhang_letter = anhang_letter

    def run(self):
        try:
            out_path = add_page_numbers(
                input_pdf=self.input_pdf,
                output_pdf=self.output_pdf,
                start_number=self.start_number,
                remove_logo=self.remove_logo,
                remove_old_pagination=self.remove_old_pagination,
                replace_anhang=self.replace_anhang,
                anhang_letter=self.anhang_letter,
                progress_callback=lambda cur, tot: self.progress.emit(cur, tot),
            )
            self.finished.emit(str(out_path))
        except Exception as e:
            self.error.emit(str(e))


class DropArea(QFrame):
    """Interaktive Drag & Drop-Zone mit Klick-Funktion für Dateiauswahl."""
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.current_file: Path | None = None
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("dropArea")
        self.setMinimumHeight(130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel("📄")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 36px; background: transparent;")

        self.title_label = QLabel("PDF-Datei hier hineinziehen")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #1E293B; background: transparent;")

        self.subtitle_label = QLabel("oder klicken, um den Dateiexplorer zu öffnen")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet("font-size: 12px; color: #64748B; background: transparent;")

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

        self.set_default_style()

    def set_default_style(self):
        self.setStyleSheet("""
            #dropArea {
                border: 2px dashed #CBD5E1;
                border-radius: 12px;
                background-color: #F8FAFC;
            }
            #dropArea:hover {
                border-color: #3B82F6;
                background-color: #EFF6FF;
            }
        """)

    def set_drag_over_style(self):
        self.setStyleSheet("""
            #dropArea {
                border: 2px dashed #2563EB;
                border-radius: 12px;
                background-color: #DBEAFE;
            }
        """)

    def set_file_loaded(self, path: Path, page_count: int, size_str: str):
        self.current_file = path
        self.icon_label.setText("✅")
        self.title_label.setText(path.name)
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #0F172A; background: transparent;")
        self.subtitle_label.setText(f"{page_count} Seiten • {size_str} • Klicken zum Wechseln")
        self.setStyleSheet("""
            #dropArea {
                border: 2px solid #10B981;
                border-radius: 12px;
                background-color: #ECFDF5;
            }
            #dropArea:hover {
                border-color: #059669;
                background-color: #D1FAE5;
            }
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith(".pdf") for url in urls):
                event.acceptProposedAction()
                self.set_drag_over_style()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        if self.current_file:
            # reload file style
            pass
        else:
            self.set_default_style()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(".pdf"):
                event.acceptProposedAction()
                self.file_selected.emit(file_path)
                return
        self.set_default_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "PDF-Datei auswählen",
                "",
                "PDF-Dateien (*.pdf)",
            )
            if file_path:
                self.file_selected.emit(file_path)


class MainWindow(QMainWindow):
    """Hauptfenster der PDF-Nummerierungs-App."""

    def __init__(self):
        super().__init__()
        self.selected_pdf: Path | None = None
        self.current_page_count: int = 0
        self.thread: QThread | None = None
        self.worker: ProcessingWorker | None = None
        self.last_output_path: Path | None = None

        self._init_window()
        self._build_ui()

    def _init_window(self):
        self.setWindowTitle("PDF Seitennummerierer & Styler")
        self.setMinimumSize(680, 800)
        self.resize(720, 840)

        # Globales Anwendungs-Styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F1F5F9;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame.card {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 12px;
            }
            QLabel {
                color: #1E293B;
            }
            QCheckBox {
                color: #1E293B;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #CBD5E1;
                background-color: #FFFFFF;
            }
            QCheckBox::indicator:checked {
                background-color: #2563EB;
                border-color: #2563EB;
                image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>');
            }
            QSpinBox {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 14px;
                font-weight: 600;
                color: #0F172A;
            }
            QSpinBox:focus {
                border-color: #2563EB;
                background-color: #FFFFFF;
            }
            QLineEdit {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                color: #334155;
            }
            QPushButton.primaryBtn {
                background-color: #2563EB;
                color: white;
                font-size: 15px;
                font-weight: 600;
                border-radius: 8px;
                padding: 12px 24px;
                border: none;
            }
            QPushButton.primaryBtn:hover {
                background-color: #1D4ED8;
            }
            QPushButton.primaryBtn:disabled {
                background-color: #94A3B8;
            }
            QPushButton.secondaryBtn {
                background-color: #FFFFFF;
                color: #334155;
                font-size: 12px;
                font-weight: 600;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton.secondaryBtn:hover {
                background-color: #F1F5F9;
                border-color: #94A3B8;
            }
            QProgressBar {
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                background-color: #F1F5F9;
                text-align: center;
                color: #0F172A;
                font-weight: 600;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #2563EB;
                border-radius: 5px;
            }
        """)

    def _build_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        title = QLabel("PDF Seitennummerierer")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #0F172A;")
        subtitle = QLabel("Seitenzahlen im exakten Seite.pdf-Stil (Arial 12.96 pt • unten rechts)")
        subtitle.setStyleSheet("font-size: 13px; color: #64748B;")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        main_layout.addLayout(header_layout)

        # 2. Drag & Drop Zone
        self.drop_area = DropArea()
        self.drop_area.file_selected.connect(self.on_file_loaded)
        main_layout.addWidget(self.drop_area)

        # 3. Einstellungen Card
        settings_card = QFrame()
        settings_card.setProperty("class", "card")
        settings_card_layout = QVBoxLayout(settings_card)
        settings_card_layout.setContentsMargins(18, 16, 18, 16)
        settings_card_layout.setSpacing(12)

        # Startnummer
        start_row = QHBoxLayout()
        start_label = QLabel("Start-Seitenzahl:")
        start_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #1E293B;")
        self.spin_start = QSpinBox()
        self.spin_start.setRange(1, 99999)
        self.spin_start.setValue(1)
        self.spin_start.setFixedWidth(110)
        self.spin_start.valueChanged.connect(self.update_preview)

        start_hint = QLabel("(Erste Seite des Dokuments erhält diese Nummer)")
        start_hint.setStyleSheet("font-size: 12px; color: #64748B;")

        start_row.addWidget(start_label)
        start_row.addWidget(self.spin_start)
        start_row.addWidget(start_hint)
        start_row.addStretch()
        settings_card_layout.addLayout(start_row)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #F1F5F9; background-color: #F1F5F9;")
        settings_card_layout.addWidget(sep1)

        # Anhang korrigieren
        anhang_row = QHBoxLayout()
        self.chk_replace_anhang = QCheckBox("Kopfzeile 'Anhang' auf Seite 1 anpassen:")
        self.chk_replace_anhang.setChecked(True)
        self.chk_replace_anhang.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.chk_replace_anhang.stateChanged.connect(self.update_preview)

        self.txt_anhang_letter = QLineEdit("C")
        self.txt_anhang_letter.setMaxLength(4)
        self.txt_anhang_letter.setFixedWidth(44)
        self.txt_anhang_letter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.txt_anhang_letter.setStyleSheet("font-weight: 700; font-size: 13px;")
        self.txt_anhang_letter.textChanged.connect(self.update_preview)

        anhang_hint = QLabel("(z. B. 'Anhang B...' ➔ 'Anhang C...')")
        anhang_hint.setStyleSheet("font-size: 11px; color: #64748B;")

        anhang_row.addWidget(self.chk_replace_anhang)
        anhang_row.addWidget(self.txt_anhang_letter)
        anhang_row.addWidget(anhang_hint)
        anhang_row.addStretch()
        settings_card_layout.addLayout(anhang_row)

        # Toggle 1: MAXQDA-Logo entfernen
        self.chk_remove_logo = QCheckBox("MAXQDA-Logo unten rechts herausschneiden")
        self.chk_remove_logo.setChecked(True)
        self.chk_remove_logo.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.chk_remove_logo.stateChanged.connect(self.update_preview)

        logo_desc = QLabel("   Entfernt das MAXQDA-Bildlogo unten rechts, damit Platz für die neue Seitenzahl ist.")
        logo_desc.setStyleSheet("font-size: 11px; color: #64748B;")
        settings_card_layout.addWidget(self.chk_remove_logo)
        settings_card_layout.addWidget(logo_desc)

        # Toggle 2: Alte zentrierte Seitenzahl entfernen
        self.chk_remove_old = QCheckBox("Bestehende zentrierte Seitenzahl in Fußzeile entfernen (z. B. '1/8')")
        self.chk_remove_old.setChecked(True)
        self.chk_remove_old.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.chk_remove_old.stateChanged.connect(self.update_preview)

        old_desc = QLabel("   Löscht alte Paginierungen in der Mitte der Fußzeile für ein sauberes Erscheinungsbild.")
        old_desc.setStyleSheet("font-size: 11px; color: #64748B;")
        settings_card_layout.addWidget(self.chk_remove_old)
        settings_card_layout.addWidget(old_desc)

        # Ausgabepfad
        out_row = QHBoxLayout()
        out_label = QLabel("Zielordner / Name:")
        out_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
        self.txt_output = QLineEdit()
        self.txt_output.setPlaceholderText("Wird automatisch erzeugt (z. B. Dokument_numbered.pdf)")
        self.btn_browse_out = QPushButton("Ändern...")
        self.btn_browse_out.setProperty("class", "secondaryBtn")
        self.btn_browse_out.clicked.connect(self.choose_output_path)

        out_row.addWidget(out_label)
        out_row.addWidget(self.txt_output)
        out_row.addWidget(self.btn_browse_out)
        settings_card_layout.addLayout(out_row)

        main_layout.addWidget(settings_card)

        # 4. Live-Vorschau Card
        preview_card = QFrame()
        preview_card.setProperty("class", "card")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(14, 12, 14, 12)
        preview_layout.setSpacing(8)

        preview_header = QHBoxLayout()
        preview_title = QLabel("Live-Vorschau der Fußzeile (Seite 1):")
        preview_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
        self.preview_badge = QLabel("Keine PDF geladen")
        self.preview_badge.setStyleSheet("font-size: 11px; color: #94A3B8; font-style: italic;")
        preview_header.addWidget(preview_title)
        preview_header.addStretch()
        preview_header.addWidget(self.preview_badge)
        preview_layout.addLayout(preview_header)

        self.preview_label = QLabel("Lade eine PDF-Datei hinein, um die Live-Vorschau zu sehen.")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(95)
        self.preview_label.setStyleSheet("""
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            color: #94A3B8;
            font-size: 12px;
        """)
        preview_layout.addWidget(self.preview_label)

        main_layout.addWidget(preview_card)

        # 5. Progress Bar & Action Button
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Status / Ergebnis-Box
        self.status_box = QFrame()
        self.status_box.setVisible(False)
        self.status_box.setStyleSheet("""
            background-color: #ECFDF5;
            border: 1px solid #A7F3D0;
            border-radius: 8px;
            padding: 8px;
        """)
        status_layout = QHBoxLayout(self.status_box)
        self.status_text = QLabel("Erfolgreich nummeriert!")
        self.status_text.setStyleSheet("color: #065F46; font-weight: 600; font-size: 12px; background: transparent;")
        self.btn_open_pdf = QPushButton("PDF öffnen")
        self.btn_open_pdf.setProperty("class", "secondaryBtn")
        self.btn_open_pdf.clicked.connect(self.open_output_pdf)
        self.btn_open_folder = QPushButton("Im Ordner zeigen")
        self.btn_open_folder.setProperty("class", "secondaryBtn")
        self.btn_open_folder.clicked.connect(self.open_output_folder)

        status_layout.addWidget(self.status_text)
        status_layout.addStretch()
        status_layout.addWidget(self.btn_open_pdf)
        status_layout.addWidget(self.btn_open_folder)
        main_layout.addWidget(self.status_box)

        # Start Button
        self.btn_process = QPushButton("🚀 PDF jetzt nummerieren")
        self.btn_process.setProperty("class", "primaryBtn")
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self.start_processing)
        main_layout.addWidget(self.btn_process)

    def on_file_loaded(self, file_path_str: str):
        path = Path(file_path_str)
        if not path.exists():
            return

        try:
            doc = pymupdf.open(path)
            self.current_page_count = len(doc)
            doc.close()
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Öffnen", f"Konnte PDF nicht öffnen:\n{e}")
            return

        self.selected_pdf = path
        size_kb = path.stat().st_size / 1024.0
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024.0:.1f} MB"

        self.drop_area.set_file_loaded(path, self.current_page_count, size_str)

        # Vorgeschlagenen Ausgabepfad setzen
        default_out = path.with_name(f"{path.stem}_nummeriert{path.suffix}")
        self.txt_output.setText(str(default_out))

        self.btn_process.setEnabled(True)
        self.status_box.setVisible(False)
        self.update_preview()

    def update_preview(self):
        if not self.selected_pdf or not self.selected_pdf.exists():
            return

        try:
            png_data = render_page_preview(
                pdf_path=self.selected_pdf,
                page_idx=0,
                start_number=self.spin_start.value(),
                remove_logo=self.chk_remove_logo.isChecked(),
                remove_old_pagination=self.chk_remove_old.isChecked(),
                replace_anhang=self.chk_replace_anhang.isChecked(),
                anhang_letter=self.txt_anhang_letter.text().strip().upper() or "C",
                footer_only=True,
            )

            qimg = QImage.fromData(png_data)
            pixmap = QPixmap.fromImage(qimg)

            scaled_pixmap = pixmap.scaledToWidth(
                self.preview_label.width() - 10,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled_pixmap)
            self.preview_badge.setText("Live-Vorschau aktiv")
            self.preview_badge.setStyleSheet("font-size: 11px; color: #10B981; font-weight: 600;")
        except Exception as e:
            self.preview_label.setText(f"Vorschau konnte nicht gerendert werden: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Wenn Fenstergröße geändert wird, ggf. Vorschau neu skalieren
        if self.selected_pdf:
            self.update_preview()

    def choose_output_path(self):
        current_txt = self.txt_output.text().strip()
        default_dir = str(Path(current_txt).parent) if current_txt else ""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Speicherort für nummerierte PDF wählen",
            default_dir,
            "PDF-Dateien (*.pdf)",
        )
        if file_path:
            if not file_path.lower().endswith(".pdf"):
                file_path += ".pdf"
            self.txt_output.setText(file_path)

    def start_processing(self):
        if not self.selected_pdf or not self.selected_pdf.exists():
            return

        out_path_str = self.txt_output.text().strip()
        if not out_path_str:
            out_path_str = str(self.selected_pdf.with_name(f"{self.selected_pdf.stem}_nummeriert.pdf"))

        self.btn_process.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(self.current_page_count)
        self.status_box.setVisible(False)

        # Thread & Worker starten
        self.thread = QThread()
        self.worker = ProcessingWorker(
            input_pdf=str(self.selected_pdf),
            output_pdf=out_path_str,
            start_number=self.spin_start.value(),
            remove_logo=self.chk_remove_logo.isChecked(),
            remove_old_pagination=self.chk_remove_old.isChecked(),
            replace_anhang=self.chk_replace_anhang.isChecked(),
            anhang_letter=self.txt_anhang_letter.text().strip().upper() or "C",
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.thread.start()

    def on_progress(self, current: int, total: int):
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"Verarbeite Seite {current} von {total}...")

    def on_finished(self, output_path: str):
        self.thread.quit()
        self.thread.wait()
        self.last_output_path = Path(output_path)

        self.progress_bar.setVisible(False)
        self.btn_process.setEnabled(True)

        self.status_text.setText(f"Fertig! Gespeichert als '{self.last_output_path.name}'")
        self.status_box.setVisible(True)

    def on_error(self, err_msg: str):
        self.thread.quit()
        self.thread.wait()
        self.progress_bar.setVisible(False)
        self.btn_process.setEnabled(True)
        QMessageBox.critical(self, "Fehler", f"Bei der Verarbeitung ist ein Fehler aufgetreten:\n{err_msg}")

    def open_output_pdf(self):
        if self.last_output_path and self.last_output_path.exists():
            os.startfile(str(self.last_output_path))

    def open_output_folder(self):
        if self.last_output_path and self.last_output_path.exists():
            subprocess.run(["explorer.exe", "/select,", str(self.last_output_path)])


def run_gui():
    """Startet die grafische Benutzeroberfläche."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
