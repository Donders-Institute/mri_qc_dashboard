#!/bin/bash

project='/project/3055010.02'

module load bidscoin/3.7.3
source activate /opt/bidscoin

rawmapper.py -r $project/raw -f ManufacturerModelName AcquisitionDate
bidscoiner.py $project/raw $project/BIDS_data #-b $project/QualityAssessment_new/ScannerData/code/bidsmap.yaml