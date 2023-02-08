# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""
import numpy as np
import json
import fsspec
import re
from scipy import ndimage
from scipy.spatial.distance import cdist
import matplotlib.pyplot as plt
import glob
from os import path
import dateutil.parser as dparser
import datetime
import pandas as pd
from nilearn.plotting import plot_anat
import nibabel as nib
import nipype.algorithms.confounds as confounds
from nilearn.image import new_img_like
from pathlib import Path

pd.set_option('display.max_colwidth', 1000)

default_path = Path('/project/3055010.02/BIDS_data')

#def create_tSNR_detrend_images(file) : #creates the tSNRimages of detrended images
#    tsnr = confounds.TSNR(regress_poly=1,
#                          tsnr_file=file.replace("echo-1_bold","echo-1_bold_tsnr_detrended"),
#                          mean_file=file.replace("echo-1_bold","echo-1_bold_mean_detrended"),
#                          stddev_file=file.replace("echo-1_bold","echo-1_bold_stddev_detrended"),
#                          detrended_file=file.replace("echo-1_bold","echo-1_bold_detrended"))
#    tsnr.inputs.in_file = file
#    tsnr.run() 


def gsr(epi_data, mask, axis=1, ref_file=None, out_file=None):
    """
    Computes the :abbr:`GSR (ghost to signal ratio)` [Giannelli2010]_. The
    procedure is as follows:

      #. Create a Nyquist ghost mask by circle-shifting the original mask by :math:`N/2`.

      #. Rotate by :math:`N/2`

      #. Remove the intersection with the original mask

      #. Generate a non-ghost background

      #. Calculate the :abbr:`GSR (ghost to signal ratio)`


    .. warning ::

      This should be used with EPI images for which the phase
      encoding direction is known.

    :param str epi_file: path to epi file
    :param str mask_file: path to brain mask
    :param str direction: the direction of phase encoding (x, y, all)
    :return: the computed gsr

    """


    # Roll data of mask through the appropriate axis

    n2_mask = np.roll(mask, mask.shape[axis] // 2, axis=axis)

    # Step 3: remove from n2_mask pixels inside the brain
    n2_mask = n2_mask * (1 - mask)

    # Step 4: non-ghost background region is labeled as 2
    n2_mask = n2_mask + 2 * (1 - n2_mask - mask)

    # Step 5: signal is the entire foreground image
    ghost = np.mean(epi_data[n2_mask == 1]) - np.mean(epi_data[n2_mask == 2])
    signal = np.median(epi_data[n2_mask == 0])
    return float(ghost / signal)


def create_functional_image_metrics(filePath) : #creates the tSNRimages of original images
    file = filePath.as_posix()
    tsnr = confounds.TSNR(tsnr_file=file.replace("echo-1_bold","echo-1_bold_tsnr"),
                          mean_file=file.replace("echo-1_bold","echo-1_bold_mean"),
                          stddev_file=file.replace("echo-1_bold","echo-1_bold_stddev"))
    tsnr.inputs.in_file = file
    tsnr.run()
    tsnr_img = nib.load(file.replace("echo-1_bold","echo-1_bold_tsnr")) #reads tSNR file
    mean_img = nib.load(file.replace("echo-1_bold","echo-1_bold_mean")) #reads mean file
    signal_img = nib.load(file) #reads bold file
    tsnr_data = tsnr_img.get_fdata()
    mean_data = mean_img.get_fdata()
    signal_data = signal_img.get_fdata()
    center_of_mass = ndimage.measurements.center_of_mass(tsnr_data)
    x_coord = int(round(center_of_mass[0]))
    y_coord = int(round(center_of_mass[1]))
    z_coord = int(round(center_of_mass[2]))
    signal_mask =  0*tsnr_data
    mean_data_mask = np.where(mean_data>np.amax(mean_data)*.25, 1, 0) 
    signal_mask[x_coord-10:x_coord+10,y_coord-10:y_coord+10,z_coord-5:z_coord+5]=1
    tsnr_masked_data = tsnr_data*signal_mask
    signal_mask4d=np.zeros((signal_data.shape[0],signal_data.shape[1],signal_data.shape[2],signal_data.shape[3]))
    signal_mask4d[:,:,:,:] = signal_mask[:,:,:,np.newaxis] == 1
    signal_masked_data = signal_data*signal_mask4d
    timeseries = np.zeros(signal_masked_data.shape[3])
    center_of_mass_list = list()
    for i in np.arange(signal_masked_data.shape[3]):
           timepoint = signal_masked_data[:,:,:,i][signal_masked_data[:,:,:,i]!=0].mean()
           center_of_mass = ndimage.measurements.center_of_mass(signal_data[:,:,:,i])
           center_of_mass_list.append(np.asarray([center_of_mass[0],center_of_mass[1],center_of_mass[2]]))
           timeseries[i]=timepoint
    hdist = cdist(center_of_mass_list, center_of_mass_list, metric='euclidean')
    max_displacement = hdist.max()
    
    timeseries_poly = np.polyfit(np.arange(signal_masked_data.shape[3]), timeseries, 2)
    timeseries_fit=np.polyval(timeseries_poly,np.arange(signal_masked_data.shape[3]))
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(1, 1, 1)
    ax.set_title('fMRI timeseries and polynomial fit',fontsize=20)
    ax.set_xlim([0,300])
    ax.set_xlabel('Time (in TRs)',fontsize=20)
    ax.set_ylabel('Intensity',fontsize=20)
    line1 = ax.plot(timeseries,label='Timeseries in mask')    
    line2 = ax.plot(timeseries_fit,label='Polynomial fit')    
    ax.legend(fontsize = 'large')
    print(file)
    fig.savefig(file.replace("echo-1_bold.nii.gz","echo-1_bold_timeseries.png"), dpi=500,bbox_inches = 'tight')
    plt.close(fig)
    tsnr_mask_img = new_img_like(tsnr_img, tsnr_masked_data)
    display = plot_anat(tsnr_img,draw_cross=False)
    display.add_contours(tsnr_mask_img, contours=1, antialiased=False,
                     linewidths=1., levels=[0], colors=['red'])
    display.savefig(file.replace("echo-1_bold.nii.gz","echo-1_bold_tsnr.png"))
    display.close()
    tSNR = tsnr_masked_data[np.nonzero(tsnr_masked_data)].mean()
    ghost_signal_ratio = gsr(mean_data,mean_data_mask)*100
    json_file=file.replace("echo-1_bold.nii.gz","echo-1_bold.json")
    parsed_json=json_read(json_file)
    ref_amp = parsed_json['TxRefAmp']
    return  tSNR,ghost_signal_ratio,ref_amp,max_displacement
    
def get_all_files_scanner(scanner): #gets all files from a specific scanner
    files = list()
    for filename in default_path.joinpath('sub-'+scanner).glob('**/func/*'+'ep2dboldstability_run-1_echo-1_bold.nii.gz'):
        # print(filename)
        files.append(filename)
    return files

def json_read(filename):
   with open(filename) as f_in:
       return(json.load(f_in))

def filter_file_list_scanner_after(scanner,date): #gets all files from a specific scanner on a specific date
    files=get_all_files_scanner(scanner)
    files_filtered = list()
    for file in files:
        match_date = re.search(r'\d{8}_task', file.as_posix())
        match_date = dparser.parse(match_date.group(0),fuzzy=True)
        if match_date>datetime.datetime.strptime(str(date), '%Y%m%d'):
            files_filtered.append(file)
    return files_filtered

def filter_file_list_scanner_before(scanner,date): #gets all files from a specific scanner on a specific date
    files=get_all_files_scanner(scanner)
    files_filtered = list()
    for file in files:
        match_date = re.search(r'\d{8}_task', file.as_posix())
        match_date = dparser.parse(match_date.group(0),fuzzy=True)
        if match_date<datetime.datetime.strptime(str(date), '%Y%m%d'):
            files_filtered.append(file)
    return files_filtered
 
def get_date_from_file_list(files):
    dates=list()
    for file in files:
        match_date = re.search(r'\d{8}_task', file.as_posix())
        match_date = dparser.parse(match_date.group(0),fuzzy=True)
        dates.append(match_date.date())
    return dates


def create_dataframe_scanner(scanner):
    files = get_all_files_scanner(scanner)
    file_dates = get_date_from_file_list(files)
    dates_df = sorted(file_dates) #sort dates
    dates_df = set(dates_df) #remove duplicates
    dates_df = list(dates_df) #puts in list format
    dates_df = [datetime.date.strftime(x,'%Y%m%d') for x in dates_df] #puts dates in string format
    col_names = ['tSNR','GSR','ref_amp','max_displacement']
    df = pd.DataFrame(columns=col_names,index=dates_df)
    i=0
    for file in files:
        if not path.exists(file.replace("echo-1_bold.nii.gz","echo-1_bold_timeseries.png")):
            tSNR,GSR,ref_amp,max_displacement = create_functional_image_metrics(file)
            df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),'tSNR']=tSNR
            df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),'GSR']=GSR
            df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),'ref_amp']=ref_amp
            df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),'max_displacement']=max_displacement

        else:
            tsnr_img = nib.load(file.replace("echo-1_bold","echo-1_bold_tsnr")) #reads tSNR file
            mean_img = nib.load(file.replace("echo-1_bold","echo-1_bold_mean")) #reads tSNR file
            signal_img = nib.load(file)
            signal_data = signal_img.get_fdata()
            center_of_mass_list = list()
            for image in np.arange(signal_img.shape[3]):
                center_of_mass = ndimage.measurements.center_of_mass(signal_data[:,:,:,image])
                center_of_mass_list.append(np.asarray([center_of_mass[0],center_of_mass[1],center_of_mass[2]]))
            hdist = cdist(center_of_mass_list, center_of_mass_list, metric='euclidean')
            max_displacement = hdist.max()
            tsnr_data = tsnr_img.get_fdata()
            mean_data = mean_img.get_fdata()
            center_of_mass = ndimage.measurements.center_of_mass(tsnr_data)
            x_coord = int(round(center_of_mass[0]))
            y_coord = int(round(center_of_mass[1]))
            z_coord = int(round(center_of_mass[2]))
            signal_mask =  0*tsnr_data
            mean_data_mask = np.where(mean_data>np.amax(mean_data)*.25, 1, 0) 
            signal_mask[x_coord-10:x_coord+10,y_coord-10:y_coord+10,z_coord-5:z_coord+5]=1
            tsnr_masked_data = tsnr_data*signal_mask
            tSNR = tsnr_masked_data[np.nonzero(tsnr_masked_data)].mean()
            GSR = gsr(mean_data,mean_data_mask)*100
            json_file=file.replace("echo-1_bold.nii.gz","echo-1_bold.json")
            parsed_json=json_read(json_file)
            ref_amp = parsed_json['TxRefAmp']
            df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),'tSNR']=tSNR
            df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),'GSR']=GSR
            df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),'ref_amp']=ref_amp
            df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),'max_displacement']=max_displacement
        i=i+1
    df=df.sort_index()
    df.index.names = ['date']
    df.to_csv(default_path.joinpath('sub-'+scanner+'/full_data_fMRI.csv'))


def update_dataframe_scanner(scanner):
    full_data_path = default_path.joinpath('sub-'+scanner).joinpath('full_data_fMRI.csv')
    df_full=pd.read_csv(full_data_path, index_col=0)
    first_date = df_full.index[0]
    files_before=filter_file_list_scanner_before(scanner,first_date)
    last_date = df_full.index[-1]
    files_after=filter_file_list_scanner_after(scanner,last_date)
    files=files_before+files_after
    file_dates = get_date_from_file_list(files)
    dates_df = sorted(file_dates) #sort dates
    dates_df = set(dates_df) #remove duplicates
    dates_df = list(dates_df) #puts in list format
    dates_df = [datetime.date.strftime(x,'%Y%m%d') for x in dates_df] #puts dates in string format
    col_names = ['tSNR','GSR','ref_amp']
    df = pd.DataFrame(columns=col_names,index=dates_df)
    i=0
    for file in files:
        tSNR,GSR,ref_amp,max_displacement = create_functional_image_metrics(file)
        df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),'tSNR']=tSNR
        df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),'GSR']=GSR
        df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),'ref_amp']=ref_amp
        df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),'max_displacement']=max_displacement

        i=i+1
    df.index=pd.Index.astype(df.index,'int')
    df_full=df_full.append(df)
    df_full=df_full.sort_index()
    df_full.index.names = ['date']
    df_full.to_csv(full_data_path)
    
def create_report(scanner,date):
    f = open(default_path.joinpath('sub-'+scanner+'/ses-'+str(date)+'_phantom_fMRI.html'),'w')
    source = default_path.joinpath('sub-'+scanner+'/ses-'+str(date)+'/func/sub-'+scanner+'_ses-'+str(date)+'_task-ep2dboldstability_run-1_echo-1_bold_tsnr.png')
    source2 = default_path.joinpath('sub-'+scanner+'/ses-'+str(date)+'/func/sub-'+scanner+'_ses-'+str(date)+'_task-ep2dboldstability_run-1_echo-1_bold_timeseries.png')
    message = """<html>
    <head></head>
    <body><img src="%(source)s"><br><img src="%(source2)s" height="550" width="550"></body>
    </html>""" % {'source': source,'source2': source2}
    f.write(message)
    f.close()

def create_all_individual_reports(scanner):
    files= get_all_files_scanner(scanner)
    file_dates = get_date_from_file_list(files) 
    dates_df = sorted(file_dates) #sort dates
    dates_df = set(dates_df) #remove duplicates
    dates_df = list(dates_df) #puts in list format
    dates_df = [datetime.date.strftime(x,'%Y%m%d') for x in dates_df] #puts dates in string format
    dates_df = list(map(int, dates_df))
    for dates in dates_df:
        print (str(dates))
        create_report(scanner,dates)
        
def update_all_individual_reports(scanner):
    df_full=pd.read_csv(default_path.joinpath('sub-'+scanner).joinpath('full_data_fMRI.csv'),index_col=0)

    first_date = df_full.index[0]
    files_before=filter_file_list_scanner_before(scanner,first_date)
    last_date = df_full.index[-1]
    files_after=filter_file_list_scanner_after(scanner,last_date)
    files=files_before+files_after
    file_dates = get_date_from_file_list(files) 
    dates_df = sorted(file_dates) #sort dates
    dates_df = set(dates_df) #remove duplicates
    dates_df = list(dates_df) #puts in list format
    dates_df = [datetime.date.strftime(x,'%Y%m%d') for x in dates_df] #puts dates in string format
    dates_df = list(map(int, dates_df))
    for dates in dates_df:
        print (str(dates))
        create_report(scanner,dates)

        
if __name__ == "__main__":

    scanners=['Skyra','Prismafit','Prisma']
    for scanner in scanners:
        print(scanner)
        update_all_individual_reports(scanner)
        update_dataframe_scanner(scanner)

