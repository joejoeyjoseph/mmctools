"""
Data readers for remote sensing devices (e.g., 3D data)

Based on https://github.com/NWTC/datatools/blob/master/remote_sensing.py
"""
import numpy as np
import pandas as pd


def profiler(fname,scans=None,
        check_na=['SPD','DIR'],na_values=999999,
        read_scan_properties=False,
        verbose=False):
    """Wind Profiler radar with RASS

    Users:
    - Earth Sciences Research Laboratory (ESRL)
    - Texas Tech University (TTU)

    Assumed data format for consensus data format rev 5.1 based on
    provided reference for rev 4.1 from:
    https://a2e.energy.gov/data/wfip2/attach/915mhz-cns-winds-data-format.txt
    - Winds variables of interest: SPD, DIR(, SNR)
    - RASS variables of interest: T, Tc, W

    Additional data format reference:
    https://www.esrl.noaa.gov/psd/data/obs/formats/

    Usage
    =====
    scans : int, list, or None
        Number of data blocks to read from file; a list of zero-indexed
        scans to read from file; or set to None to read all data
    check_na : list
        Column names from file to check for n/a or nan values
    na_values : values or list of values
        Values to be considered n/a and set to nan
    read_scan_properties : bool, list, optional
        Read scan properties for each data block if True or an existing
        scan information list is provided (to be updated)
    """
    dataframes = []
    if read_scan_properties == True:
        scantypes = []
    else:
        # scantypes provided as a list of dicts
        assert isinstance(read_scan_properties, list)
        scantypes = read_scan_properties
        read_scan_properties = True
    def match_scan_type(newscan):
        assert (newscan is not None)
        match = False
        for itype, scaninfo in enumerate(scantypes):
            if newscan==scaninfo:
                match = True
                break
        if match:
            scantypeid = itype
        else:
            # new scan type
            scantypes.append(newscan)
            scantypeid = len(scantypes)-1
        return scantypeid
    with open(fname,'r') as f:
        if scans is not None:
            if hasattr(scans,'__iter__'):
                # specified scans to read
                scans_to_read = np.arange(np.max(scans)+1)
            else:
                # specified number of scans
                scans_to_read = np.arange(scans)
                scans = scans_to_read
            for i in scans_to_read:
                try:
                    df,scaninfo = _read_profiler_data_block(f,read_scan_properties)
                except (IOError,IndexError):
                    break
                if i in scans:
                    if verbose:
                        print('Adding scan',i)
                    if read_scan_properties:
                        df['scan_type'] = match_scan_type(scaninfo)
                    dataframes.append(df)
                else:
                    if verbose:
                        print('Skipping scan',i)
        else:
            # read all scans
            i = 0
            while True:
                try:
                    df,scaninfo = _read_profiler_data_block(f,read_scan_properties)
                except (IOError,IndexError):
                    break
                else:
                    if verbose:
                        print('Read scan',i)
                    if read_scan_properties:
                        df['scan_type'] = match_scan_type(scaninfo)
                    dataframes.append(df)
                    i += 1
    df = pd.concat(dataframes)
    if na_values is not None:
        nalist = []
        for col in check_na:
            if col in df.columns:
                matches = [col]
            else:
                matches = [ c for c in df.columns if c.startswith(col+'.') ]
            if len(matches) > 0:
                nalist += matches
            else:
                if verbose:
                    print('Note: column '+col+'* not found')
        check_na = nalist
        if not hasattr(na_values,'__iter__'):
            na_values = [na_values]
        for val in na_values:
            for col in check_na:
                if verbose:
                    print('Checking',col,'for',val)
                df.loc[df[col]==val,col] = np.nan # flag bad values
    if read_scan_properties and verbose:
        for itype,scantype in enumerate(scantypes):
            print('scan type',itype,scantype)
    return df

def _read_profiler_data_block(f, read_scan_properties=False,
                              expected_datatypes=['WINDS','RASS']):
    """Used by radar profiler"""
    # Line 1 (may not be present for subsequent blocks within the same file
    name = f.readline().strip()
    if name == '':
        # Line 2: station name
        name = f.readline().strip()
    # Line 3: WINDS, version
    data_format = f.readline().strip()
    datatype = data_format.split()[0]
    assert(datatype in expected_datatypes)
    # Line 4: lat (N), long (W), elevation (m)
    lat,lon,elev = [float(val) for val in f.readline().split()]
    # Line 5: date
    Y,m,d,H,M,S,_ = f.readline().split()
    datetime = pd.to_datetime('20{}{}{} {}{}{}'.format(Y,m,d,H,M,S))
    if read_scan_properties:
        # Line 6: consensus averaging time [min], # beams, # range gates
        cns_avg_time, num_beams, num_ranges = [int(val) for val in f.readline().split()]
        # Line 7: for each beam: num_records:tot_records (consensus_window_size)
        lineitems = f.readline().split()
        assert len(lineitems) == 2*num_beams
        num_records = [int(item.split(':')[0]) for item in lineitems[::2]]
        tot_records = [int(item.split(':')[1]) for item in lineitems[::2]]
        cns_window_size = [float(item.strip('()')) for item in lineitems[1::2]]
        # Line 8: processing info (oblique/vertical pairs)
        lineitems = [int(val) for val in f.readline().split()]
        num_coherent_integrations = lineitems[:2]
        num_spectral_averages = lineitems[2:4]
        pulse_width = lineitems[4:6] # [ns]
        inner_pulse_period = lineitems[6:8] # [ms]
        # Line 9: processing info (oblique/vertical pairs)
        lineitems = f.readline().split()
        doppler_value = [float(val) for val in lineitems[:2]] # [m/s]
        vertical_correction = bool(lineitems[2])
        delay = [int(val) for val in lineitems[3:5]] # [ns]
        num_gates = [int(val) for val in lineitems[5:7]]
        gate_spacing = [int(val) for val in lineitems[7:9]] # [ns]
        # Line 10: for each beam: azimuth, elevation
        lineitems = [float(val) for val in f.readline().split()]
        assert len(lineitems) == 2*num_beams
        beam_azimuth = lineitems[::2] # [deg]
        beam_elevation = lineitems[1::2] # [deg]
    else:
        f.readline()
        f.readline()
        f.readline()
        f.readline()
        f.readline()
    # Line 11: Column labels
    header = f.readline().split()
    header = [ col + '.' + str(header[:i].count(col))
               if header.count(col) > 1
               else col
               for i,col in enumerate(header) ]
    # Line 12: Start of data
    block = []
    line = f.readline()
    while not line.strip()=='$' and not line=='':
        block.append(line.split())
        line = f.readline()
    df = pd.DataFrame(data=block,columns=header,dtype=float)
    df['datetime'] = datetime
    # return data and header info if requested
    if read_scan_properties:
        scaninfo = {
            'station':name,
            'data_format':data_format,
            # Line 7
            'beam:reqd_records_for_consensus': num_records,
            'beam:tot_num_records': tot_records,
            'beam:consensus_window_size_m/s': cns_window_size,
            # Line 8
            'num_coherent_integrations': num_coherent_integrations,
            'num_spectral_averages': num_spectral_averages,
            'pulse_width_ns': pulse_width,
            'inner_pulse_period_ms': inner_pulse_period,
            # Line 9
            'fullscale_doppler_value_m/s': doppler_value,
            'vertical_correction_to_obliques': vertical_correction,
            'delay_to_first_gate_ns': delay,
            'num_gates': num_gates,
            'gate_spacing_ns': gate_spacing,
            # Line 10
            'beam:azimuth_deg': beam_azimuth,
            'beam:elevation_deg': beam_elevation,
        }
        return df, scaninfo
    else:
        return df, None
