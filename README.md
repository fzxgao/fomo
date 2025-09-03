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
