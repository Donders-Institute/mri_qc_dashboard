#!/bin/bash

# Please run this script in an interactive session on a compute node, not on a mentat node. If you run it on a mentat node, it won't work on a mentat node because Python 3.6 is absent there for some reason.

cd /project/3055010.02/QualityAssessment_2022/
source ./venv/bin/activate venv
sh Raw2Bids.sh
cd /project/3055010.02/QualityAssessment_2022/
python Preprocess_Phantom_T1.py
python Preprocess_Phantom_fMRI.py
python Dashboard_Phantom.py



