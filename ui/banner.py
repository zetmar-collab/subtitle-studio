"""Explicit banner geometry with a live, shared-compositor preview."""
import copy
from dataclasses import asdict
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPlainTextEdit, QFontComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QColorDialog, QDialogButtonBox, QLabel, QScrollArea, QWidget, QPushButton)
from core.projects.model import Banner
from ui.preview import Preview
from ui.colors import ColorButton


class BannerDialog(QDialog):
    def __init__(self, owner, banner=None):
        super().__init__(owner)
        self.owner = owner
        self.value = copy.deepcopy(banner or Banner())
        self.project = copy.deepcopy(owner.project)
        self.index = next((i for i, item in enumerate(self.project.banners)
                           if item.banner_id == self.value.banner_id), len(self.project.banners))
        if self.index == len(self.project.banners):
            self.project.banners.append(self.value)
        t = owner.tr_text
        self.setWindowTitle(t('Baner — napis na kolorowym tle', 'Banner — text on a colored background'))
        self.resize(1020, 720)
        layout = QVBoxLayout(self)
        content = QHBoxLayout()
        layout.addLayout(content, 1)
        self.preview = Preview()
        self.preview.project = self.project
        self.preview.banner_index = self.index
        self.preview.frame = owner.preview.frame.copy()
        if self.preview.frame.isNull():
            self.preview.frame = QImage(640, 360, QImage.Format.Format_RGB888)
            self.preview.frame.fill(QColor('#273246'))
        content.addWidget(self.preview, 1)
        panel = QWidget()
        form = QFormLayout(panel)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.fields = {}
        def add(key, label, widget):
            form.addRow(label, widget)
            widget.setAccessibleName(label)
            self.fields[key] = widget
        templates = QHBoxLayout()
        self.template = QComboBox(); self.template.setAccessibleName(t('Szablon baneru', 'Banner template'))
        templates.addWidget(self.template, 1)
        for pl, en, callback in [('Zastosuj', 'Apply', self.apply_template),
                                 ('Zapisz jako…', 'Save as…', self.save_template),
                                 ('Usuń', 'Delete', self.delete_template)]:
            button = QPushButton(t(pl, en)); button.clicked.connect(callback); templates.addWidget(button)
        form.addRow(t('Szablon', 'Template'), templates)
        self.reload_templates()
        add('name', t('Nazwa warstwy', 'Layer name'), QLineEdit(self.value.name))
        text = QPlainTextEdit(self.value.text)
        text.setMaximumHeight(100)
        add('text', t('Tekst baneru', 'Banner text'), text)
        for key, pl, en, low, high in [
                ('x','Środek X (%)','Center X (%)',0,100), ('y','Środek Y (%)','Center Y (%)',0,100),
                ('width','Szerokość (%)','Width (%)',1,100), ('height','Wysokość (%)','Height (%)',1,100),
                ('opacity','Widoczność (%)','Opacity (%)',0,100)]:
            spin = QDoubleSpinBox(); spin.setRange(low, high); spin.setValue(getattr(self.value, key))
            add(key, t(pl, en), spin)
        font = QFontComboBox(); font.setCurrentFont(self.preview.font()); font.setCurrentText(self.value.font)
        add('font', t('Czcionka', 'Font'), font)
        for key, pl, en, low, high in [
                ('font_size','Rozmiar tekstu / 1080p','Text size / 1080p',8,300),
                ('radius','Zaokrąglenie','Corner radius',0,300), ('padding','Odstęp tekstu od krawędzi','Text padding',0,200),
                ('border_width','Grubość ramki','Border width',0,30),
                ('start','Początek (ms)','Start (ms)',0,2147483646), ('end','Koniec (ms)','End (ms)',1,2147483647)]:
            spin = QSpinBox(); spin.setRange(low, high); spin.setValue(getattr(self.value, key))
            add(key, t(pl, en), spin)
        for key, pl, en in [('bold','Pogrubienie','Bold'), ('auto_fit','Dopasuj tekst do prostokąta','Fit text inside rectangle')]:
            checkbox = QCheckBox(); checkbox.setChecked(getattr(self.value, key)); add(key, t(pl,en), checkbox)
        for key, pl, en in [('color','Kolor tekstu','Text color'), ('background','Kolor tła','Background color'),
                            ('border_color','Kolor ramki','Border color')]:
            button = ColorButton(getattr(self.value, key))
            button.clicked.connect(lambda checked=False, k=key: self.choose_color(k))
            add(key, t(pl,en), button)
        align = QComboBox()
        for pl,en,key in [('Do lewej','Left','left'), ('Wyśrodkowany','Center','center'), ('Do prawej','Right','right')]:
            align.addItem(t(pl,en),key)
        align.setCurrentIndex(align.findData(self.value.align)); add('align',t('Wyrównanie','Alignment'),align)
        animation = QComboBox()
        for key, pl, en in [('none','Brak','None'), ('fade','Przenikanie','Fade'),
                            ('slide_up','Wjazd z dołu','Slide up'), ('slide_down','Wjazd z góry','Slide down'),
                            ('slide_left','Wjazd z prawej','Slide in from right'),
                            ('slide_right','Wjazd z lewej','Slide in from left'), ('pop','Wyskok','Pop')]:
            animation.addItem(t(pl,en), key)
        animation.setCurrentIndex(animation.findData(self.value.animation))
        add('animation', t('Animacja wejścia i wyjścia','Entrance and exit animation'), animation)
        duration = QSpinBox(); duration.setRange(1, 5000); duration.setSuffix(' ms')
        duration.setValue(self.value.animation_ms)
        add('animation_ms', t('Czas animacji','Animation duration'), duration)
        if self.value.keyframes:
            form.addRow(QLabel(t(f'Klatki kluczowe ruchu: {len(self.value.keyframes)} (Montaż → Ctrl+K).',
                                 f'Motion keyframes: {len(self.value.keyframes)} (Edit → Ctrl+K).')))
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(panel)
        content.addWidget(scroll)
        self.note = QLabel(t('Przesuwaj baner myszą. Prawy dolny uchwyt zmienia jego rozmiar. '
                             'Wymiary dotyczą całego kolorowego prostokąta; czasy są w milisekundach filmu.',
                             'Drag the banner to move it. Its bottom-right handle resizes it. Dimensions describe '
                             'the entire colored rectangle; times are video milliseconds.'))
        self.note.setWordWrap(True); layout.addWidget(self.note)
        self.instructions = self.note.text()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText(t('Zapisz','Save'))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t('Anuluj','Cancel'))
        for widget in self.fields.values():
            for signal in ('textChanged','valueChanged','toggled','currentTextChanged'):
                if hasattr(widget,signal):
                    getattr(widget,signal).connect(self.update_preview)
                    break
        self.preview.moved.connect(self.move_banner)
        self.preview.resized.connect(self.resize_banner)
        from ui.help import install_help
        install_help(self,owner)
        self.update_preview()

    def reload_templates(self, select=None):
        from core.projects import banner_templates
        self.template.clear()
        user = banner_templates.load_user()
        for name in banner_templates.all_templates():
            self.template.addItem(name if name in user else name + ' · ' + self.owner.tr_text('wbudowany', 'built-in'), name)
        if select:
            self.template.setCurrentIndex(self.template.findData(select))

    def set_fields(self, value):
        for key, widget in self.fields.items():
            current = getattr(value, key)
            if isinstance(widget, ColorButton): widget.set_color(QColor(current))
            elif isinstance(widget, QPlainTextEdit): widget.setPlainText(current)
            elif isinstance(widget, QLineEdit): widget.setText(current)
            elif isinstance(widget, QCheckBox): widget.setChecked(current)
            elif key == 'font': widget.setCurrentText(current)
            elif isinstance(widget, QComboBox): widget.setCurrentIndex(widget.findData(current))
            else: widget.setValue(current)
        self.update_preview()

    def apply_template(self):
        from core.projects import banner_templates
        try:
            self.set_fields(banner_templates.apply(self.value, self.template.currentData()))
        except ValueError as error:
            self.note.setText(str(error))

    def save_template(self):
        from PySide6.QtWidgets import QInputDialog
        from core.projects import banner_templates
        t = self.owner.tr_text
        name, ok = QInputDialog.getText(self, t('Zapisz szablon','Save template'),
                                        t('Nazwa szablonu:','Template name:'), text=self.value.name)
        if not ok:
            return
        try:
            banner_templates.save_user(name, self.value)
            self.reload_templates(name.strip())
        except (OSError, ValueError) as error:
            self.note.setText(str(error))

    def delete_template(self):
        from core.projects import banner_templates
        try:
            banner_templates.delete_user(self.template.currentData())
            self.reload_templates()
        except (OSError, ValueError) as error:
            self.note.setText(str(error))

    def choose_color(self, key):
        button = self.fields[key]
        color = QColorDialog.getColor(button.color(), self, options=QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            button.set_color(color); self.update_preview()

    def move_banner(self, x, y):
        self.fields['x'].setValue(x); self.fields['y'].setValue(y)

    def resize_banner(self, width, height):
        self.fields['width'].setValue(width); self.fields['height'].setValue(height)

    def update_preview(self, *args):
        data = asdict(self.value)
        for key, widget in self.fields.items():
            if isinstance(widget, ColorButton): value = widget.value()
            elif isinstance(widget, QPlainTextEdit): value = widget.toPlainText()
            elif isinstance(widget, QLineEdit): value = widget.text()
            elif isinstance(widget, QCheckBox): value = widget.isChecked()
            elif key == 'font': value = widget.currentFont().family()
            elif isinstance(widget, QComboBox): value = widget.currentData()
            else: value = widget.value()
            data[key] = value
        try:
            value = Banner(**data).validate()
        except ValueError as error:
            self.save_button.setEnabled(False)
            self.note.setText(str(error))
            return
        self.save_button.setEnabled(True)
        self.note.setText(self.instructions)
        self.value = value; self.project.banners[self.index] = value
        self.preview.ms = max(value.start, min(self.owner.preview.ms, value.end - 1))
        if value.animation != 'none':
            # Show the settled banner, not the invisible first frame of its entrance.
            self.preview.ms = max(self.preview.ms, min(value.start + value.animation_ms, value.end - 1))
        self.preview.update()

    def accept(self):
        self.update_preview()
        if self.save_button.isEnabled():
            super().accept()
