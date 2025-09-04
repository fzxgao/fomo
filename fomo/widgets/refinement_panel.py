from PyQt5 import QtCore, QtWidgets
from fomo.widgets.subboxing import SubboxingWidget

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
    """Side panel shown in normal mode with tabs for processing and subboxing."""

    def __init__(self, *args, verbose=False, **kwargs):
        super().__init__(QtCore.Qt.Vertical, *args, **kwargs)
        tabs = QtWidgets.QTabWidget()
        # Processing tab contains the original three sections in a splitter
        self._proc_split = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self._proc_split.addWidget(self._build_initial_avg_section())
        self._proc_split.addWidget(self._build_numeric_params_section())
        self._proc_split.addWidget(self._build_live_refinement_section())
        tabs.addTab(self._proc_split, "Processing")

        # Subboxing tab
        self.subboxing = SubboxingWidget(verbose=verbose)
        tabs.addTab(self.subboxing, "Subboxing")

        self.addWidget(tabs)

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
        return widget

    # -------- Numerical parameters --------
    def _build_numeric_params_section(self):
        # Container widget that holds a label and a tabbed area with all
        # numeric parameter widgets split into Round 1 and Round 2.
        widget = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(widget)
        v.addWidget(QtWidgets.QLabel("Numerical parameters"))
        tabs = QtWidgets.QTabWidget()

        def _wrap_label(text: str) -> QtWidgets.QLabel:
            lbl = QtWidgets.QLabel(text)
            lbl.setWordWrap(True)
            lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            lbl.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
            return lbl

        # ----- Round 1 -----
        form_widget_r1 = QtWidgets.QWidget()
        form_r1 = QtWidgets.QFormLayout(form_widget_r1)
        form_r1.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        # 1 Iterations
        self.ite_r1 = QtWidgets.QSpinBox()
        self.ite_r1.setMaximum(1000000)
        self.ite_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.ite_r1.setValue(8)
        _disable_scroll(self.ite_r1)
        form_r1.addRow(_wrap_label("Iterations"), self.ite_r1)
        # 2 References
        self.nref_r1 = QtWidgets.QSpinBox()
        self.nref_r1.setMaximum(1000000)
        self.nref_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.nref_r1.setValue(1)
        _disable_scroll(self.nref_r1)
        form_r1.addRow(_wrap_label("References"), self.nref_r1)
        # 3 Cone Aperture
        self.cone_range_r1 = QtWidgets.QSpinBox()
        self.cone_range_r1.setMaximum(1000000)
        self.cone_range_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.cone_range_r1.setValue(45)
        _disable_scroll(self.cone_range_r1)
        form_r1.addRow(_wrap_label("Cone Aperture"), self.cone_range_r1)
        # 4 Cone Sampling
        self.cone_sampling_r1 = QtWidgets.QSpinBox()
        self.cone_sampling_r1.setMaximum(1000000)
        self.cone_sampling_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.cone_sampling_r1.setValue(15)
        _disable_scroll(self.cone_sampling_r1)
        form_r1.addRow(_wrap_label("Cone Sampling"), self.cone_sampling_r1)
        # 5 Azimuth Rotation Range
        self.inplane_range_r1 = QtWidgets.QSpinBox()
        self.inplane_range_r1.setMaximum(1000000)
        self.inplane_range_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.inplane_range_r1.setValue(60)
        _disable_scroll(self.inplane_range_r1)
        form_r1.addRow(_wrap_label("Azimuth Rotation Range"), self.inplane_range_r1)
        # 6 Azimuth Rotation Sampling
        self.inplane_sampling_r1 = QtWidgets.QSpinBox()
        self.inplane_sampling_r1.setMaximum(1000000)
        self.inplane_sampling_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.inplane_sampling_r1.setValue(15)
        _disable_scroll(self.inplane_sampling_r1)
        form_r1.addRow(_wrap_label("Azimuth Rotation Sampling"), self.inplane_sampling_r1)
        # 7 Refine
        self.refine_r1 = QtWidgets.QSpinBox()
        self.refine_r1.setMaximum(1000000)
        self.refine_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.refine_r1.setValue(2)
        _disable_scroll(self.refine_r1)
        form_r1.addRow(_wrap_label("Refine"), self.refine_r1)
        # 8 Refine Factor
        self.refine_factor_r1 = QtWidgets.QSpinBox()
        self.refine_factor_r1.setMaximum(1000000)
        self.refine_factor_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.refine_factor_r1.setValue(2)
        _disable_scroll(self.refine_factor_r1)
        form_r1.addRow(_wrap_label("Refine Factor"), self.refine_factor_r1)
        # 9 High Pass
        self.high_r1 = QtWidgets.QSpinBox()
        self.high_r1.setMaximum(1000000)
        self.high_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.high_r1.setValue(1)
        _disable_scroll(self.high_r1)
        form_r1.addRow(_wrap_label("High Pass"), self.high_r1)
        #10 Low Pass
        self.low_r1 = QtWidgets.QSpinBox()
        self.low_r1.setMaximum(1000000)
        self.low_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.low_r1.setValue(12)
        _disable_scroll(self.low_r1)
        form_r1.addRow(_wrap_label("Low Pass"), self.low_r1)
        #11 Symmetry
        self.sym_r1 = QtWidgets.QLineEdit("C1")
        form_r1.addRow(_wrap_label("Symmetry"), self.sym_r1)
        #12 Particle Dimensions
        self.dim_r1 = QtWidgets.QSpinBox()
        self.dim_r1.setMaximum(1000000)
        self.dim_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.dim_r1.setValue(52)
        _disable_scroll(self.dim_r1)
        form_r1.addRow(_wrap_label("Particle Dimensions"), self.dim_r1)
        #13 Shift limits
        shift_widget_r1 = QtWidgets.QWidget()
        sh1 = QtWidgets.QHBoxLayout(shift_widget_r1)
        self.area_search_r1_x = QtWidgets.QSpinBox()
        self.area_search_r1_x.setMaximum(1000000)
        self.area_search_r1_x.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r1_x.setValue(4)
        self.area_search_r1_x.setMinimumWidth(30)
        _disable_scroll(self.area_search_r1_x)
        self.area_search_r1_y = QtWidgets.QSpinBox()
        self.area_search_r1_y.setMaximum(1000000)
        self.area_search_r1_y.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r1_y.setValue(4)
        self.area_search_r1_y.setMinimumWidth(30)
        _disable_scroll(self.area_search_r1_y)
        self.area_search_r1_z = QtWidgets.QSpinBox()
        self.area_search_r1_z.setMaximum(1000000)
        self.area_search_r1_z.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r1_z.setValue(8)
        self.area_search_r1_z.setMinimumWidth(30)
        _disable_scroll(self.area_search_r1_z)
        sh1.addWidget(self.area_search_r1_x); sh1.addWidget(self.area_search_r1_y); sh1.addWidget(self.area_search_r1_z)
        form_r1.addRow(_wrap_label("Shift limits"), shift_widget_r1)
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
        form_r1.addRow(_wrap_label("Shift limiting way"), self.area_search_modus_r1)
        #15 Separation in Tomogram
        self.separation_in_tomogram_r1 = QtWidgets.QSpinBox()
        self.separation_in_tomogram_r1.setMaximum(1000000)
        self.separation_in_tomogram_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.separation_in_tomogram_r1.setValue(0)
        _disable_scroll(self.separation_in_tomogram_r1)
        form_r1.addRow(_wrap_label("Separation in Tomogram"), self.separation_in_tomogram_r1)
        #16 Basic MRA
        self.mra_r1 = QtWidgets.QSpinBox()
        self.mra_r1.setMaximum(1000000)
        self.mra_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.mra_r1.setValue(0)
        _disable_scroll(self.mra_r1)
        form_r1.addRow(_wrap_label("Basic MRA"), self.mra_r1)
        #17 Threshold parameter
        self.threshold_r1 = QtWidgets.QDoubleSpinBox()
        self.threshold_r1.setMaximum(1000000.0)
        self.threshold_r1.setDecimals(6)
        self.threshold_r1.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.threshold_r1.setValue(0.2)
        _disable_scroll(self.threshold_r1)
        form_r1.addRow(_wrap_label("Threshold parameter"), self.threshold_r1)
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
        form_r1.addRow(_wrap_label("Threshold Mode"), self.threshold_mode)
        #19 Exclusion Mode
        self.exclusion_mode = QtWidgets.QComboBox()
        self.exclusion_mode.addItems([
            "No exclusion from averaging and alignment",
            "Exclusion from averaging and alignment",
        ])
        self.exclusion_mode.setCurrentText("No exclusion from averaging and alignment")
        _disable_scroll(self.exclusion_mode)
        form_r1.addRow(_wrap_label("Exclusion Mode"), self.exclusion_mode)

        # Ensure text inputs and dropdowns expand to the panel width (R1)
        growing_r1 = form_widget_r1.findChildren(
            (QtWidgets.QLineEdit, QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QComboBox)
        )
        for w in growing_r1:
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

        scroll_r1 = QtWidgets.QScrollArea()
        scroll_r1.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_r1.setWidgetResizable(True)
        scroll_r1.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll_r1.setWidget(form_widget_r1)
        tabs.addTab(scroll_r1, "Round 1")

        # ----- Round 2 -----
        form_widget_r2 = QtWidgets.QWidget()
        form_r2 = QtWidgets.QFormLayout(form_widget_r2)
        form_r2.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        # 1 Iterations
        self.ite_r2 = QtWidgets.QSpinBox()
        self.ite_r2.setMaximum(1000000)
        self.ite_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.ite_r2.setValue(1)
        _disable_scroll(self.ite_r2)
        form_r2.addRow(_wrap_label("Iterations"), self.ite_r2)
        # 2 References
        self.nref_r2 = QtWidgets.QSpinBox()
        self.nref_r2.setMaximum(1000000)
        self.nref_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.nref_r2.setValue(1)
        _disable_scroll(self.nref_r2)
        form_r2.addRow(_wrap_label("References"), self.nref_r2)
        # 3 Cone Aperture
        self.cone_range_r2 = QtWidgets.QSpinBox()
        self.cone_range_r2.setMaximum(1000000)
        self.cone_range_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.cone_range_r2.setValue(0)
        _disable_scroll(self.cone_range_r2)
        form_r2.addRow(_wrap_label("Cone Aperture"), self.cone_range_r2)
        # 4 Cone Sampling
        self.cone_sampling_r2 = QtWidgets.QSpinBox()
        self.cone_sampling_r2.setMaximum(1000000)
        self.cone_sampling_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.cone_sampling_r2.setValue(0)
        _disable_scroll(self.cone_sampling_r2)
        form_r2.addRow(_wrap_label("Cone Sampling"), self.cone_sampling_r2)
        # 5 Azimuth Rotation Range
        self.inplane_range_r2 = QtWidgets.QSpinBox()
        self.inplane_range_r2.setMaximum(1000000)
        self.inplane_range_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.inplane_range_r2.setValue(0)
        _disable_scroll(self.inplane_range_r2)
        form_r2.addRow(_wrap_label("Azimuth Rotation Range"), self.inplane_range_r2)
        # 6 Azimuth Rotation Sampling
        self.inplane_sampling_r2 = QtWidgets.QSpinBox()
        self.inplane_sampling_r2.setMaximum(1000000)
        self.inplane_sampling_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.inplane_sampling_r2.setValue(0)
        _disable_scroll(self.inplane_sampling_r2)
        form_r2.addRow(_wrap_label("Azimuth Rotation Sampling"), self.inplane_sampling_r2)
        # 7 Refine
        self.refine_r2 = QtWidgets.QSpinBox()
        self.refine_r2.setMaximum(1000000)
        self.refine_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.refine_r2.setValue(2)
        _disable_scroll(self.refine_r2)
        form_r2.addRow(_wrap_label("Refine"), self.refine_r2)
        # 8 Refine Factor
        self.refine_factor_r2 = QtWidgets.QSpinBox()
        self.refine_factor_r2.setMaximum(1000000)
        self.refine_factor_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.refine_factor_r2.setValue(2)
        _disable_scroll(self.refine_factor_r2)
        form_r2.addRow(_wrap_label("Refine Factor"), self.refine_factor_r2)
        # 9 High Pass
        self.high_r2 = QtWidgets.QSpinBox()
        self.high_r2.setMaximum(1000000)
        self.high_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.high_r2.setValue(1)
        _disable_scroll(self.high_r2)
        form_r2.addRow(_wrap_label("High Pass"), self.high_r2)
        #10 Low Pass
        self.low_r2 = QtWidgets.QSpinBox()
        self.low_r2.setMaximum(1000000)
        self.low_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.low_r2.setValue(12)
        _disable_scroll(self.low_r2)
        form_r2.addRow(_wrap_label("Low Pass"), self.low_r2)
        #11 Symmetry
        self.sym_r2 = QtWidgets.QLineEdit("C1")
        form_r2.addRow(_wrap_label("Symmetry"), self.sym_r2)
        #12 Particle Dimensions
        self.dim_r2 = QtWidgets.QSpinBox()
        self.dim_r2.setMaximum(1000000)
        self.dim_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.dim_r2.setValue(52)
        _disable_scroll(self.dim_r2)
        form_r2.addRow(_wrap_label("Particle Dimensions"), self.dim_r2)
        #13 Shift limits
        shift_widget_r2 = QtWidgets.QWidget()
        sh2 = QtWidgets.QHBoxLayout(shift_widget_r2)
        self.area_search_r2_x = QtWidgets.QSpinBox()
        self.area_search_r2_x.setMaximum(1000000)
        self.area_search_r2_x.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r2_x.setValue(0)
        self.area_search_r2_x.setMinimumWidth(30)
        _disable_scroll(self.area_search_r2_x)
        self.area_search_r2_y = QtWidgets.QSpinBox()
        self.area_search_r2_y.setMaximum(1000000)
        self.area_search_r2_y.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r2_y.setValue(0)
        self.area_search_r2_y.setMinimumWidth(30)
        _disable_scroll(self.area_search_r2_y)
        self.area_search_r2_z = QtWidgets.QSpinBox()
        self.area_search_r2_z.setMaximum(1000000)
        self.area_search_r2_z.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r2_z.setValue(0)
        self.area_search_r2_z.setMinimumWidth(30)
        _disable_scroll(self.area_search_r2_z)
        sh2.addWidget(self.area_search_r2_x); sh2.addWidget(self.area_search_r2_y); sh2.addWidget(self.area_search_r2_z)
        form_r2.addRow(_wrap_label("Shift limits"), shift_widget_r2)
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
        form_r2.addRow(_wrap_label("Shift limiting way"), self.area_search_modus_r2)
        #15 Separation in Tomogram
        self.separation_in_tomogram_r2 = QtWidgets.QSpinBox()
        self.separation_in_tomogram_r2.setMaximum(1000000)
        self.separation_in_tomogram_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.separation_in_tomogram_r2.setValue(7)
        _disable_scroll(self.separation_in_tomogram_r2)
        form_r2.addRow(_wrap_label("Separation in Tomogram"), self.separation_in_tomogram_r2)
        #16 Basic MRA
        self.mra_r2 = QtWidgets.QSpinBox()
        self.mra_r2.setMaximum(1000000)
        self.mra_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.mra_r2.setValue(0)
        _disable_scroll(self.mra_r2)
        form_r2.addRow(_wrap_label("Basic MRA"), self.mra_r2)
        #17 Threshold parameter
        self.threshold_r2 = QtWidgets.QDoubleSpinBox()
        self.threshold_r2.setMaximum(1000000.0)
        self.threshold_r2.setDecimals(6)
        self.threshold_r2.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.threshold_r2.setValue(0.2)
        _disable_scroll(self.threshold_r2)
        form_r2.addRow(_wrap_label("Threshold parameter"), self.threshold_r2)
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
        form_r2.addRow(_wrap_label("Threshold Mode"), self.threshold_mode_r2)
        #19 Exclusion Mode
        self.exclusion_mode_r2 = QtWidgets.QComboBox()
        self.exclusion_mode_r2.addItems([
            "No exclusion from averaging and alignment",
            "Exclusion from averaging and alignment",
        ])
        self.exclusion_mode_r2.setCurrentText("No exclusion from averaging and alignment")
        _disable_scroll(self.exclusion_mode_r2)
        form_r2.addRow(_wrap_label("Exclusion Mode"), self.exclusion_mode_r2)

        # Ensure text inputs and dropdowns expand to the panel width (R2)
        growing_r2 = form_widget_r2.findChildren(
            (QtWidgets.QLineEdit, QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QComboBox)
        )
        for w in growing_r2:
            if w in (
                self.area_search_r2_x,
                self.area_search_r2_y,
                self.area_search_r2_z,
            ):
                continue
            if isinstance(w, QtWidgets.QComboBox):
                w.setMinimumContentsLength(0)
                w.setSizeAdjustPolicy(
                    QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon
                )
            w.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        scroll_r2 = QtWidgets.QScrollArea()
        scroll_r2.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_r2.setWidgetResizable(True)
        scroll_r2.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll_r2.setWidget(form_widget_r2)
        tabs.addTab(scroll_r2, "Round 2")

        # ----- Round 3 ----- (same logic as Round 2)
        form_widget_r3 = QtWidgets.QWidget()
        form_r3 = QtWidgets.QFormLayout(form_widget_r3)
        form_r3.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        # 1 Iterations
        self.ite_r3 = QtWidgets.QSpinBox()
        self.ite_r3.setMaximum(1000000)
        self.ite_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.ite_r3.setValue(8)
        _disable_scroll(self.ite_r3)
        form_r3.addRow(_wrap_label("Iterations"), self.ite_r3)
        # 2 References
        self.nref_r3 = QtWidgets.QSpinBox()
        self.nref_r3.setMaximum(1000000)
        self.nref_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.nref_r3.setValue(1)
        _disable_scroll(self.nref_r3)
        form_r3.addRow(_wrap_label("References"), self.nref_r3)
        # 3 Cone Aperture
        self.cone_range_r3 = QtWidgets.QSpinBox()
        self.cone_range_r3.setMaximum(1000000)
        self.cone_range_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.cone_range_r3.setValue(30)
        _disable_scroll(self.cone_range_r3)
        form_r3.addRow(_wrap_label("Cone Aperture"), self.cone_range_r3)
        # 4 Cone Sampling
        self.cone_sampling_r3 = QtWidgets.QSpinBox()
        self.cone_sampling_r3.setMaximum(1000000)
        self.cone_sampling_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.cone_sampling_r3.setValue(5)
        _disable_scroll(self.cone_sampling_r3)
        form_r3.addRow(_wrap_label("Cone Sampling"), self.cone_sampling_r3)
        # 5 Azimuth Rotation Range
        self.inplane_range_r3 = QtWidgets.QSpinBox()
        self.inplane_range_r3.setMaximum(1000000)
        self.inplane_range_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.inplane_range_r3.setValue(30)
        _disable_scroll(self.inplane_range_r3)
        form_r3.addRow(_wrap_label("Azimuth Rotation Range"), self.inplane_range_r3)
        # 6 Azimuth Rotation Sampling
        self.inplane_sampling_r3 = QtWidgets.QSpinBox()
        self.inplane_sampling_r3.setMaximum(1000000)
        self.inplane_sampling_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.inplane_sampling_r3.setValue(5)
        _disable_scroll(self.inplane_sampling_r3)
        form_r3.addRow(_wrap_label("Azimuth Rotation Sampling"), self.inplane_sampling_r3)
        # 7 Refine
        self.refine_r3 = QtWidgets.QSpinBox()
        self.refine_r3.setMaximum(1000000)
        self.refine_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.refine_r3.setValue(2)
        _disable_scroll(self.refine_r3)
        form_r3.addRow(_wrap_label("Refine"), self.refine_r3)
        # 8 Refine Factor
        self.refine_factor_r3 = QtWidgets.QSpinBox()
        self.refine_factor_r3.setMaximum(1000000)
        self.refine_factor_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.refine_factor_r3.setValue(2)
        _disable_scroll(self.refine_factor_r3)
        form_r3.addRow(_wrap_label("Refine Factor"), self.refine_factor_r3)
        # 9 High Pass
        self.high_r3 = QtWidgets.QSpinBox()
        self.high_r3.setMaximum(1000000)
        self.high_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.high_r3.setValue(1)
        _disable_scroll(self.high_r3)
        form_r3.addRow(_wrap_label("High Pass"), self.high_r3)
        #10 Low Pass
        self.low_r3 = QtWidgets.QSpinBox()
        self.low_r3.setMaximum(1000000)
        self.low_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.low_r3.setValue(12)
        _disable_scroll(self.low_r3)
        form_r3.addRow(_wrap_label("Low Pass"), self.low_r3)
        #11 Symmetry
        self.sym_r3 = QtWidgets.QLineEdit("C1")
        form_r3.addRow(_wrap_label("Symmetry"), self.sym_r3)
        #12 Particle Dimensions
        self.dim_r3 = QtWidgets.QSpinBox()
        self.dim_r3.setMaximum(1000000)
        self.dim_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.dim_r3.setValue(52)
        _disable_scroll(self.dim_r3)
        form_r3.addRow(_wrap_label("Particle Dimensions"), self.dim_r3)
        #13 Shift limits
        shift_widget_r3 = QtWidgets.QWidget()
        sh3 = QtWidgets.QHBoxLayout(shift_widget_r3)
        self.area_search_r3_x = QtWidgets.QSpinBox()
        self.area_search_r3_x.setMaximum(1000000)
        self.area_search_r3_x.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r3_x.setValue(1)
        self.area_search_r3_x.setMinimumWidth(30)
        _disable_scroll(self.area_search_r3_x)
        self.area_search_r3_y = QtWidgets.QSpinBox()
        self.area_search_r3_y.setMaximum(1000000)
        self.area_search_r3_y.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r3_y.setValue(1)
        self.area_search_r3_y.setMinimumWidth(30)
        _disable_scroll(self.area_search_r3_y)
        self.area_search_r3_z = QtWidgets.QSpinBox()
        self.area_search_r3_z.setMaximum(1000000)
        self.area_search_r3_z.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.area_search_r3_z.setValue(0)
        self.area_search_r3_z.setMinimumWidth(30)
        _disable_scroll(self.area_search_r3_z)
        sh3.addWidget(self.area_search_r3_x); sh3.addWidget(self.area_search_r3_y); sh3.addWidget(self.area_search_r3_z)
        form_r3.addRow(_wrap_label("Shift limits"), shift_widget_r3)
        #14 Shift limiting way
        self.area_search_modus_r3 = QtWidgets.QComboBox()
        self.area_search_modus_r3.addItems([
            "No limitations",
            "From the center of the particle cube",
            "From the previous estimation on the particle position",
            "From the estimation provided for the first iteration, with static origin",
        ])
        self.area_search_modus_r3.setCurrentText("From the center of the particle cube")
        _disable_scroll(self.area_search_modus_r3)
        form_r3.addRow(_wrap_label("Shift limiting way"), self.area_search_modus_r3)
        #15 Separation in Tomogram
        self.separation_in_tomogram_r3 = QtWidgets.QSpinBox()
        self.separation_in_tomogram_r3.setMaximum(1000000)
        self.separation_in_tomogram_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.separation_in_tomogram_r3.setValue(0)
        _disable_scroll(self.separation_in_tomogram_r3)
        form_r3.addRow(_wrap_label("Separation in Tomogram"), self.separation_in_tomogram_r3)
        #16 Basic MRA
        self.mra_r3 = QtWidgets.QSpinBox()
        self.mra_r3.setMaximum(1000000)
        self.mra_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.mra_r3.setValue(0)
        _disable_scroll(self.mra_r3)
        form_r3.addRow(_wrap_label("Basic MRA"), self.mra_r3)
        #17 Threshold parameter
        self.threshold_r3 = QtWidgets.QDoubleSpinBox()
        self.threshold_r3.setMaximum(1000000.0)
        self.threshold_r3.setDecimals(6)
        self.threshold_r3.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.threshold_r3.setValue(0.2)
        _disable_scroll(self.threshold_r3)
        form_r3.addRow(_wrap_label("Threshold parameter"), self.threshold_r3)
        #18 Threshold Mode
        self.threshold_mode_r3 = QtWidgets.QComboBox()
        self.threshold_mode_r3.addItems([
            "no thresholding policy",
            "Threshold is an absolute threshold (only particles with CC above this value are selected).",
            "Effective threshold = mean(CC) * THRESHOLD.",
            "Effective threshold = mean(CC) +std(CC)*THRESHOLD.",
            "Threshold is the total number of particles (ordered by CC ).",
            "Threshold ranges between 0 and 1  and sets the fraction of particles.",
        ])
        self.threshold_mode_r3.setCurrentText("no thresholding policy")
        _disable_scroll(self.threshold_mode_r3)
        form_r3.addRow(_wrap_label("Threshold Mode"), self.threshold_mode_r3)
        #19 Exclusion Mode
        self.exclusion_mode_r3 = QtWidgets.QComboBox()
        self.exclusion_mode_r3.addItems([
            "No exclusion from averaging and alignment",
            "Exclusion from averaging and alignment",
        ])
        self.exclusion_mode_r3.setCurrentText("No exclusion from averaging and alignment")
        _disable_scroll(self.exclusion_mode_r3)
        form_r3.addRow(_wrap_label("Exclusion Mode"), self.exclusion_mode_r3)

        # Ensure text inputs and dropdowns expand to the panel width (R3)
        growing_r3 = form_widget_r3.findChildren(
            (QtWidgets.QLineEdit, QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QComboBox)
        )
        for w in growing_r3:
            if w in (
                self.area_search_r3_x,
                self.area_search_r3_y,
                self.area_search_r3_z,
            ):
                continue
            if isinstance(w, QtWidgets.QComboBox):
                w.setMinimumContentsLength(0)
                w.setSizeAdjustPolicy(
                    QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon
                )
            w.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        scroll_r3 = QtWidgets.QScrollArea()
        scroll_r3.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_r3.setWidgetResizable(True)
        scroll_r3.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll_r3.setWidget(form_widget_r3)
        tabs.addTab(scroll_r3, "Round 3")

        v.addWidget(tabs)

        return widget

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

        # Parameters for RELION export (appear above the export button)
        relion_form = QtWidgets.QFormLayout()
        relion_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        def _wrap_label(text: str) -> QtWidgets.QLabel:
            lbl = QtWidgets.QLabel(text)
            lbl.setWordWrap(True)
            lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            return lbl

        # Output pixel size (angstroms per pixel)
        self.relion_output_angpix = QtWidgets.QDoubleSpinBox()
        self.relion_output_angpix.setDecimals(3)
        self.relion_output_angpix.setMinimum(0.001)
        self.relion_output_angpix.setMaximum(100000.0)
        self.relion_output_angpix.setValue(4.0)
        self.relion_output_angpix.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        _disable_scroll(self.relion_output_angpix)
        relion_form.addRow(_wrap_label("Output pixel size"), self.relion_output_angpix)

        # Box size in pixels
        self.relion_warpbox = QtWidgets.QSpinBox()
        self.relion_warpbox.setMinimum(1)
        self.relion_warpbox.setMaximum(1000000)
        self.relion_warpbox.setValue(128)
        self.relion_warpbox.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        _disable_scroll(self.relion_warpbox)
        relion_form.addRow(_wrap_label("Box size (pixels)"), self.relion_warpbox)

        # Particle diameter in angstroms
        self.relion_warp_diameter = QtWidgets.QSpinBox()
        self.relion_warp_diameter.setMinimum(1)
        self.relion_warp_diameter.setMaximum(1000000)
        self.relion_warp_diameter.setValue(220)
        self.relion_warp_diameter.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        _disable_scroll(self.relion_warp_diameter)
        relion_form.addRow(_wrap_label("Particle diameter (angstroms)"), self.relion_warp_diameter)

        btns.addLayout(relion_form)
        self.export_relion_btn = QtWidgets.QPushButton("Export to RELION")
        btns.addWidget(self.export_relion_btn)
        v.addLayout(btns)
        return widget

    def wheelEvent(self, event):
        event.ignore()
