# Copyright 2020 NREL

# Licensed under the Apache License, Version 2.0 (the "License"); you may not use
# this file except in compliance with the License. You may obtain a copy of the
# License at http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software distributed
# under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.

"""
Class for reading in `set` type of OpenFOAM sampling 'probes'

written by Regis Thedin (regis.thedin@nrel.gov)

"""
from __future__ import print_function
import os
import pandas as pd
import numpy as np
from .reader import Reader

class ProbeSets(Reader):
    """Stores a time array (t), and field arrays as attributes. The
    fields have shape:
        (Nt, N[, Nd])
    where N is the number of probes and Nt is the number of samples.
    Vectors have an additional dimension to denote vector components.
    Symmetric tensors have an additional dimension to denote tensor components (xx, xy, xz, yy, yz, zz).
    
    The `set`-type of probe is used when large number of data points need to be saved.
    Therefore, this class differs from `Probe` and is tailored for the specification of 
    many sets and looping through the files with ease. The inputs of this class were created
    to make it easy to accomodate very large datasets, or only read a subset of the saved data.
    
    If the need of using `set` arises, chances are the naming of the probes will be complex and likely
    inlcude a sweep of a variable in its name. Due to that, the user can specify the name of the probes
    split into prefix, suffix, variable sweep, and variables to save. It is also possible to specify a
    sub-domain in which data is needed. It is assumed that all sets have the same points.

    Sample usage:
        
        from windtools.SOWFA6.postProcessing.probeSets import ProbeSets
        
        # read all times, all variables
        probeData = ProbeSet('path/to/case/postProcessing/probeName')
        
        # read specified fields
        probeData = ProbeSet('path/to/case/PostProcessing/probeName', varList['U','T'])
        
        # read specified sub-domain
        probeData = ProbeSet('path/to/case/postProcessing/probeName', xi=-2500, xf=2500, yi=-2500, yf=2500)
        
        # read all and account for added perturbation on the sampling points
        probeData = ProbeSet('path/to/case/postProcessing/probeName', posPert=-0.01)
        
        # read specified time dirs
        probeData = ProbeSet('path/to/case/postProcessing/probeName', tstart=30000, tend=30100)
        
        # read certain files following complex naming convention
        # e.g. if the probes are specified as
        ```
        probeName
        {
            type sets;
            name pointcloud;
            // other settings...
            fields ( U T );
            sets
            (
                vmasts_h10
                {
                    type points;
                    // ...
                }
                vmasts_h20
                {
                    // ...
                }
                // ...
            )
        }
        ```
        # and the user wishes to read to vmasts_h{10,50}_{T,U}.xy, then:
        probeData = ProbeSet('path/to/case/postProcessing/probeName',
                    fprefix='vmasts_h', fparam=['10','50'], varList=['T','U'], fsuffix='.xy')
                    
    Notes:
        - If `varList` is not specified, then all the probes are read, ignoring prefix, sufix, and parameters
        - Pandas/dataframe is used internally even though the final object is of `Reader` type.

    """
    def __init__(self, dpath=None, tstart=None, tend=None, varList='all', posPert=0.0, 
                 xi=None, xf=None, yi=None, yf=None,
                 fprefix=None, fparam=None, fsuffix=None,
                 **kwargs):
        self.xi = xi
        self.xf = xf
        self.yi = yi
        self.yf = yf
        self.fprefix = fprefix
        self.fparam  = fparam
        self.fsuffix = fsuffix
        self.posPert = posPert
        self.tstart = tstart
        self.tend = tend
        self.varList = varList
        self._allVars = {'U','UMean','T','TMean','TPrimeUPrimeMean','UPrime2Mean','p_rgh'}
        super().__init__(dpath,includeDt=True,**kwargs)
            

    def _trimtimes(self,tdirList, tstart=None,tend=None):
        if (tstart is not None) or (tend is not None):
            if tstart is None: tstart = 0.0
            if tend is None: tend = 9e9
            selected = [ (t >= tstart) & (t <= tend) for t in self.times ]
            self.filelist = [tdirList[i] for i,b in enumerate(selected) if b ]
            self.times = [self.times[i] for i,b in enumerate(selected) if b ]
            self.Ntimes = len(self.times)
            try:
                tdirList = [tdirList[i] for i,b in enumerate(selected) if b ]
            except AttributeError:
                pass
        return tdirList
         
        
    def _processdirs(self, tdirList, trimOverlap=False, **kwargs):
        print('Probe data saved:',len(self.simStartTimes), 'time steps, from', \
              self.simStartTimes[0],'s to',self.simStartTimes[-1],'s')

        # make varList iterable if not already a list 
        varList = [self.varList] if not isinstance(self.varList, (list)) else self.varList
        # Create a list of all the probe files that will be processed
        if varList[0].lower()=='all':
            print('No varList given. Reading all probes.')
            outputs = [ fname for fname in os.listdir(tdirList[0])
                            if os.path.isfile(tdirList[0]+os.sep+fname) ]
        else:
            # Make values iterable if not specified list
            fprefix = [self.fprefix] if not isinstance(self.fprefix, (list)) else self.fprefix
            fparam  = [self.fparam]  if not isinstance(self.fparam,  (list)) else self.fparam
            fsuffix = [self.fsuffix] if not isinstance(self.fsuffix, (list)) else self.fsuffix
            # create a varList that contains all the files names
            fileList = []
            for var in varList:
                for prefix in fprefix:
                    for param in fparam:
                        for suffix in fsuffix:
                            fileList.append( prefix + param + '_' + var + suffix )
            outputs = fileList

        # Get list of times and trim the data
        self.times = [float(os.path.basename(p)) for p in self.simTimeDirs]
        tdirList = self._trimtimes(tdirList,self.tstart,self.tend)
        
        try:
            print('Probe data requested:',len(tdirList), 'time steps, from', \
                  float(os.path.basename(tdirList[0])),'s to', \
                  float(os.path.basename(tdirList[-1])),'s')
        except IndexError:
            raise ValueError('End time needs to be greater than the start time')
                
        # Raise an error if list is empty
        if not tdirList:
            raise ValueError('No time directories found')
        
        # Process all data
        for field in outputs:
            arrays = [ self._read_data( tdir,field ) for tdir in tdirList ]
            # combine into a single array and trim end of time series
            arrays = np.concatenate(arrays)[:self.imax,:]    
            # parse the name to create the right variable
            param, var = self._parseProbeName(field)
            # add the zagl to the array
            arrays = np.hstack((arrays[:,:4], \
                                np.full((arrays.shape[0],1),param), \
                                arrays[:,4:]))
            # append to (or create) a variable attribute
            try:
                setattr(self,var,np.concatenate((getattr(self,var),arrays)))
            except AttributeError:
                setattr( self, var, arrays )
                
            if not var in self._processed:   
                self._processed.append(var)
            print('  read',field) 

        self.t = np.unique(arrays[:,0])
        self.Nt = len(self.t)
        
        # sort times
        for var in self._allVars:
            try:
                self.var = self.var[np.argsort(self.var[:,0])]
            except AttributeError:
                pass    

        
    def _parseProbeName(self, field):
        # Example: get 'vmasts_50mGrid_h30_T.xy' and return param=30, var='T'
        # Remove the prefix from the full field name
        f = field.replace(self.fprefix,'')
        # Substitude the first underscore with a dot and split array
        f = f.replace('_','.',1).split('.')
        for i in set(f).intersection(self._allVars):
            var = i
        param = int(f[-3])
        return param, var
    
        
    def _read_data(self, dpath, fname): 
        fpath = dpath + os.sep + fname    
        currentTime = float(os.path.basename(dpath))
        with open(fpath) as f:
            try:
                # read the actual data from probes
                array = self._read_probe_posAndData(f)
                # add current time step info to first column
                array = np.c_[np.full(array.shape[0],currentTime), array]
            except IOError:
                print('unable to read '+ fpath) 
        return array
    
    
    def _read_probe_posAndData(self,f):
        out = []
        # Pandas is a LOT faster than reading the file line by line
        out = pd.read_csv(f.name,header=None,comment='#',sep='\t')
        # Add position perturbation to x, y, zabs
        out[[0,1,2]] = out[[0,1,2]].add(self.posPert)
        # clip spatial data
        out = self._trimpositions(out, self.xi, self.xf, self.yi, self.yf)
        out = out.to_numpy(dtype=float)
        self.N = len(out)
        return out
     
    
    def _trimpositions(self, df, xi=None,xf=None, yi=None, yf=None):
        if (xi is not None) and (xf is not None):
            df = df.loc[ (df[0]>=xi) & (df[0]<=xf) ]
        elif xi is not None:
            df = df.loc[ df[0]>=xi ]
        elif xf is not None:
            df = df.loc[ df[0]<=xf ]

        if (yi is not None) and (yf is not None):
            df = df.loc[ (df[1]>=yi) & (df[1]<=yf) ]
        elif yi is not None:
            df = df.loc[ df[1]>=yi ]
        elif yf is not None:
            df = df.loc[ df[1]<=yf ]
                
        return df
    

    #============================================================================
    #
    # DATA I/O
    #
    #============================================================================

    def to_pandas(self,itime=None,fields=None,dtype=None):
        #output all vars
        if fields is None:
            fields = self._processed
        # select time range
        if itime is None:
            tindices = range(len(self.t))
        else:
            try:
                iter(itime)
            except TypeError:
                # specified single time index
                tindices = [itime]
            else:
                # specified list of indices
                tindices = itime
                
        # create dataframes for each field
        print('Creating dataframe ...')
        data = {}
        for var in fields:
            print('processing', var)
            F = getattr(self,var)          
            # Fill in data
            data['time'] = F[:,0]
            data['x'] = F[:,1]
            data['y'] = F[:,2]
            data['zabs'] = F[:,3]
            data['zagl'] = F[:,4]
            if F.shape[1]==6:
                # scalar
                data[var] = F[:,5:].flatten()
            elif F.shape[1]==8:
                # vector
                for j,name in enumerate(['x','y','z']):
                    data[var+name] = F[:,5+j].flatten()
            elif F.shape[1]==11:
                # symmetric tensor
                for j,name in enumerate(['xx','xy','xz','yy','yz','zz']):
                    data[var+name] = F[:,5+j].flatten()
                    
        df = pd.DataFrame(data=data,dtype=dtype)
        return df.sort_values(['time','x','y','zabs','zagl']).set_index(['time','x','y','zagl'])
        
    def to_netcdf(self,fname,fieldDescriptions={},fieldUnits={}):
        raise NotImplementedError('Not available for ProbeSet class.')
