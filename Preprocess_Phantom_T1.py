# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""
import warnings
from os import path
import re
from scipy import ndimage
import glob
import dateutil.parser as dparser
import datetime
import pandas as pd
import math
from nilearn import plotting
import nibabel as nib
from pathlib import Path

pd.set_option('display.max_colwidth', None)
default_path = Path('/project/3055010.02/BIDS_data')


def data_array(file) : #calculates center of mass and signal sum
  img = nib.load(file)  #reads image file
  data = img.get_fdata() #gets matrix type structure from image
  return  ndimage.measurements.center_of_mass(data),sum(sum(sum(data))) # gets measurments in question - add stuff in this line for more metrics


def get_all_files_scanner(scanner): #gets all files from a specific scanner
    files = list() #list of files
    coils = ["%.2d" % i for i in range(1,33)] #coil list
    filename_pattern = re.compile(".*grecoilCheck(C|cH)\d+_run-1_T1w.nii")
    files = [f for f in default_path.joinpath('sub-' + scanner).glob('**/anat/*grecoilCheck*_run-1_T1w.nii.gz') if filename_pattern.match(f.as_posix())]
    return files

def filter_file_list_scanner_after(scanner,date): #gets all files from a specific scanner after a specific date
    files=get_all_files_scanner(scanner)
    files_filtered = list()
    for file in files:
        match_date = re.search(r'\d{8}_acq', file.as_posix()) #gets dates from file names
        match_date = dparser.parse(match_date.group(0),fuzzy=True)
        if match_date>datetime.datetime.strptime(str(date), '%Y%m%d'): #This is where the filtering happens
            files_filtered.append(file)
    return files_filtered
 
def filter_file_list_scanner_before(scanner,date): #gets all files from a specific scanner before a specific date (same as previous but different filter)
    files=get_all_files_scanner(scanner)
    files_filtered = list()
    for file in files:
        match_date = re.search(r'\d{8}_acq', file.as_posix())
        match_date = dparser.parse(match_date.group(0),fuzzy=True)
        if match_date<datetime.datetime.strptime(str(date), '%Y%m%d'):
            files_filtered.append(file)
    return files_filtered
    

def create_plot_32_coils(scanner,date): #creates html code that has the correct structure for a given scanner and date - plots the image of each of the 32 coil images
    coil_images = dict() # creates a dictionary that will hold the html code for each image
    coils = ["%.2d" % i for i in range(1,33)]  #coil list
    for coil in coils:
        img_path = default_path.joinpath('sub-'+scanner+'/ses-'+str(date)+'/anat/sub-'+scanner+'_ses-'+str(date)+'_acq-grecoilCheckC'+coil+'_run-1_T1w.png')

        source_path = [f for f in default_path.joinpath('sub-' + scanner + '/ses-' + str(date) + '/anat/').glob('sub-%s_ses-%s_acq-grecoilCheck*%i_run-1_T1w.nii.gz' % ( scanner,str(date),int(coil)))
                       if re.search('grecoilCheck(C|cH)0?%i_run-1_T1w' % int(coil), f.as_posix())]

        if len(source_path)==0:
            warnings.warn('GRE coil check files missing in '+default_path.joinpath('sub-' + scanner + '/ses-' + str(date) + '/anat/').as_posix())
            return

        source_path = source_path[0].as_posix()

        coil_images[coil]='<img src="'+img_path.as_posix()+'" />' #html code to link to an image
        if not img_path.exists(): #only creates image if it doesnt exist yet
            plotting.plot_anat(anat_img=source_path,display_mode='z',cut_coords=1,
                           output_file=img_path.as_posix(),title='C'+coil)# creates the plot
  
    df=pd.DataFrame(data=coil_images.items()) #dataframe from dictionary
    df=df.drop(columns=[0])# drop first column
    #Remaining formatting for the html file
    col=[1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,4]
    df['col']=col
    df=df.pivot_table(df,index='col',aggfunc=lambda x: '  '.join(str(v) for v in x))
    df.columns=['Name']
    df=df.Name.str.split("  ",expand=True,)
    df.to_html(default_path.joinpath('sub-'+scanner+'/ses-'+str(date)+'_phantom.html'),escape=False, header=False, index=False)

def get_date_from_file_list(files): #gets list of dates and coils from files
    dates=list()
    coils=list()
    for file in files:
        match_date = re.search(r'\d{8}_acq', file.as_posix())
        match_coil = re.search(r'(C|cH)(\d{1,2})', file.as_posix())
        match_date = dparser.parse(match_date.group(0),fuzzy=True)
        match_coil = match_coil.group(2)
        dates.append(match_date.date())
        coils.append(match_coil)
    return dates,coils

def create_dataframe_scanner(scanner):
    files= get_all_files_scanner(scanner)
    file_dates,file_coils = get_date_from_file_list(files)
    dates_df = sorted(file_dates) #sort dates
    dates_df = set(dates_df) #remove duplicates
    dates_df = list(dates_df) #puts in list format
    dates_df = [datetime.date.strftime(x,'%Y%m%d') for x in dates_df] #puts dates in string format
    center_of_mass_x_col = ["center_of_mass_x_C"+"%.2d" % i for i in range(1,33)]
    center_of_mass_y_col = ["center_of_mass_y_C"+"%.2d" % i for i in range(1,33)]
    center_of_mass_z_col = ["center_of_mass_z_C"+"%.2d" % i for i in range(1,33)]
    proportion_col = ["signal_proportion_C"+"%.2d" % i for i in range(1,33)]
    lists = [center_of_mass_x_col,center_of_mass_y_col,center_of_mass_z_col,proportion_col]
    col_names=[val for tup in zip(*lists) for val in tup]
    df = pd.DataFrame(columns=col_names,index=dates_df)
    i=0
    for file in files:
        center_of_mass,signal=data_array(file)
        df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),"center_of_mass_x_C"+file_coils[i]]=center_of_mass[0]
        df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),"center_of_mass_y_C"+file_coils[i]]=center_of_mass[1]
        df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),"center_of_mass_z_C"+file_coils[i]]=center_of_mass[2]
        df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),"signal_proportion_C"+file_coils[i]]=signal
        i=i+1
    coils = ["%.2d" % i for i in range(1,33)]
    for index, row in df.iterrows():
        signal_coils = 0
        for coil in coils:
            if not math.isnan(row["signal_proportion_C"+coil]):
                signal_coils = signal_coils+row["signal_proportion_C"+coil]
        for coil in coils:
            if not math.isnan(row["signal_proportion_C"+coil]):
                df.loc[index,"signal_proportion_C"+coil]=row["signal_proportion_C"+coil]/signal_coils
    df=df.sort_index()
    df.index.names = ['date']
    df.to_csv(default_path.joinpath('sub-'+scanner+'/full_data.csv'))

def create_all_individual_reports(scanner):
    files= get_all_files_scanner(scanner)
    file_dates,file_coils = get_date_from_file_list(files) 
    dates_df = sorted(file_dates) #sort dates
    dates_df = set(dates_df) #remove duplicates
    dates_df = list(dates_df) #puts in list format
    dates_df = [datetime.date.strftime(x,'%Y%m%d') for x in dates_df] #puts dates in string format
    dates_df = list(map(int, dates_df))
    for dates in dates_df:
        print (str(dates))
        create_plot_32_coils(scanner,dates)

def update_dataframe_scanner(scanner):
    df_full=pd.read_csv(default_path.joinpath('sub-'+scanner+'/full_data.csv'),index_col=0)
    first_date = df_full.index[0]
    files_before=filter_file_list_scanner_before(scanner,first_date)
    last_date = df_full.index[-1]
    files_after=filter_file_list_scanner_after(scanner,last_date)
    files=files_before+files_after
    file_dates,file_coils = get_date_from_file_list(files)
    dates_df = sorted(file_dates) #sort dates
    dates_df = set(dates_df) #remove duplicates
    dates_df = list(dates_df) #puts in list format
    dates_df = [datetime.date.strftime(x,'%Y%m%d') for x in dates_df] #puts dates in string format
    center_of_mass_x_col = ["center_of_mass_x_C"+"%.2d" % i for i in range(1,33)]
    center_of_mass_y_col = ["center_of_mass_y_C"+"%.2d" % i for i in range(1,33)]
    center_of_mass_z_col = ["center_of_mass_z_C"+"%.2d" % i for i in range(1,33)]
    proportion_col = ["signal_proportion_C"+"%.2d" % i for i in range(1,33)]
    lists = [center_of_mass_x_col,center_of_mass_y_col,center_of_mass_z_col,proportion_col]
    col_names=[val for tup in zip(*lists) for val in tup]
    df = pd.DataFrame(columns=col_names,index=dates_df)
    i=0
    for file in files:
        center_of_mass,signal=data_array(file)
        file_coils[i] = '%02i' % int(file_coils[i])
        df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),"center_of_mass_x_C"+file_coils[i]]=center_of_mass[0]
        df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),"center_of_mass_y_C"+file_coils[i]]=center_of_mass[1]
        df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),"center_of_mass_z_C"+file_coils[i]]=center_of_mass[2]
        df.loc[datetime.date.strftime(file_dates[i],'%Y%m%d'),"signal_proportion_C"+file_coils[i]]=signal
        i=i+1
    coils = ["%.2d" % i for i in range(1,33)]
    for index, row in df.iterrows():
        signal_coils = 0
        for coil in coils:
            if not math.isnan(row["signal_proportion_C"+coil]):
                signal_coils = signal_coils+row["signal_proportion_C"+coil]
        for coil in coils:
            if not math.isnan(row["signal_proportion_C"+coil]):
                df.loc[index,"signal_proportion_C"+coil]=row["signal_proportion_C"+coil]/signal_coils
    df.index=pd.Index.astype(df.index,'int')
    df_full=df_full.append(df)
    df_full=df_full.sort_index()
    df_full.index.names = ['date']
    df_full.to_csv(default_path.joinpath('sub-'+scanner+'/full_data.csv'))
    
    
def update_all_individual_reports(scanner):
    df_full=pd.read_csv(default_path.joinpath('sub-'+scanner+'/full_data.csv'),index_col=0)
    first_date = df_full.index[0]
    files_before=filter_file_list_scanner_before(scanner,first_date)
    last_date = df_full.index[-1]
    files_after=filter_file_list_scanner_after(scanner,last_date)
    files=files_before+files_after
    file_dates,file_coils = get_date_from_file_list(files)
    dates_df = sorted(file_dates) #sort dates
    dates_df = set(dates_df) #remove duplicates
    dates_df = list(dates_df) #puts in list format
    dates_df = [datetime.date.strftime(x,'%Y%m%d') for x in dates_df] #puts dates in string format
    dates_df = list(map(int, dates_df))
    for dates in dates_df:
        print (str(dates))
        create_plot_32_coils(scanner,dates)
        
def add_marks_worst_coil(scanner):
     df=pd.read_csv(default_path.joinpath('sub-'+scanner+'/full_data_short.csv'),converters={'coil': lambda x: str(x)})
     df['date'] = df['date'].astype(str)
     df['link']= df.apply(lambda row: default_path.joinpath('sub-'+scanner+'/ses-'+str(row.date)+'_phantom.html'),axis=1)

     for row in df.iterrows():
         if not Path(row[1].link).exists():
             warnings.warn('File %s does not exist, trying to recreate' % row[1].link)
             create_plot_32_coils(scanner, row[1].date)
             if not Path(row[1].link).exists():
                warnings.warn('Wasn\'t able to create %s, skipping' % row[1].link)
             else:
                 print('File successfully created')

             continue
         with open(row[1].link, 'r') as f:
             html_string = f.read()
             html_string = "<style>table, tr, td {border: 1px solid black;}#biggest{border: 2px solid #FF0000;}</style> \n"+html_string
             path_to_img = default_path.joinpath('sub-'+scanner+'/ses-'+row[1].date+'/anat/sub-'+scanner+'_ses-'+row[1].date+'_acq-grecoilCheckC'+row[1].coil+'_run-1_T1w.png').as_posix()
             find = '<td><img src="'+path_to_img+'" /></td>'
             replace = '<td bgcolor="#FF0000" id="biggest"><img src="'+path_to_img+'"/></td>'
             html_string=html_string.replace(find,replace)
             f.close()
         with open(row[1].link, mode='w') as corrected_html_file:
             corrected_html_file.write(html_string)
             corrected_html_file.close()
             
def create_dataframe_scanner_short(scanner):
     df_full=pd.read_csv(default_path.joinpath('sub-'+scanner+'/full_data.csv'),index_col=0)
     df_median = df_full.rolling(5).median()
     df_dist = (df_full-df_median)**2
     df_short = pd.DataFrame(columns=['max_dev', 'max_prop_dev','coil'],index=df_dist.index)
     coils = ["%.2d" % i for i in range(1,33)]
     for index, row in df_dist.iterrows():
         max_dev_coils = 0
         max_prop_coils = 0
         max_coil='01'
         for coil in coils:
             max_dev = math.sqrt(row['center_of_mass_x_C'+coil]+row['center_of_mass_y_C'+coil]+row['center_of_mass_z_C'+coil])
             max_prop= math.sqrt(row['signal_proportion_C'+coil])*100
             if max_dev >= max_dev_coils:
                 max_dev_coils=max_dev
                 max_coil=coil
             if max_prop >= max_prop_coils:
                 max_prop_coils=max_prop
         df_short.loc[index,'max_dev']=max_dev_coils
         df_short.loc[index,'max_prop_dev']=max_prop_coils
         df_short.loc[index,'coil']=max_coil
     df_short=df_short.drop(df_short.index[0:4])
     df_short.index.names = ['date']
     df_short.to_csv(default_path.joinpath('sub-'+scanner+'/full_data_short.csv'))

       

if __name__ == "__main__":

    scanners=['Skyra','Prismafit','Prisma']
    for scanner in scanners:
        print(scanner)
        update_all_individual_reports(scanner)
        update_dataframe_scanner(scanner)
        create_dataframe_scanner_short(scanner)
        add_marks_worst_coil(scanner)
