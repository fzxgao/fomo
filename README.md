# Fomo - Filament Tomography
<img width="2556" height="1990" alt="image" src="https://github.com/user-attachments/assets/d405269c-4d8f-4896-847e-99b274f419b9" />


Fomo is a high-performance end-to-end MRC/REC tomogram reconstruction, viewing, picking and refinement tool designed for electron tomography workflows.
It supports fast Z-slicing, contrast adjustment via histogram, dual XY/XZ panels, and optional picking, alignment and sub-boxing modes for advanced analysis.

## Features
- Dual XY and XZ slice views
- Interactive contrast adjustment with histogram
- Scroll acceleration for fast slicing
- Fully functional over secure shell with X11 forwarding
- Picking mode with custom plane resampling
- PAST - Pick and Align (at the Same Time)
- Estimation of helical parameters and subboxing
- Modular architecture for easy extension

## Installation
### Dependencies
Fomo depends on WarpTools and Dynamo. 

Clone the repository and install the required dependencies:
```bash
pip install -r requirements.txt
```

## Acknowledgements
FOMO builds on the ideas, software, and community effort of several outstanding projects. We’re grateful for their tools, that made this work possible:

RANSAC (Random Sample Consensus) — for robust model fitting and outlier rejection that underpins our geometric filtering/clean-up steps.
Javier Vargas, Ana-Lucia Álvarez-Cabrera, Roberto Marabini, Jose M. Carazo, C. O. S. Sorzano, Efficient initial volume determination from electron microscopy images of single particles, Bioinformatics, Volume 30, Issue 20, October 2014, Pages 2891–2898, https://doi.org/10.1093/bioinformatics/btu404

Dynamo — for a mature ecosystem around subtomogram alignment/averaging, file formats, and practical workflows that inspired parts of our data handling and interoperability.
Thanks to Daniel Castaño-Díez and the Dynamo community.
Daniel Castaño-Díez, Mikhail Kudryashev, Marcel Arheit, Henning Stahlberg, Dynamo: A flexible, user-friendly development tool for subtomogram averaging of cryo-EM data in high-performance computing environments, Journal of Structural Biology, Volume 178, Issue 2, 2012, Pages 139-151, ISSN 1047-8477, https://doi.org/10.1016/j.jsb.2011.12.017.

Warp / WarpTools — for fast cryo-EM/ET preprocessing and a clear, scriptable toolkit whose conventions and exports FOMO interoperates with.
Thanks to Dmitry Tegunov and contributors.
Tegunov, D., Cramer, P. Real-time cryo-electron microscopy data preprocessing with Warp. Nat Methods 16, 1146–1152 (2019). https://doi.org/10.1038/s41592-019-0580-y

Please cite their work if using FOMO.
