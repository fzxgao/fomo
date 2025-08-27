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
        # Container widget that holds a label and a scroll area with all numeric
        # parameter widgets.  The scroll area allows the overall panel to be
        # shorter while still exposing all parameters to the user.
        widget = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(widget)
        v.addWidget(QtWidgets.QLabel("Numerical parameters"))

        form_widget = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(form_widget)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        # 1 Iterations
        self.ite_r1 = QtWidgets.QSpinBox()
        self.ite_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.ite_r1.setValue(4)
        _disable_scroll(self.ite_r1)
        form.addRow("Iterations", self.ite_r1)
        # 2 References
        self.nref_r1 = QtWidgets.QSpinBox()
        self.nref_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.nref_r1.setValue(1)
        _disable_scroll(self.nref_r1)
        form.addRow("References", self.nref_r1)
        # 3 Cone Aperture
        self.cone_range_r1 = QtWidgets.QSpinBox()
        self.cone_range_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.cone_range_r1.setValue(45)
        _disable_scroll(self.cone_range_r1)
        form.addRow("Cone Aperture", self.cone_range_r1)
        # 4 Cone Sampling
        self.cone_sampling_r1 = QtWidgets.QSpinBox()
        self.cone_sampling_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.cone_sampling_r1.setValue(15)
        _disable_scroll(self.cone_sampling_r1)
        form.addRow("Cone Sampling", self.cone_sampling_r1)
        # 5 Azimuth Rotation Range
        self.inplane_range_r1 = QtWidgets.QSpinBox()
        self.inplane_range_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.inplane_range_r1.setValue(60)
        _disable_scroll(self.inplane_range_r1)
        form.addRow("Azimuth Rotation Range", self.inplane_range_r1)
        # 6 Azimuth Rotation Sampling
        self.inplane_sampling_r1 = QtWidgets.QSpinBox()
        self.inplane_sampling_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.inplane_sampling_r1.setValue(15)
        _disable_scroll(self.inplane_sampling_r1)
        form.addRow("Azimuth Rotation Sampling", self.inplane_sampling_r1)
        # 7 Refine
        self.refine_r1 = QtWidgets.QSpinBox()
        self.refine_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.refine_r1.setValue(2)
        _disable_scroll(self.refine_r1)
        form.addRow("Refine", self.refine_r1)
        # 8 Refine Factor
        self.refine_factor_r1 = QtWidgets.QSpinBox()
        self.refine_factor_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.refine_factor_r1.setValue(2)
        _disable_scroll(self.refine_factor_r1)
        form.addRow("Refine Factor", self.refine_factor_r1)
        # 9 High Pass
        self.high_r1 = QtWidgets.QSpinBox()
        self.high_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.high_r1.setValue(1)
        _disable_scroll(self.high_r1)
        form.addRow("High Pass", self.high_r1)
        #10 Low Pass
        self.low_r1 = QtWidgets.QSpinBox()
        self.low_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.low_r1.setValue(12)
        _disable_scroll(self.low_r1)
        form.addRow("Low Pass", self.low_r1)
        #11 Symmetry
        self.sym_r1 = QtWidgets.QLineEdit("C1")
        form.addRow("Symmetry", self.sym_r1)
        #12 Particle Dimensions
        self.dim_r1 = QtWidgets.QSpinBox()
        self.dim_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.dim_r1.setValue(52)
        _disable_scroll(self.dim_r1)
        form.addRow("Particle Dimensions", self.dim_r1)
        #13 Shift limits
        shift_widget = QtWidgets.QWidget()
        sh = QtWidgets.QHBoxLayout(shift_widget)
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
        sh.addWidget(self.area_search_r1_x); sh.addWidget(self.area_search_r1_y); sh.addWidget(self.area_search_r1_z)
        form.addRow("Shift limits", shift_widget)
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
        form.addRow("Shift limiting way", self.area_search_modus_r1)
        #15 Separation in Tomogram
        self.separation_in_tomogram_r1 = QtWidgets.QSpinBox()
        self.separation_in_tomogram_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.separation_in_tomogram_r1.setValue(14)
        _disable_scroll(self.separation_in_tomogram_r1)
        form.addRow("Separation in Tomogram", self.separation_in_tomogram_r1)
        #16 Basic MRA
        self.mra_r1 = QtWidgets.QSpinBox()
        self.mra_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.mra_r1.setValue(0)
        _disable_scroll(self.mra_r1)
        form.addRow("Basic MRA", self.mra_r1)
        #17 Threshold parameter
        self.threshold_r1 = QtWidgets.QDoubleSpinBox()
        self.threshold_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.threshold_r1.setValue(0.2)
        _disable_scroll(self.threshold_r1)
        form.addRow("Threshold parameter", self.threshold_r1)
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
        form.addRow("Threshold Mode", self.threshold_mode)
        #19 Exclusion Mode
        self.exclusion_mode = QtWidgets.QComboBox()
        self.exclusion_mode.addItems([
            "No exclusion from averaging and alignment",
            "Exclusion from averaging and alignment",
        ])
        self.exclusion_mode.setCurrentText("No exclusion from averaging and alignment")
        _disable_scroll(self.exclusion_mode)
        form.addRow("Exclusion Mode", self.exclusion_mode)

        # Ensure text inputs and dropdowns expand to the panel width
        growing = form_widget.findChildren(
            (QtWidgets.QLineEdit, QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QComboBox)
        )
        for w in growing:
            if w in (
                self.area_search_r1_x,
                self.area_search_r1_y,
                self.area_search_r1_z,
            ):
                continue
            if isinstance(w, QtWidgets.QComboBox):
                w.setMinimumContentsLength(0)
                w.setSizeAdjustPolicy(
                    QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon
                )
            w.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        scroll = QtWidgets.QScrollArea()
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidget(form_widget)
        v.addWidget(scroll)

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