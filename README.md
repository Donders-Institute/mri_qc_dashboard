# mri_qc_dashboard
MRI QC dashboard

This repository contains the files used (a) for the QC based on the phantom measurements (with 'phantom' in the filenames) and (b) for the project-based QC.

Scripts and their intended use:
- Dashboard_Phantom.py - main entry point for the phantom measurements QC
- Preprocess_Phantom_{T1|fMRI}.py - preprocessing for the phantom QC based on the BIDSified data
- Raw2bids_Phantom.sh - BIDSifier for the phantom QC
- Raw2Dashboard_Phantom.sh - combined shell script that does the preprocessing with the two scripts listed above and starts Dashboard_Phantom.py

- Dashboard_project.py - main entry point for the general QC for all projects
- project_dashboards_functions.py - functions generating the plots for the projects dashboard
- project_helpers.py - other helper function for the projects dashboard
