"""A short export form with optional encoding controls."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox,
    QDoubleSpinBox, QSpinBox, QCheckBox, QLabel, QWidget, QDialogButtonBox)


class ExportDialog(QDialog):
    def __init__(self, editor):
        super().__init__(editor)
        t = editor.tr_text
        self.setWindowTitle(t('Zapisz gotowy film', 'Export your video'))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.size = QComboBox()
        self.size.addItems([t('Rozmiar oryginalny', 'Original size'), '1920 × 1080',
                            '3840 × 2160', '1080 × 1920', '1080 × 1080'])
        self.quality = QComboBox()
        self.quality.addItem(t('Standardowa — mniejszy plik', 'Standard — smaller file'), 20)
        self.quality.addItem(t('Wysoka — większy plik', 'High — larger file'), 17)
        form.addRow(t('Rozmiar obrazu', 'Video size'), self.size)
        form.addRow(t('Jakość', 'Quality'), self.quality)
        self.test = QCheckBox(t('Próba: pierwsze 10 sekund wybranego zakresu',
                               'Test: first 10 seconds of the selected range'))
        self.selected_range = QCheckBox(t('Tylko zakres zaznaczony na osi czasu', 'Only the selected timeline range'))
        layout.addWidget(self.selected_range)
        layout.addWidget(self.test)
        notice = QLabel(t('Napisy i logo będą częścią obrazu filmu. Oryginalny plik pozostanie bez zmian. '
                          'Domyślny format: MP4 — zalecany. Przy zmianie proporcji mogą pojawić się pasy.',
                          'Captions and logos become part of the video image. Your original file stays unchanged. '
                          'Default format: MP4 — recommended. Changing the aspect ratio may add bars.'))
        notice.setWordWrap(True)
        layout.addWidget(notice)
        toggle = QCheckBox(t('Zaawansowane ustawienia', 'Advanced settings'))
        layout.addWidget(toggle)
        self.advanced = QWidget()
        advanced_form = QFormLayout(self.advanced)
        self.profile = QComboBox()
        self.profile.addItems(['MP4 · H.264 / AAC', 'MP4 · H.265 / AAC', 'WebM · VP9 / Opus', 'MKV · H.264 / AAC'])
        self.fps = QDoubleSpinBox()
        self.fps.setRange(1, 120)
        self.fps.setDecimals(3)
        self.fps.setValue(max(1, min(120, editor.info['fps'])))
        self.crf = QSpinBox()
        self.crf.setRange(0, 51)
        self.crf.setValue(20)
        self.quality.currentIndexChanged.connect(lambda: self.crf.setValue(self.quality.currentData()))
        advanced_form.addRow(t('Format i kodek', 'Format and codec'), self.profile)
        advanced_form.addRow(t('Klatki na sekundę (FPS)', 'Frames per second (FPS)'), self.fps)
        advanced_form.addRow(t('Kompresja (CRF; mniej = wyższa jakość)', 'Compression (CRF; lower = higher quality)'), self.crf)
        hint = QLabel(t('Zmiana FPS ustawia stałą liczbę klatek na sekundę. Bez czasów słów '
                        'podświetlenie dzieli czas napisu równo między słowa.',
                        'Export uses a constant frame rate. Without word timings, highlighting '
                        'divides the caption duration equally between words.'))
        hint.setWordWrap(True)
        advanced_form.addRow(hint)
        layout.addWidget(self.advanced)
        self.advanced.hide()
        toggle.toggled.connect(self.advanced.setVisible)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(t('Wybierz plik i zapisz…', 'Choose file and export…'))
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName('primary')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t('Anuluj', 'Cancel'))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for form_layout in (form, advanced_form):
            for row in range(form_layout.rowCount()):
                field = form_layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
                label = form_layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
                if field and label and isinstance(label.widget(), QLabel):
                    label.widget().setBuddy(field.widget())
                    field.widget().setAccessibleName(label.widget().text())
        self.setMinimumWidth(460)
