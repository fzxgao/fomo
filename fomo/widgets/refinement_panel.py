from PyQt5 import QtCore, QtWidgets


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
        widget = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(widget)
        v.addWidget(QtWidgets.QLabel("Numerical parameters"))
        form = QtWidgets.QFormLayout()
        # 1 Iterations
        self.iterations = QtWidgets.QSpinBox(); self.iterations.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.iterations.setValue(4)
        form.addRow("Iterations", self.iterations)
        # 2 References
        self.references = QtWidgets.QSpinBox(); self.references.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.references.setValue(1)
        form.addRow("References", self.references)
        # 3 Cone Aperture
        self.cone_aperture = QtWidgets.QSpinBox(); self.cone_aperture.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.cone_aperture.setValue(45)
        form.addRow("Cone Aperture", self.cone_aperture)
        # 4 Cone Sampling
        self.cone_sampling = QtWidgets.QSpinBox(); self.cone_sampling.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.cone_sampling.setValue(15)
        form.addRow("Cone Sampling", self.cone_sampling)
        # 5 Azimuth Rotation Range
        self.az_rot_range = QtWidgets.QSpinBox(); self.az_rot_range.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.az_rot_range.setValue(60)
        form.addRow("Azimuth Rotation Range", self.az_rot_range)
        # 6 Azimuth Rotation Sampling
        self.az_rot_sampling = QtWidgets.QSpinBox(); self.az_rot_sampling.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.az_rot_sampling.setValue(15)
        form.addRow("Azimuth Rotation Sampling", self.az_rot_sampling)
        # 7 Refine
        self.refine = QtWidgets.QSpinBox(); self.refine.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.refine.setValue(2)
        form.addRow("Refine", self.refine)
        # 8 Refine Factor
        self.refine_factor = QtWidgets.QSpinBox(); self.refine_factor.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.refine_factor.setValue(2)
        form.addRow("Refine Factor", self.refine_factor)
        # 9 High Pass
        self.high_pass = QtWidgets.QSpinBox(); self.high_pass.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.high_pass.setValue(1)
        form.addRow("High Pass", self.high_pass)
        #10 Low Pass
        self.low_pass = QtWidgets.QSpinBox(); self.low_pass.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.low_pass.setValue(12)
        form.addRow("Low Pass", self.low_pass)
        #11 Symmetry
        self.symmetry = QtWidgets.QLineEdit("C1")
        form.addRow("Symmetry", self.symmetry)
        #12 Particle Dimensions
        self.particle_dims = QtWidgets.QSpinBox(); self.particle_dims.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.particle_dims.setValue(40)
        form.addRow("Particle Dimensions", self.particle_dims)
        #13 Shift limits
        shift_widget = QtWidgets.QWidget()
        sh = QtWidgets.QHBoxLayout(shift_widget)
        self.shift_x = QtWidgets.QSpinBox(); self.shift_x.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.shift_x.setValue(4); self.shift_x.setMinimumWidth(30)
        self.shift_y = QtWidgets.QSpinBox(); self.shift_y.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.shift_y.setValue(4); self.shift_y.setMinimumWidth(30)
        self.shift_z = QtWidgets.QSpinBox(); self.shift_z.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.shift_z.setValue(12); self.shift_z.setMinimumWidth(30)
        sh.addWidget(self.shift_x); sh.addWidget(self.shift_y); sh.addWidget(self.shift_z)
        form.addRow("Shift limits", shift_widget)
        #14 Shift limiting way
        self.shift_way = QtWidgets.QComboBox()
        self.shift_way.addItems([
            "No limitations",
            "From the center of the particle cube",
            "From the previous estimation on the particle position",
            "From the estimation provided for the first iteration, with static origin",
        ])
        self.shift_way.setCurrentText("From the center of the particle cube")
        form.addRow("Shift limiting way", self.shift_way)
        #15 Separation in Tomogram
        self.separation = QtWidgets.QSpinBox(); self.separation.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.separation.setValue(20)
        form.addRow("Separation in Tomogram", self.separation)
        #16 Basic MRA
        self.basic_mra = QtWidgets.QSpinBox(); self.basic_mra.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.basic_mra.setValue(0)
        form.addRow("Basic MRA", self.basic_mra)
        #17 Threshold parameter
        self.threshold_param = QtWidgets.QDoubleSpinBox(); self.threshold_param.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons); self.threshold_param.setValue(0.2)
        form.addRow("Threshold parameter", self.threshold_param)
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
        form.addRow("Threshold Mode", self.threshold_mode)
        #19 Exclusion Mode
        self.exclusion_mode = QtWidgets.QComboBox()
        self.exclusion_mode.addItems([
            "No exclusion from averaging and alignment",
            "Exclusion from averaging and alignment",
        ])
        self.exclusion_mode.setCurrentText("No exclusion from averaging and alignment")
        form.addRow("Exclusion Mode", self.exclusion_mode)
        v.addLayout(form)
        self.addWidget(widget)

    # -------- Live refinement --------
    def _build_live_refinement_section(self):
        widget = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(widget)
        v.addWidget(QtWidgets.QLabel("Live refinement"))
        hl = QtWidgets.QHBoxLayout()
        self.refined_views = []
        for axis in ("X", "Y", "Z"):
            vb = QtWidgets.QVBoxLayout()
            label = QtWidgets.QLabel(f"{axis}")
            label.setFrameShape(QtWidgets.QFrame.Box)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setFixedSize(60, 60)
            self.refined_views.append(label)
            vb.addWidget(label)
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            vb.addWidget(slider)
            hl.addLayout(vb)
        v.addLayout(hl)
        btns = QtWidgets.QHBoxLayout()
        self.import_left = QtWidgets.QToolButton()
        self.import_left.setArrowType(QtCore.Qt.LeftArrow)
        btns.addWidget(self.import_left)
        self.import_btn = QtWidgets.QPushButton("Import refined coordinates")
        btns.addWidget(self.import_btn)
        self.import_right = QtWidgets.QToolButton()
        self.import_right.setArrowType(QtCore.Qt.RightArrow)
        btns.addWidget(self.import_right)
        self.export_relion_btn = QtWidgets.QPushButton("Export to RELION")
        btns.addWidget(self.export_relion_btn)
        v.addLayout(btns)
        self.addWidget(widget)

    def wheelEvent(self, event):
        event.ignore()