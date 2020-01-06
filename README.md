Average Revenue Per User Predictor (arpu_predictor)
===========================================

Description
===========
**arpu_predictor** is a predictive model which estimates the average revenue per user capable
of being spent on telecommunications services.


Setup and configuration
=======================

All code for **arpu_predictor** is written in Python (Python>=3.7) and has a number of dependencies.
See `requirements.txt` for a full list.

Using conda
-----------

The recommended installation method is to use [conda](http://conda.pydata.org/miniconda.html),
which handles packages and virtual environments,
along with the `conda-forge` channel which has a host of pre-built libraries and packages.

Create a conda environment called `arpu_predictor`:

    conda create --name arpu_predictor python=3.5

Activate it (run each time you switch projects)::

    activate arpu_predictor

First, install required packages including `pandas`,  `requests` and `rasterstats`:

    conda install pandas requests rasterstats

Conda does not have `geoio`, so also:

    pip install geoio

To visualize the results, install `matplotlib` and `seaborn`:

    conda install matplotlib seaborn

And then run:

    python vis/vis.py

Background and funding
======================

**arpu_predictor** has been funded by UK EPSRC via the Infrastructure Transitions Research
Consortium (EP/N017064/1) and a subsequent EPSRC Impact Accelerator Award.

Contributors
============
- Edward J. Oughton (University of Oxford) (Primary Investigator)
- Jatin Mathur (University of Illinois)

Quick Start
===========
- download:
    - gadm data
    - lsms data
    - noaa nightlight data
    - worldpop
- run preprocess.py
- run grid.py
- run arpu_predictor.py
