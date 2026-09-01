import pandas as pd
import numpy as np
import datetime
import glob
import xarray as xr

from PyBSI.tools import *

def convert_folder(path, nFBG=8) :
    files = glob.glob(path)
    files.sort()    
    for i, file in enumerate(files):
        if i == 0:
            absTime, relTime, OutWav, refTime = read(file, nFBG=nFBG)
            continue
        TabsTime, TrelTime, TOutWav, _ = read(file, refTime=refTime, nFBG=nFBG)
        try :
            absTime, relTime, OutWav = np.append(absTime, TabsTime), np.append(relTime, TrelTime), np.append(OutWav, TOutWav, axis=1)
        except :
            print('Error file : %s' %file)
        #print(absTime[0], absTime[-1])
        if verif_date(absTime) == True :
            print('Exporting file')
            IdxEndTime = np.where(absTime.astype('datetime64[D]')==absTime[-1].astype('datetime64[D]'))[0][0]
            OabsTime, OrelTime, OOutWav = absTime[:IdxEndTime], relTime[:IdxEndTime], OutWav[:,:IdxEndTime]
            absTime, relTime, OutWav = absTime[IdxEndTime:], relTime[IdxEndTime:], OutWav[:,IdxEndTime:]
            export_nc(OabsTime, OrelTime, OOutWav, refwav=None)
    try :
        export_nc(absTime, relTime, OutWav, refwav=None)
    except : pass

def read(filepath, refwav=None, refTime=None, nFBG=8):

    info = filepath.split('/')
    print('Starting reading file : %s' %info[-1])
    sttime = info[-1][:16]

    date = datetime.datetime.strptime(sttime, '%Y%m%dT%H%M%SZ')
    timing = np.datetime64(date, 'ms')
    headers = ['Time [sec]']
    for i in range(1, nFBG+1):
        headers.append('Wavelength %i[nm]' %i)
    data = pd.read_csv(filepath, delimiter='\t', decimal=',', usecols=headers)
    data = data.to_numpy()
    rtime = data[:,0]
    data = data[:,1:].T

    urtime = (rtime*1000).astype(int)
    if refTime is None:
        refTime = timing - urtime[0]
    #print(refTime, urtime)
    absTime = refTime + urtime 


    return absTime, rtime, data, refTime

def export_nc(absTime, relTime, OutWav, refwav=None, path='./'):
    if refwav is None :
        refwav = OutWav[:,0]
 
    data = xr.Dataset(data_vars=dict(Wavelength_nm = (["FBG","Time"], OutWav),
                                    Calibration_Wavelength = (['FBG'], refwav)),
                      coords = dict(relative_Time = relTime,
                                   Time = absTime),
                      attrs=dict(description="FBG data -  Dimension of the data (FBG*Time)"))
    OutName = str(absTime[0]).replace('-','.').replace(':','.')
    data.to_netcdf(path+'/FBG_HSV_%s.nc' %(OutName))