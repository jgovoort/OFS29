import pandas as pd
import numpy as np
import warnings
import os
import csv 

from PyBSI.tools import *


def read(filepath, refwav=None, nChannel=8, maxFBGs=12, extended=False):
    """
    Read BSI FBG text files with multichannel data and return a 3D array of wavelengths over time.

    This function reads a file containing multichannel FBG (Fiber Bragg Grating) data, processes the 
    wavelengths for each channel, and returns the data in a structured format. It can optionally 
    return the data in a dictionary format with additional timing information.

    Parameters
    ----------
    filepath : str
        Path to the BSI text file containing the FBG data.
    
    refwav : np.ndarray, optional
        A 2D array used as the reference wavelength for the channels and FBGs. If not provided, the first
        entry in the data file will be used as the reference (default is None).
    
    nChannel : int, optional
        Number of channels to read from the file (default is 8).
    
    maxFBGs : int, optional
        Maximum number of FBGs per channel to read (default is 12).
    
    extended : bool, optional
        If True, the function returns dictionaries with channel-wise data and timestamps. If False, it returns
        simple arrays (default is False).

    Returns
    -------
    If extended is False:
        absTime : np.ndarray
            Array of absolute timestamps in `datetime64` format.
        
        refTime : np.ndarray
            Array of reference times in float format.
        
        OutWav : np.ndarray
            3D array of wavelengths with dimensions (Channel x FBG x Time).
        
        refwav : np.ndarray
            Reference wavelength used for comparison.
    
    If extended is True:
        dict_data : dict
            Dictionary containing channel-wise FBG data over time, indexed by channel.
        
        dict_time : dict
            Dictionary containing absolute timestamps, indexed by channel.
    
    Notes
    -----
    - If no reference wavelength (`refwav`) is provided, the first set of data is used as the reference.
    - A warning is raised if a shift greater than 3 nm is detected between the current data and the reference, 
      and the function attempts to auto-correct it using `fbg_verifier`.
    - The output 3D array `OutWav` has dimensions corresponding to (Channels, FBGs, Time).
    - The function assumes that each row in the input file contains tab-separated values, where the first column 
      is the timestamp and the following columns are wavelength values.

    Examples
    --------
    >>> filepath = 'data/fbg_measurements.txt'
    >>> absTime, refTime, OutWav, refwav = read_LS_FBG(filepath)
    
    >>> # With extended output (channel-wise dictionary)
    >>> dict_data, dict_time = read_LS_FBG(filepath, extended=True)
    
    """
    absTime = []
    refTime = []

    try:
        with open(filepath, mode='r', newline='') as file:
            reader = csv.reader(file)

            # Iterate over each row in the CSV file
            for i, row in enumerate(reader):
                if i == 0:
                    continue  # Skip the header
                
                # Split the row by tab and process data
                lst = str(row[0]).split('\t')
                wav = np.array(np.hsplit(np.array(lst[2:]), nChannel), dtype=float)
                wav = wav[:nChannel, :maxFBGs]
                wav = wav.reshape((nChannel, maxFBGs, 1))

                # Initialize reference wavelength if not provided
                if i == 1 and refwav is None:
                    refwav = wav
                
                # Check for wavelength shifts larger than 3 nm
                '''
                if wav.shape == refwav.shape and (np.abs(wav - refwav) > 3.).any():
                    warnings.warn("A shift of more than 3 nm has been found. Attempting automatic correction.")
                    wav = fbg_verifier(refwav, wav, nFBG=maxFBGs)
                '''
                
                # Replace zeros with NaNs
                wav = np.where(wav == 0, np.nan, wav)

                # Initialize output arrays
                if i == 1:
                    print('Starting file:', filepath)
                    absTime.append(lst[0]), refTime.append(float(lst[1]))
                    OutWav = wav
                else:
                    # Append data to output arrays
                    OutWav = np.append(OutWav, wav, axis=2)
                    absTime.append(lst[0]), refTime.append(float(lst[1]))
    
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return None

    # Convert time to numpy datetime64 format
    absTime = np.array(absTime, dtype='datetime64[ns]')

    # Return extended dictionary format if required
    if extended :
        dict_data, dict_time = dict(), dict()
        for ch in range(1,nChannel+1) :
            dict_data['Channel_%i' %ch] = (['Channel %i : FBGs' %ch, "Channel %i : Over time" %ch], OutWav[ch-1,:,:])
            dict_time['Channel_%i_time' %ch] = absTime
        return dict_data, dict_time
    
    return absTime, np.array(refTime), OutWav, refwav


def folder_read(path, nChannel=8, maxFBGs=12):
    """
    Reads all the FBG data files in the specified folder, processes them,
    and exports the data to NetCDF format.

    Parameters
    ----------
    path : str
        Path to the folder containing FBG data files.
    
    nChannel : int, optional
        Number of channels to process. Default is 8.
    
    maxFBGs : int, optional
        Maximum number of FBGs per channel. Default is 12.
    """
    files = os.listdir(path)
    files.sort()
    ji = 0
    
    for file in files:
        if not file.endswith('Z.txt'):  # Use Pythonic way to check file extension
            continue

        try:
            # Read the current FBG file
            dict_data, dict_time = read(path + file, nChannel=nChannel, maxFBGs=maxFBGs, extended=True)
            mode = 'PerCH'
        except Exception as e:
            print(f"Error reading file {file}: {e}")
            continue  # Skip the file and move to the next

        if ji == 0:
            ALL_dict_data, ALL_dict_time = dict_data.copy(), dict_time.copy()
            ji += 1
            continue
        
        for i, name in enumerate(dict_data):
            ch = i + 1
            name_time = f'Channel_{ch}_time'
            
            # Merge the time arrays and the data arrays
            ALL_dict_time[name_time] = np.append(ALL_dict_time[name_time], dict_time[name_time])
            out_chann_arr = np.append(ALL_dict_data[name][1], dict_data[name][1], axis=1)
            
            ALL_dict_data[name] = (['Channel %i : FBGs' % ch, "Channel %i : Over time" % ch], out_chann_arr)
            
            del out_chann_arr
        
        # If a day change is detected, process and export the data up to that point
        if verif_date(ALL_dict_time['Channel_1_time']):
            absTime = np.array(ALL_dict_time['Channel_1_time'], dtype='datetime64[ns]')
            IdxEndTime = np.where(absTime.astype('datetime64[D]') == absTime[-1].astype('datetime64[D]'))[0][0]
            
            OUT_dict_time, OUT_dict_data = dict(), dict()
            
            for ch in range(1, nChannel + 1):
                # Split the time and data arrays at the detected day change
                OUT_dict_time[f'Channel_{ch}_time'] = ALL_dict_time[f'Channel_{ch}_time'][:IdxEndTime].copy()
                OUT_dict_data[f'Channel_{ch}'] = (['Channel %i : FBGs' % ch, "Channel %i : Over time" % ch], ALL_dict_data[f'Channel_{ch}'][1][:, :IdxEndTime])
                
                out_chann_arr = ALL_dict_data[f'Channel_{ch}'][1][:, IdxEndTime:].copy()
                
                ALL_dict_time[f'Channel_{ch}_time'] = ALL_dict_time[f'Channel_{ch}_time'][IdxEndTime:].copy()
                ALL_dict_data[f'Channel_{ch}'] = (['Channel %i : FBGs' % ch, "Channel %i : Over time" % ch], out_chann_arr)
            
            try:
                export_nc(OUT_dict_data, OUT_dict_time, mode=mode)
                print(f"Exported data for {file} (up to day change)")
            except Exception as e:
                print(f"Error exporting data for {file}: {e}")
            
            del OUT_dict_data, OUT_dict_time, out_chann_arr
    
    # Try to export remaining data after processing all files
    try:
        export_nc(ALL_dict_data, ALL_dict_time, mode=mode)
        print(f"Final export completed for folder: {path}")
    except Exception as e:
        print(f"Error in final export: {e}")