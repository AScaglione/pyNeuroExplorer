'''
This module contains functions to read the *.nev(spikes) and *.nsx (lfp)
data.
This module has three parts:
1. Read NEV files
2. Read NSX files
3. Utilities to bundle operations

All the functions can be called separatedly, nevertheless, it is preferable

Usage: after importing the library:

import m_BlackrockLib as BL
BL.bin2h5() --> will ask for the files, optionally can be parsed as inputs

This module is based on the neurapy module by Kaushik Ghose https://github.com/kghose/neurapy
'''
##### IMPORTS ########################################################################

import os, struct, tables, pickle, re, shutil
from glob import glob
import numpy as np
from PyQt4 import QtGui, QtCore
import guidata.dataset.dataitems as di
import guidata.dataset.datatypes as dt
import guidata
app = guidata.qapplication()

pth = os.path.expanduser('~')

######################################################################################
############ FIRST PART OF THE MODULE HAS FUNCTIONS TO READ THE NEV FILES ############
######################################################################################

def read_basic_header(f):
    """Given a freshly opened file handle, read us the basic nev header"""

    f.seek(0, 2)#skip to end
    file_length_in_bytes = f.tell()
    f.seek(0)#skip back to start
    basic_header = {}
    basic_header['file type id'] = f.read(8)
    basic_header['file spec']    = f.read(2)
    additional_flags = f.read(2)
    basic_header['spike waveform is 16bit']      = bool(ord(additional_flags[0]))
    basic_header['bytes in headers'],            = struct.unpack('I',  f.read(4))
    basic_header['bytes in data packets'],       = struct.unpack('I',  f.read(4))
    basic_header['time stamp resolution Hz'],    = struct.unpack('I',  f.read(4))
    basic_header['neural sample resolution Hz'], = struct.unpack('I',  f.read(4))
    basic_header['time origin']                  = struct.unpack('8H', f.read(16))
    basic_header['creator']                      = f.read(32)
    basic_header['comment']                      = f.read(256)
    basic_header['number of extended headers'],  = struct.unpack('I', f.read(4))

    #This is for us, not stored in the actual file
    basic_header['file size']     = file_length_in_bytes
    basic_header['total packets'] = (basic_header['file size'] -\
                                     basic_header['bytes in headers'])\
                                     /basic_header['bytes in data packets']

    return basic_header

######################################################################################

def read_extended_header(f, basic_header):
    """Given a file handle and the basic_header, read the extended header. File
    should be spun forward past the basic header"""

    n_extended_headers = basic_header['number of extended headers']

    # Extended header
    extended_header = {}
    extended_header['comments'] = []
    extended_header['neural event waveform']          = {} #NEUEVWAV
    extended_header['neural event label']             = {} #NEUEVLBL
    extended_header['neural event filter']            = {} #NEUEVFLT
    extended_header['digital label']                  = {} #DIGLABEL
    extended_header['NSAS expt information channels'] = {} #NSASEXEV

    extended_header['other packets'] = []
    for nhdr in range(n_extended_headers):
        packet_id = f.read(8)
        payload = f.read(24)
        if packet_id == 'ARRAYNME':
            extended_header['electrode array'] = payload
        elif packet_id == 'ECOMMENT':
            extended_header['comments'].append(payload)
        elif packet_id == 'CCOMMENT':
            extended_header['comments'][-1] += payload
        elif packet_id == 'MAPFILE':
            extended_header['map file'] = payload
        elif packet_id == 'NEUEVWAV':
            parse_neuevwav(extended_header['neural event waveform'],
                           packet_id, payload)
        else:
            extended_header['other packets'].append([packet_id, payload])

    return extended_header

##########################################################################################

def parse_neuevwav(neural_event_waveform_dict, packet_id, payload):
    """Given that we know this is a NEUEVWAV packet, parse it and insert it into
    the dict"""
    electrode_info_dict = {}
    offset = 0
    electrode_id, = struct.unpack_from('H', payload)
    offset += 2
    electrode_info_dict['physical connector'], = struct.unpack_from('B', payload, offset)
    offset += 1
    electrode_info_dict['connector pin'], = struct.unpack_from('B', payload, offset)
    offset += 1
    electrode_info_dict['nV per LSB'], = struct.unpack_from('H', payload, offset)
    offset += 2
    electrode_info_dict['energy threshold'], = struct.unpack_from('H', payload, offset)
    offset += 2
    electrode_info_dict['high threshold uV'], = struct.unpack_from('h', payload, offset)
    offset += 2
    electrode_info_dict['low threshold uV'], = struct.unpack_from('h', payload, offset)
    offset += 2
    electrode_info_dict['number of sorted units'], = struct.unpack_from('B', payload, offset)
    offset += 1
    electrode_info_dict['bytes per waveform sample'], = struct.unpack_from('B', payload, offset)
    offset += 1

    neural_event_waveform_dict[electrode_id] = electrode_info_dict

##########################################################################################
    
def rewind(f, basic_header):
    """Position file pointer at start of packet data"""
    bytes_in_headers = basic_header['bytes in headers']
    f.seek(bytes_in_headers, 0) #we are now positioned at the start of the data packets
    
##########################################################################################
    
def addSpikes2H5(h5file, pth, bas_header, ext_header, pd = None):

    if type(h5file) != tables.file.File:
        return

    # create a group to store spikes
    h5file.createGroup('/','Spikes')

    # get a list with the files to process
    files = glob(os.path.join(pth,'channel*'))
    files.sort()

    # read some parameters from the headers
    channel_info_dict         = ext_header['neural event waveform'][1]
    bytes_in_data_packets     = bas_header['bytes in data packets']
    bytes_per_waveform_sample = channel_info_dict['bytes per waveform sample']
    waveform_format = 'h'
    waveform_size   = (bytes_in_data_packets - 8)/bytes_per_waveform_sample
    Fs = float(bas_header['time stamp resolution Hz'])
    Ts = 1.0/Fs
    
    # iterate over the list of fragments
    for n,f in enumerate(files):

        if pd is not None:
            # animate progression bar
            pd.setLabelText('%s' % f)
            pd.setValue(n+1)

        # open binary fragment
        fid      = open(f, 'rb')

        waveform = []
        TS       = []
 
        while 1:
            # read "bytes_in_data_packets" from the current position
            w = fid.read(bytes_in_data_packets)

            # exit if the number of read bytes is less than expected
            if len(w) < bytes_in_data_packets: break

            # transform the waveform and timestamp data into a number
            waveform.append(np.array(struct.unpack(waveform_size*waveform_format, w[8:]),
                                     dtype = np.int16))
            TS.append(struct.unpack('I', w[0:4])[0] * Ts * 1000)

        # close fragment
        fid.close()
        
        # if the channel doesen't contain waveforms or timestamps:
        if not waveform or not TS: continue

        # transform waveforms and timestamps into 16 bits integer array
        waveform = np.array(waveform, dtype=np.int16)
        TS       = np.array(TS)
        Unsorted = np.arange(len(TS))

        # create the groups and arrays inside the h5file
        # to host the information
        chName = 'Chan_%03d' % (n+1)
        h5file.createGroup('/Spikes', chName)
        h5file.createArray('/Spikes/'+chName,'Waveforms', waveform)
        h5file.createArray('/Spikes/'+chName,'TimeStamp', TS)
        h5file.createArray('/Spikes/'+chName,'Unsorted',  Unsorted)
        h5file.createArray('/Spikes/'+chName,'isMultiunit', False)
        h5file.createArray('/Spikes/'+chName,'isTrash',   False)

    # add header information to the h5 file
    if not h5file.__contains__('/Header'):
        h5file.createGroup('/','Header')
    h5file.createArray('/Header', 'WaveformSize', waveform_size)
    h5file.createArray('/Header', 'TimeStamp_Res', Fs)

    # save changes to disk
    h5file.flush()
        
##########################################################################################

def addNonNeural2H5(h5file, pth, bas_header, pd = None):

    # read the non neural data
    Timestamps, code = read_frag_nonneural_digital(pth, bas_header)

    # read the bit changes in the binary codes
    if not np.any(code): return

    # animate progression bar
    if pd is not None:
        pd.setLabelText('Adding Non Neural Data ...')
        pd.setValue(pd.value()+1)
        
    binCode = np.int8([ map(int, np.binary_repr(k, width = 16)) for k in code], ndmin=2)
    tmp     = np.ones( shape = (1, binCode.shape[1]), dtype = np.int8)
    tmp     = np.append(tmp, binCode, axis = 0)
    dx      = np.diff(tmp, n=1, axis=0)
    L       = dx.shape[1]
    ton     = []
    toff    = []
    
    for k in range(1, L+1):
        ton.append(Timestamps[dx[:,-k]<0])
        toff.append(Timestamps[dx[:,-k]>0])

    # create the group and leaves to hold the non neural data
    h5file.createGroup('/','Non_Neural_Events')
    h5file.createGroup('/Non_Neural_Events', 'ton')
    h5file.createGroup('/Non_Neural_Events', 'toff')
    
    for j, k in enumerate(ton):
        if len(k)>0:
            h5file.createArray('/Non_Neural_Events/ton', 'ton_%02d' % j, k)

    for j, k in enumerate(toff):
        if len(k)>0:
            h5file.createArray('/Non_Neural_Events/toff', 'toff_%02d' % j, k)

    # save changes to disk
    h5file.flush()
                
##########################################################################################
    
def ext_fragments(filename=None, outdir=None):
    '''
    Wrapper for the 'fragment' function. It reads the headers from the
    nev file and uses that to extract the package files
    '''

    fid = open(filename, 'rb')
    bas_header = read_basic_header(fid)
    ext_header = read_extended_header(fid, bas_header)

    fname  = os.path.split(filename)[1]
    outdir = os.path.join(outdir, fname[0:fname.find('.')])

    # create a directory if it doesn't exists
    if not os.path.isdir(outdir): os.mkdir(outdir)

    # save headers to a pickled file
    headers = open(os.path.join(outdir,'headers.p'),'wb')
    pickle.dump([bas_header, ext_header], headers)
    headers.close()

    # run the extraction function
    fragment(fid,
             bas_header,
             ext_header,
             channel_list = np.arange(1,65),
             frag_dir = outdir,
             ignore_spike_sorting = True)
    fid.close()

    # return the output directory
    return outdir

##########################################################################################

def fragment(f, basic_header, extended_header,
             frag_dir = 'myspikes/',
             channel_list = np.arange(1,97),
             ignore_spike_sorting = True):
    
    """Given a list of electrodes this will start from the beginning of the file
    and simply dump the spike times and the waveform for each electrode in a
    separate file.
    This automatically includes the non-neural events.
    Electrode numbering follows Cerebrus conventions i.e. starting from 1

    We might want to rewrite this in C and wrap a python module round it:
    http://starship.python.net/crew/mwh/toext/less-trivial.html

    Inputs:
    f - pointer to nev file
    basic_header
    extended_header - both read from the nev file
    channel_list - all the required channels
    ignore_spike_sorting - if true, ignore any online sorted units and dump
                           everything to unit 0
    """

    if not os.path.exists(frag_dir):
        os.makedirs(frag_dir)

    #Open file
    fnonneural = open(frag_dir + '/nonneural.bin', 'wb')

    #open files for all the units
    if channel_list.size > 0:
        fout = [None]*(channel_list.max())
    else:
        fout = []
    neuw = extended_header['neural event waveform']
    #print 'fragment: warning, for debugging purposes, fixing sorted units as 4 per electrode'
    for channel in channel_list:
        if not ignore_spike_sorting:
            units_classified = neuw[channel]['number of sorted units']
        else:
            units_classified = 0

        #units_classified = 4
        fout[channel-1] = [None]*(units_classified+1) #0 is always the unclassified one
        for m in range(units_classified+1):
            fname = frag_dir + '/channel%02dunit%02d.bin' %(channel,m)
            fout[channel-1][m] = open(fname, 'wb')

    #Now just rewind and start redirecting the packets
    rewind(f, basic_header)

    bytes_in_data_packets = basic_header['bytes in data packets']
    eof = False
    premature_eof = False
    nnev_counter = 0

    percent_packets_read = 0
    one_percent_packets = basic_header['total packets']/100
    packet_counter = one_percent_packets

    while not eof:
        #Read the packet header
        header_buffer = f.read(6)
        if len(header_buffer) < 6:
            eof = True
            if len(header_buffer) > 0:
                #This means we got cut off in an odd manner
                premature_eof = True
                rewind(f, basic_header)
        else:
            pi, = struct.unpack('H', header_buffer[4:])#packet id
            if pi == 0:
                fnonneural.write(header_buffer)
                fnonneural.write(f.read(bytes_in_data_packets - 6))
                nnev_counter += 1
            elif pi in channel_list:
                buffer = f.read(bytes_in_data_packets - 6)
                if not ignore_spike_sorting:
                    sub_unit, =  struct.unpack('B', buffer[0])
                else:
                    sub_unit = 0
                thisfptr = fout[pi-1][sub_unit]

                thisfptr.write(header_buffer)
                thisfptr.write(buffer)
                #Note that even if we ignore online spike sorting, we preserve the unit
                #identity
            else:
                f.seek(bytes_in_data_packets - 6, 1) #skip appropriate number of bytes

        packet_counter -= 1
        if packet_counter == 0:
            percent_packets_read += 1
            packet_counter = one_percent_packets

    return not premature_eof #return false if there was a problem

##########################################################################################

def read_frag_nonneural_digital(frag_dir, basic_header):
    """Read the nonneural packets (packet id 0) and return the timestamps and the
    value of the digital input port.

    Inputs:
    frag_dir - the directory the fragmented data is in
    basic_header - from reading the nev file

    Ouputs:
    time_stamps - absolute times in ms (to match with lablib convention)
    codes - value of the digital input port"""

    #Open file
    f = open(os.path.join(frag_dir, 'nonneural.bin'),'rb')
    f.seek(0,2)
    file_length_in_bytes = f.tell()
    f.seek(0)#skip back to start

    Fs = float(basic_header['time stamp resolution Hz'])
    T_ms = 1000.0/Fs #ms in one clock cycle
    bytes_in_data_packets = basic_header['bytes in data packets']

    N = file_length_in_bytes/bytes_in_data_packets
    
    time_stamp_ms = np.zeros(N, dtype='float32')
    codes = np.zeros(N, dtype='uint16')

    eof = False
    premature_eof = False
    counter = 0
    
    while not eof:
        buffer = f.read(bytes_in_data_packets)
        if len(buffer) < bytes_in_data_packets:
            eof = True
            if len(buffer) > 0:
                #This means we got cut off in an odd manner
                premature_eof = True
        else:
            timestamp, = struct.unpack('I', buffer[0:4])
            time_stamp_ms[counter] = timestamp * T_ms
            codes[counter], = struct.unpack('H', buffer[8:10])
            counter += 1

    return time_stamp_ms[:counter], codes[:counter]

##########################################################################################
######## FUNCTIONS TO READ THE CONTINOUS DATA (LFP) ######################################
##########################################################################################

def list2str(List):
    ''' helper function to transform a list into a string '''
    tmp=''
    for k in List: tmp = tmp + k
    return tmp

##########################################################################################

def readNS2(filename = None):
    '''reads the ns5 file and returns a dictionary with all the data structure'''

    # return if not filename provided
    if filename is None: return

    # get the path and the filename
    path  = os.path.split(filename)[0]
    fname = os.path.split(filename)[1]
    NSx   = dict(MetaTags={}, ElectrodesInfo={})

    # Defining constants
    ExtHeaderLength = 66
    elecReading     = 1
    maxNSPChannels  = 128
    pausedFile      = 0

    # Give all input arguments a default value. All input argumens are optional.
    Report        = 'noreport'
    ReadData      = 'read'
    StartPacket   = 0
    TimeScale     = 'sample'
    precisionType = '*short=>short'
    skipFactor    = 1
    modifiedTime  = 0

    # use the fromfile function from numpy. Read everything as unsiged int8
    FData = np.fromfile(os.path.join(path, fname), dtype = np.uint8)

    # read meta information
    NSx['MetaTags']['Filename']     = fname
    NSx['MetaTags']['FilePath']     = path
    NSx['MetaTags']['FileExt']      = re.search('(?<=\.)[a-zA-z0-9]*', fname).group()
    NSx['MetaTags']['FileTypeID']   = FData[0:8].tostring()
    NSx['MetaTags']['openNSxver'] = '4.2.1.4'

    vchar = np.vectorize(chr)

    # currently we can only read "NEURALCD" files
    if NSx['MetaTags']['FileTypeID'] != 'NEURALCD': return

    # get basic information
    BasicHeader                      = FData[8:8+306]
    NSx['MetaTags']['FileSpec']      = '%d.%d' % (BasicHeader[0], BasicHeader[1])
    NSx['MetaTags']['SamplingLabel'] = BasicHeader[6:22].tostring()
    NSx['MetaTags']['Comment']       = BasicHeader[22:278].tostring()
    NSx['MetaTags']['TimeRes']       = BasicHeader[282:286].view(np.uint32)[0]
    NSx['MetaTags']['SamplingFreq']  = NSx['MetaTags']['TimeRes'] / np.double(BasicHeader[278:282].view(np.uint32))

    # read the date time information
    t                              = BasicHeader[286:302].view(np.uint16)
    NSx['MetaTags']['DateTimeRaw'] = t
    NSx['MetaTags']['DateTime']    = str(t[1])+'/'+str(t[3])+'/'+str(t[0])+\
                                     ' '+str(t[4])+':'+str(t[5])+':'+str(t[6])+'.'+str(t[7])

    # get the number of channels
    ChannelCount                     = BasicHeader[302:306].view(np.uint32)[0]
    NSx['MetaTags']['ChannelCount']  = ChannelCount

    # get the extended header
    curpos = 8 + 306
    readSize        = np.int32(ChannelCount * ExtHeaderLength)
    ExtendedHeader  = FData[curpos : curpos + readSize]
    curpos          = curpos + readSize

    # check if file is corrupted
    if FData[curpos] != 1:
        print 'Cannot read file. Data header is corrupted!'
        return

    NSx['MetaTags']['Timestamp']  = FData[curpos+1:curpos+5].view(np.uint32)[0]
    curpos = curpos + 5
    NSx['MetaTags']['DataPoints'] = FData[curpos:curpos+4].view(np.uint32)[0]
    curpos = curpos + 4


    NSx['ElectrodesInfo'] = []
    ##  Populating extended header information
    for headerIDX in range(0, ChannelCount):
        offset = (headerIDX)*ExtHeaderLength

        NSx['ElectrodesInfo'].append({})

        NSx['ElectrodesInfo'][headerIDX]['Type'] = list2str(vchar(ExtendedHeader[np.arange(0,2)+offset]))
        if NSx['ElectrodesInfo'][headerIDX]['Type'] != 'CC':
            print 'extended header not supported'
            return

        NSx['ElectrodesInfo'][headerIDX]['ElectrodeID']    = ExtendedHeader[np.arange(2,4)+offset].view(np.uint16)[0]
        NSx['ElectrodesInfo'][headerIDX]['Label']          = list2str(vchar(ExtendedHeader[np.arange(4,20)+offset]))
        NSx['ElectrodesInfo'][headerIDX]['ConnectorBank']  = chr(ExtendedHeader[20+offset] + ord('A') - 1)
        NSx['ElectrodesInfo'][headerIDX]['ConnectorPin']   = ExtendedHeader[21+offset]
        NSx['ElectrodesInfo'][headerIDX]['MinDigiValue']   = ExtendedHeader[np.arange(22,24)+offset].view(np.int16)[0]
        NSx['ElectrodesInfo'][headerIDX]['MaxDigiValue']   = ExtendedHeader[np.arange(24,26)+offset].view(np.int16)[0]
        NSx['ElectrodesInfo'][headerIDX]['MinAnalogValue'] = ExtendedHeader[np.arange(26,28)+offset].view(np.int16)[0]
        NSx['ElectrodesInfo'][headerIDX]['MaxAnalogValue'] = ExtendedHeader[np.arange(28,30)+offset].view(np.int16)[0]
        NSx['ElectrodesInfo'][headerIDX]['AnalogUnits']    = list2str(vchar(ExtendedHeader[np.arange(30,46)+offset]))
        NSx['ElectrodesInfo'][headerIDX]['HighFreqCorner'] = ExtendedHeader[np.arange(46,50)+offset].view(np.uint32)[0]
        NSx['ElectrodesInfo'][headerIDX]['HighFreqOrder']  = ExtendedHeader[np.arange(50,54)+offset].view(np.uint32)[0]
        NSx['ElectrodesInfo'][headerIDX]['HighFilterType'] = ExtendedHeader[np.arange(54,56)+offset].view(np.uint16)[0]
        NSx['ElectrodesInfo'][headerIDX]['LowFreqCorner']  = ExtendedHeader[np.arange(56,60)+offset].view(np.uint32)[0]
        NSx['ElectrodesInfo'][headerIDX]['LowFreqOrder']   = ExtendedHeader[np.arange(60,64)+offset].view(np.uint32)[0]
        NSx['ElectrodesInfo'][headerIDX]['LowFilterType']  = ExtendedHeader[np.arange(64,66)+offset].view(np.uint16)[0]

    # finally get the data
    NSx['Data'] = FData[curpos:].view(np.int16)
    NSx['Data'] = NSx['Data'].reshape(NSx['Data'].size/ChannelCount, ChannelCount)

    return NSx

#################################################################################

def addLFP2h5(h5file = None, nsFileName = None, pd = None):
    '''Helper function to wrap the converter '''

    # select an h5file if none provided
    if not h5file:
        h5file =  str(QtGui.QFileDialog.getOpenFileName(filter = '*.h5'))
        if h5file:
            h5file = tables.openFile(h5file, 'a')
        else:
            if pd is not None:
                pd.setValue(pd.maximum()+1)
            return
    elif type(h5file) == str:
        h5file = tables.openFile(h5file, 'a')
        
    # select an ns5 file
    if not nsFileName:
        nsFileName = str(QtGui.QFileDialog.getOpenFileName(filter = '*.ns2'))
        if not nsFileName:
            if pd is not None: pd.setValue(pd.maximum()+1)
            return

    if pd is not None:
        pd.setLabelText('Adding LFP data ...')
        pd.setValue(pd.value()+1)
        
    # read the data into a dictionary
    NSx = readNS2(nsFileName)

    if h5file.__contains__('/LFP'):
        h5file.removeNode('/', 'LFP', recursive= True)

    h5file.createGroup('/', name = 'LFP')
    h5file.createGroup('/LFP', name = 'MetaInfo')
    h5file.createArray('/LFP/MetaInfo', 'SampFreq', NSx['MetaTags']['SamplingFreq'])
    h5file.createArray('/LFP/MetaInfo', 'nChannels', NSx['MetaTags']['ChannelCount'])

    for k in range(NSx['MetaTags']['ChannelCount']):
        h5file.createGroup('/LFP', name = 'Chan_%03d' % (k+1))
        h5file.createArray('/LFP/Chan_%03d' % (k+1), 'LFP', NSx['Data'][:,k])

        # add the electrode information to each channel
        for key in NSx['ElectrodesInfo'][k].keys():
            h5file.createArray('/LFP/Chan_%03d' % (k+1), key, NSx['ElectrodesInfo'][k][key])

    # save changes to disk
    h5file.flush()

##########################################################################################
######## CONVERSION UTILITIES ############################################################
##########################################################################################
                                 
class PthSelector(dt.DataSet):
    
    def chDir(self, item, value):
        self.nsxFile = os.path.split(value)[0]+os.path.sep
        
    nevFile = di.FileOpenItem ('NEV file', formats=['nev']).set_prop("display", callback=chDir)
    nsxFile = di.FileOpenItem ('NS2 file', formats=['ns2'])

selectPth = PthSelector()

##########################################################################################

def bin2h5(nevFile = None, nsxFile = None, pth = None):
    '''Helper function to transform binary files to an h5 file.'''

    if selectPth.edit(size = (600, 100)) == 1:
        nevFile = selectPth.nevFile
        nsxFile = selectPth.nsxFile
    else:
        return

    pth = os.path.split(nevFile)[0]
    
    # first extract all the fragments from the NEV file
    pth = ext_fragments(filename = nevFile, outdir = pth)

    # read the list of filenames of fragments
    files = glob(os.path.join(pth, 'channel*'))
    files.sort()
    title = os.path.split(pth)[1]

    # create a new h5 file
    filename = os.path.join(pth, title) + '.h5'
    h5file   = tables.openFile(filename, mode = 'w', title = title)

    # load the pickled headers:
    tmp = pickle.load(open(os.path.join(pth,'headers.p'),'rb'))
    bas_header = tmp[0]
    ext_header = tmp[1]
    
    # create and display a progression bar
    pd = QtGui.QProgressDialog('Processing Files', 'Cancel', 0, len(files)+2)
    pd.setWindowTitle('Processing Files ...')
    pd.setGeometry(500, 500, 500, 100)
    pd.show()

    # create basic structure inside the h5file
    h5file.createGroup('/','Header')
    h5file.createArray('/Header', 'NChans', len(files))
    h5file.createArray('/Header', 'Date', np.array(bas_header['time origin']))

    # add the spike data
    addSpikes2H5(h5file, pth, bas_header, ext_header, pd = pd)    

    # add non neural data
    addNonNeural2H5(h5file, pth, bas_header, pd = pd)
    
    # add the lfp nsx file
    addLFP2h5(h5file, nsFileName = nsxFile, pd = pd)
    
    # close the h5file
    h5file.close()

    # move files and delete binary fragments
    dstPth = os.path.split(pth)[0]
    shutil.move(filename, dstPth)
    shutil.move(os.path.join(pth, 'headers.p'), dstPth)
    shutil.move(os.path.join(pth, 'nonneural.bin'), dstPth)
    shutil.rmtree(pth)
    

