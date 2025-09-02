from PyQt5 import QtCore, QtWidgets

def _disable_scroll(widget):
    """Prevent mouse wheel events from altering widget value."""
    widget.wheelEvent = lambda event: event.ignore()


def _link_slider_wheel(label: QtWidgets.QLabel, slider: QtWidgets.QSlider):
    """Allow scrolling over ``label`` to move ``slider`` one step."""
    def wheel_event(event):
        delta = event.angleDelta().y()
        if delta > 0:
            slider.setValue(min(slider.maximum(), slider.value() + 1))
        elif delta < 0:
            slider.setValue(max(slider.minimum(), slider.value() - 1))
        event.accept()

    label.wheelEvent = wheel_event


class RefinementSidePanel(QtWidgets.QSplitter):
    """Side panel shown in normal mode with refinement tools."""

    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Vertical, *args, **kwargs)
        self._build_initial_avg_section()
        self._build_numeric_params_section()
        self._build_live_refinement_section()

    # -------- Initial averaging --------
    def _build_initial_avg_section(self):
        widget = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(widget)
        v.addWidget(QtWidgets.QLabel("Initial averaging"))
        hl = QtWidgets.QHBoxLayout()
        self.initial_avg_views = []
        self.initial_avg_sliders = []
        for axis in ("X", "Y", "Z"):
            vb = QtWidgets.QVBoxLayout()
            label = QtWidgets.QLabel(f"{axis}")
            label.setFrameShape(QtWidgets.QFrame.Box)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setFixedSize(60, 60)
            self.initial_avg_views.append(label)
            vb.addWidget(label)
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.initial_avg_sliders.append(slider)
            vb.addWidget(slider)
            _link_slider_wheel(label, slider)
            hl.addLayout(vb)
        v.addLayout(hl)
        btns = QtWidgets.QHBoxLayout()
        self.calc_initial_left = QtWidgets.QToolButton()
        self.calc_initial_left.setArrowType(QtCore.Qt.LeftArrow)
        btns.addWidget(self.calc_initial_left)
        self.calc_initial_btn = QtWidgets.QPushButton("Calculate initial average")
        btns.addWidget(self.calc_initial_btn)
        self.calc_initial_right = QtWidgets.QToolButton()
        self.calc_initial_right.setArrowType(QtCore.Qt.RightArrow)
        btns.addWidget(self.calc_initial_right)
        v.addLayout(btns)
        self.addWidget(widget)

    # -------- Numerical parameters --------
    def _build_numeric_params_section(self):
        # Container widget that holds a label and a tab widget with the
        # numeric parameter widgets for two rounds.
        widget = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(widget)
        v.addWidget(QtWidgets.QLabel("Numerical parameters"))

        tabs = QtWidgets.QTabWidget()
        v.addWidget(tabs)

        # ----- Round 1 tab -----
        r1_tab = QtWidgets.QWidget()
        r1_v = QtWidgets.QVBoxLayout(r1_tab)

        r1_form_widget = QtWidgets.QWidget()
        r1_form = QtWidgets.QFormLayout(r1_form_widget)
        r1_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldsStayAtSizeHint)
        r1_form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        r1_form.setHorizontalSpacing(4)
        r1_form.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        r1_form.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

        # 1 Iterations
        self.ite_r1 = QtWidgets.QSpinBox()
        self.ite_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.ite_r1.setValue(8)
        _disable_scroll(self.ite_r1)
        r1_form.addRow("Iterations", self.ite_r1)
        # 2 References
        self.nref_r1 = QtWidgets.QSpinBox()
        self.nref_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.nref_r1.setValue(1)
        _disable_scroll(self.nref_r1)
        r1_form.addRow("References", self.nref_r1)
        # 3 Cone Aperture
        self.cone_range_r1 = QtWidgets.QSpinBox()
        self.cone_range_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.cone_range_r1.setValue(45)
        _disable_scroll(self.cone_range_r1)
        r1_form.addRow("Cone Aperture", self.cone_range_r1)
        # 4 Cone Sampling
        self.cone_sampling_r1 = QtWidgets.QSpinBox()
        self.cone_sampling_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.cone_sampling_r1.setValue(15)
        _disable_scroll(self.cone_sampling_r1)
        r1_form.addRow("Cone Sampling", self.cone_sampling_r1)
        # 5 Azimuth Rotation Range
        self.inplane_range_r1 = QtWidgets.QSpinBox()
        self.inplane_range_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.inplane_range_r1.setValue(60)
        _disable_scroll(self.inplane_range_r1)
        r1_form.addRow("Azimuth Rotation Range", self.inplane_range_r1)
        # 6 Azimuth Rotation Sampling
        self.inplane_sampling_r1 = QtWidgets.QSpinBox()
        self.inplane_sampling_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.inplane_sampling_r1.setValue(15)
        _disable_scroll(self.inplane_sampling_r1)
        r1_form.addRow("Azimuth Rotation Sampling", self.inplane_sampling_r1)
        # 7 Refine
        self.refine_r1 = QtWidgets.QSpinBox()
        self.refine_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.refine_r1.setValue(2)
        _disable_scroll(self.refine_r1)
        r1_form.addRow("Refine", self.refine_r1)
        # 8 Refine Factor
        self.refine_factor_r1 = QtWidgets.QSpinBox()
        self.refine_factor_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.refine_factor_r1.setValue(2)
        _disable_scroll(self.refine_factor_r1)
        r1_form.addRow("Refine Factor", self.refine_factor_r1)
        # 9 High Pass
        self.high_r1 = QtWidgets.QSpinBox()
        self.high_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.high_r1.setValue(1)
        _disable_scroll(self.high_r1)
        r1_form.addRow("High Pass", self.high_r1)
        #10 Low Pass
        self.low_r1 = QtWidgets.QSpinBox()
        self.low_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.low_r1.setValue(12)
        _disable_scroll(self.low_r1)
        r1_form.addRow("Low Pass", self.low_r1)
        #11 Symmetry
        self.sym_r1 = QtWidgets.QLineEdit("C1")
        r1_form.addRow("Symmetry", self.sym_r1)
        #12 Particle Dimensions
        self.dim_r1 = QtWidgets.QSpinBox()
        self.dim_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.dim_r1.setValue(52)
        _disable_scroll(self.dim_r1)
        r1_form.addRow("Particle Dimensions", self.dim_r1)
        #13 Shift limits
        r1_shift_widget = QtWidgets.QWidget()
        r1_sh = QtWidgets.QHBoxLayout(r1_shift_widget)
        self.area_search_r1_x = QtWidgets.QSpinBox()
        self.area_search_r1_x.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r1_x.setValue(4)
        self.area_search_r1_x.setMinimumWidth(30)
        _disable_scroll(self.area_search_r1_x)
        self.area_search_r1_y = QtWidgets.QSpinBox()
        self.area_search_r1_y.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r1_y.setValue(4)
        self.area_search_r1_y.setMinimumWidth(30)
        _disable_scroll(self.area_search_r1_y)
        self.area_search_r1_z = QtWidgets.QSpinBox()
        self.area_search_r1_z.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r1_z.setValue(8)
        self.area_search_r1_z.setMinimumWidth(30)
        _disable_scroll(self.area_search_r1_z)
        r1_sh.addWidget(self.area_search_r1_x); r1_sh.addWidget(self.area_search_r1_y); r1_sh.addWidget(self.area_search_r1_z)
        r1_form.addRow("Shift limits", r1_shift_widget)
        #14 Shift limiting way
        self.area_search_modus_r1 = QtWidgets.QComboBox()
        self.area_search_modus_r1.addItems([
            "No limitations",
            "From the center of the particle cube",
            "From the previous estimation on the particle position",
            "From the estimation provided for the first iteration, with static origin",
        ])
        self.area_search_modus_r1.setCurrentText("From the center of the particle cube")
        _disable_scroll(self.area_search_modus_r1)
        r1_form.addRow("Shift limiting way", self.area_search_modus_r1)
        #15 Separation in Tomogram
        self.separation_in_tomogram_r1 = QtWidgets.QSpinBox()
        self.separation_in_tomogram_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.separation_in_tomogram_r1.setValue(0)
        _disable_scroll(self.separation_in_tomogram_r1)
        r1_form.addRow("Separation in Tomogram", self.separation_in_tomogram_r1)
        #16 Basic MRA
        self.mra_r1 = QtWidgets.QSpinBox()
        self.mra_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.mra_r1.setValue(0)
        _disable_scroll(self.mra_r1)
        r1_form.addRow("Basic MRA", self.mra_r1)
        #17 Threshold parameter
        self.threshold_r1 = QtWidgets.QDoubleSpinBox()
        self.threshold_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.threshold_r1.setValue(0.2)
        _disable_scroll(self.threshold_r1)
        r1_form.addRow("Threshold parameter", self.threshold_r1)
        #18 Threshold Mode
        self.threshold_mode = QtWidgets.QComboBox()
        self.threshold_mode.addItems([
            "no thresholding policy",
            "Threshold is an absolute threshold (only particles with CC above this value are selected).",
            "Effective threshold = mean(CC) * THRESHOLD.",
            "Effective threshold = mean(CC) +std(CC)*THRESHOLD.",
            "Threshold is the total number of particles (ordered by CC ).",
            "Threshold ranges between 0 and 1  and sets the fraction of particles.",
        ])
        self.threshold_mode.setCurrentText("no thresholding policy")
        _disable_scroll(self.threshold_mode)
        r1_form.addRow("Threshold Mode", self.threshold_mode)
        #19 Exclusion Mode
        self.exclusion_mode = QtWidgets.QComboBox()
        self.exclusion_mode.addItems([
            "No exclusion from averaging and alignment",
            "Exclusion from averaging and alignment",
        ])
        self.exclusion_mode.setCurrentText("No exclusion from averaging and alignment")
        _disable_scroll(self.exclusion_mode)
        r1_form.addRow("Exclusion Mode", self.exclusion_mode)

        # Ensure text inputs and dropdowns expand to the panel width
        r1_growing = r1_form_widget.findChildren(
            (QtWidgets.QLineEdit, QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QComboBox)
        )
        for w in r1_growing:
            if w in (
                self.area_search_r1_x,
                self.area_search_r1_y,
                self.area_search_r1_z,
            ):
                continue
            if isinstance(w, QtWidgets.QComboBox):
                w.setMinimumContentsLength(0)
                w.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
            # Make inputs narrower and keep them close to labels
            w.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            if isinstance(w, QtWidgets.QLineEdit):
                w.setMaximumWidth(200)
            else:
                w.setMaximumWidth(250)
            # Enable label word wrap to avoid overlap
            lbl = r1_form.labelForField(w)
            if isinstance(lbl, QtWidgets.QLabel):
                lbl.setWordWrap(True)

        r1_scroll = QtWidgets.QScrollArea()
        r1_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        r1_scroll.setWidgetResizable(True)
        r1_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        r1_scroll.setWidget(r1_form_widget)
        r1_v.addWidget(r1_scroll)
        tabs.addTab(r1_tab, "Round 1")

        # ----- Round 2 tab -----
        r2_tab = QtWidgets.QWidget()
        r2_v = QtWidgets.QVBoxLayout(r2_tab)

        r2_form_widget = QtWidgets.QWidget()
        r2_form = QtWidgets.QFormLayout(r2_form_widget)
        r2_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldsStayAtSizeHint)
        r2_form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        r2_form.setHorizontalSpacing(4)
        r2_form.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        r2_form.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

        # 1 Iterations
        self.ite_r2 = QtWidgets.QSpinBox()
        self.ite_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.ite_r2.setValue(8)
        _disable_scroll(self.ite_r2)
        r2_form.addRow("Iterations", self.ite_r2)
        # 2 References
        self.nref_r2 = QtWidgets.QSpinBox()
        self.nref_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.nref_r2.setValue(1)
        _disable_scroll(self.nref_r2)
        r2_form.addRow("References", self.nref_r2)
        # 3 Cone Aperture
        self.cone_range_r2 = QtWidgets.QSpinBox()
        self.cone_range_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.cone_range_r2.setValue(45)
        _disable_scroll(self.cone_range_r2)
        r2_form.addRow("Cone Aperture", self.cone_range_r2)
        # 4 Cone Sampling
        self.cone_sampling_r2 = QtWidgets.QSpinBox()
        self.cone_sampling_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.cone_sampling_r2.setValue(15)
        _disable_scroll(self.cone_sampling_r2)
        r2_form.addRow("Cone Sampling", self.cone_sampling_r2)
        # 5 Azimuth Rotation Range
        self.inplane_range_r2 = QtWidgets.QSpinBox()
        self.inplane_range_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.inplane_range_r2.setValue(60)
        _disable_scroll(self.inplane_range_r2)
        r2_form.addRow("Azimuth Rotation Range", self.inplane_range_r2)
        # 6 Azimuth Rotation Sampling
        self.inplane_sampling_r2 = QtWidgets.QSpinBox()
        self.inplane_sampling_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.inplane_sampling_r2.setValue(15)
        _disable_scroll(self.inplane_sampling_r2)
        r2_form.addRow("Azimuth Rotation Sampling", self.inplane_sampling_r2)
        # 7 Refine
        self.refine_r2 = QtWidgets.QSpinBox()
        self.refine_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.refine_r2.setValue(2)
        _disable_scroll(self.refine_r2)
        r2_form.addRow("Refine", self.refine_r2)
        # 8 Refine Factor
        self.refine_factor_r2 = QtWidgets.QSpinBox()
        self.refine_factor_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.refine_factor_r2.setValue(2)
        _disable_scroll(self.refine_factor_r2)
        r2_form.addRow("Refine Factor", self.refine_factor_r2)
        # 9 High Pass
        self.high_r2 = QtWidgets.QSpinBox()
        self.high_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.high_r2.setValue(1)
        _disable_scroll(self.high_r2)
        r2_form.addRow("High Pass", self.high_r2)
        #10 Low Pass
        self.low_r2 = QtWidgets.QSpinBox()
        self.low_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.low_r2.setValue(12)
        _disable_scroll(self.low_r2)
        r2_form.addRow("Low Pass", self.low_r2)
        #11 Symmetry
        self.sym_r2 = QtWidgets.QLineEdit("C1")
        r2_form.addRow("Symmetry", self.sym_r2)
        #12 Particle Dimensions
        self.dim_r2 = QtWidgets.QSpinBox()
        self.dim_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.dim_r2.setValue(52)
        _disable_scroll(self.dim_r2)
        r2_form.addRow("Particle Dimensions", self.dim_r2)
        #13 Shift limits
        r2_shift_widget = QtWidgets.QWidget()
        r2_sh = QtWidgets.QHBoxLayout(r2_shift_widget)
        self.area_search_r2_x = QtWidgets.QSpinBox()
        self.area_search_r2_x.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r2_x.setValue(4)
        self.area_search_r2_x.setMinimumWidth(30)
        _disable_scroll(self.area_search_r2_x)
        self.area_search_r2_y = QtWidgets.QSpinBox()
        self.area_search_r2_y.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r2_y.setValue(4)
        self.area_search_r2_y.setMinimumWidth(30)
        _disable_scroll(self.area_search_r2_y)
        self.area_search_r2_z = QtWidgets.QSpinBox()
        self.area_search_r2_z.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r2_z.setValue(8)
        self.area_search_r2_z.setMinimumWidth(30)
        _disable_scroll(self.area_search_r2_z)
        r2_sh.addWidget(self.area_search_r2_x); r2_sh.addWidget(self.area_search_r2_y); r2_sh.addWidget(self.area_search_r2_z)
        r2_form.addRow("Shift limits", r2_shift_widget)
        #14 Shift limiting way
        self.area_search_modus_r2 = QtWidgets.QComboBox()
        self.area_search_modus_r2.addItems([
            "No limitations",
            "From the center of the particle cube",
            "From the previous estimation on the particle position",
            "From the estimation provided for the first iteration, with static origin",
        ])
        self.area_search_modus_r2.setCurrentText("From the center of the particle cube")
        _disable_scroll(self.area_search_modus_r2)
        r2_form.addRow("Shift limiting way", self.area_search_modus_r2)
        #15 Separation in Tomogram
        self.separation_in_tomogram_r2 = QtWidgets.QSpinBox()
        self.separation_in_tomogram_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.separation_in_tomogram_r2.setValue(0)
        _disable_scroll(self.separation_in_tomogram_r2)
        r2_form.addRow("Separation in Tomogram", self.separation_in_tomogram_r2)
        #16 Basic MRA
        self.mra_r2 = QtWidgets.QSpinBox()
        self.mra_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.mra_r2.setValue(0)
        _disable_scroll(self.mra_r2)
        r2_form.addRow("Basic MRA", self.mra_r2)
        #17 Threshold parameter
        self.threshold_r2 = QtWidgets.QDoubleSpinBox()
        self.threshold_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.threshold_r2.setValue(0.2)
        _disable_scroll(self.threshold_r2)
        r2_form.addRow("Threshold parameter", self.threshold_r2)
        #18 Threshold Mode
        self.threshold_mode_r2 = QtWidgets.QComboBox()
        self.threshold_mode_r2.addItems([
            "no thresholding policy",
            "Threshold is an absolute threshold (only particles with CC above this value are selected).",
            "Effective threshold = mean(CC) * THRESHOLD.",
            "Effective threshold = mean(CC) +std(CC)*THRESHOLD.",
            "Threshold is the total number of particles (ordered by CC ).",
            "Threshold ranges between 0 and 1  and sets the fraction of particles.",
        ])
        self.threshold_mode_r2.setCurrentText("no thresholding policy")
        _disable_scroll(self.threshold_mode_r2)
        r2_form.addRow("Threshold Mode", self.threshold_mode_r2)
        #19 Exclusion Mode
        self.exclusion_mode_r2 = QtWidgets.QComboBox()
        self.exclusion_mode_r2.addItems([
            "No exclusion from averaging and alignment",
            "Exclusion from averaging and alignment",
        ])
        self.exclusion_mode_r2.setCurrentText("No exclusion from averaging and alignment")
        _disable_scroll(self.exclusion_mode_r2)
        r2_form.addRow("Exclusion Mode", self.exclusion_mode_r2)

        # Ensure text inputs and dropdowns expand to the panel width
        r2_growing = r2_form_widget.findChildren(
            (QtWidgets.QLineEdit, QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QComboBox)
        )
        for w in r2_growing:
            if w in (
                self.area_search_r2_x,
                self.area_search_r2_y,
                self.area_search_r2_z,
            ):
                continue
            if isinstance(w, QtWidgets.QComboBox):
                w.setMinimumContentsLength(0)
                w.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
            # Make inputs narrower and keep them close to labels
            w.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            if isinstance(w, QtWidgets.QLineEdit):
                w.setMaximumWidth(200)
            else:
                w.setMaximumWidth(250)
            # Enable label word wrap to avoid overlap
            lbl = r2_form.labelForField(w)
            if isinstance(lbl, QtWidgets.QLabel):
                lbl.setWordWrap(True)

        r2_scroll = QtWidgets.QScrollArea()
        r2_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        r2_scroll.setWidgetResizable(True)
        r2_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        r2_scroll.setWidget(r2_form_widget)
        r2_v.addWidget(r2_scroll)
        tabs.addTab(r2_tab, "Round 2")

        self.addWidget(widget)

    # -------- Live refinement --------
    def _build_live_refinement_section(self):
        widget = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(widget)
        v.addWidget(QtWidgets.QLabel("Live refinement"))
        hl = QtWidgets.QHBoxLayout()
        self.refined_views = []
        self.refined_sliders = []
        for axis in ("X", "Y", "Z"):
            vb = QtWidgets.QVBoxLayout()
            label = QtWidgets.QLabel(f"{axis}")
            label.setFrameShape(QtWidgets.QFrame.Box)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setFixedSize(60, 60)
            self.refined_views.append(label)
            vb.addWidget(label)
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.refined_sliders.append(slider)
            vb.addWidget(slider)
            _link_slider_wheel(label, slider)
            hl.addLayout(vb)
        v.addLayout(hl)
        btns = QtWidgets.QVBoxLayout()
        import_row = QtWidgets.QHBoxLayout()
        self.import_left = QtWidgets.QToolButton()
        self.import_left.setArrowType(QtCore.Qt.LeftArrow)
        import_row.addWidget(self.import_left)
        self.import_btn = QtWidgets.QPushButton("Import refined coordinates")
        import_row.addWidget(self.import_btn)
        self.import_right = QtWidgets.QToolButton()
        self.import_right.setArrowType(QtCore.Qt.RightArrow)
        import_row.addWidget(self.import_right)
        btns.addLayout(import_row)
        self.ransac_btn = QtWidgets.QPushButton("Run RANSAC")
        btns.addWidget(self.ransac_btn)
        self.export_relion_btn = QtWidgets.QPushButton("Export to RELION")
        btns.addWidget(self.export_relion_btn)
        v.addLayout(btns)
        self.addWidget(widget)

    def wheelEvent(self, event):
        event.ignore()
