## Imports
import os, re, sys, tables
import numpy as np
from PyQt4 import QtGui, QtCore
from matplotlib.figure import Figure
import numpy as np
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavToolbar
from matplotlib import gridspec, rc
import guidata
import pdb
from m_PlotBehavior import SaveFigure
from socket import gethostname

app = guidata.qapplication()
import guidata.dataset.datatypes as dt
import guidata.dataset.dataitems as di

rc('xtick', labelsize=8)
rc('ytick', labelsize=8)

host = gethostname()
if host == 'mapaz':
    pth = '/media/hachi/Escritorio'
elif host == 'NIALEG-01742384':
    pth = '/media/hachi/Desktop'
else:
    pth = ''

################## MATPLOTLIB WIDGET TO EMBED IN QT ######################

class MplWidget(FigCanvas):
    def __init__(self, parent=None):
        self.fig = Figure()
        self.fig.set_facecolor('w')

        FigCanvas.__init__(self, self.fig)
        if parent: self.setParent(parent)

        self.setSizePolicy(QtGui.QSizePolicy.Expanding,
                           QtGui.QSizePolicy.Expanding)
        self.updateGeometry()

##########################################################################################

class Settings(dt.DataSet):
    WorkingDir   = di.DirectoryItem('Select a Working Dir', default = pth)
    FiguresDir   = di.DirectoryItem('Path to save images', default = pth)
    
settings = Settings()

##

class NeuroExplorer(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.setWindowTitle("NeuroExplorer GUI")
        self.MainWidget = QtGui.QWidget()
        self.MainLayout = QtGui.QHBoxLayout(self.MainWidget)
        self.WorkingDir = pth

        # create a file dialog
        self.fileDialog = QtGui.QFileDialog()

        # create an open file action that gets triggered when called from menu
        openAction = QtGui.QAction('&Open File', self)        
        openAction.setShortcut('Ctrl+O')
        openAction.triggered.connect(self.OpenFile_proc)

        # trigger settings from menu
        settingsAction = QtGui.QAction('&Settings', self)
        settingsAction.setShortcut('Ctrl+S')
        settingsAction.triggered.connect(self.Settings_proc)

        # trigger the closing of the application
        closeAction = QtGui.QAction('&Close H5File', self)        
        closeAction.setShortcut('Ctrl+X')
        closeAction.triggered.connect(self.CloseFile_proc)

        # create the menubar
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(openAction)
        fileMenu.addAction(settingsAction)
        fileMenu.addAction(closeAction)

        showDock0Action = QtGui.QAction('&Show Figure Control', self)
        showDock1Action = QtGui.QAction('&Show Analisys Centered', self)
        showDock2Action = QtGui.QAction('&Show Unit Centered', self)
              
        windowsMenu = menubar.addMenu('&Windows')
        windowsMenu.addAction(showDock0Action)
        windowsMenu.addAction(showDock1Action)
        windowsMenu.addAction(showDock2Action)

        ############ add a dockable figure control widget
        
        dock0 = QtGui.QDockWidget('Figure Control', self)
        dock0.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        dock0.setMinimumWidth(QtGui.QApplication.desktop().availableGeometry().width()/6)
        showDock0Action.triggered.connect(dock0.show)
        w = QtGui.QWidget(dock0)
        w.setMaximumHeight(60)
        vlay = QtGui.QVBoxLayout(w)
        vlay.setSpacing(0)
        vlay.setMargin(0)

        hlay = QtGui.QHBoxLayout()
        self.NewFigBtn = QtGui.QPushButton('New Figure')
        self.NewFigBtn.setFont(QtGui.QFont('',8))
        #self.NewFigBtn.setMaximumHeight(25)
        self.NewFigBtn.clicked.connect(self.NewFigure_proc)
        hlay.addWidget(self.NewFigBtn)

        self.NewFigBtn = QtGui.QPushButton('Save Figure')
        self.NewFigBtn.setFont(QtGui.QFont('',8))
        #self.NewFigBtn.setMaximumHeight(25)
        self.NewFigBtn.clicked.connect(self.SaveFig_proc)
        hlay.addWidget(self.NewFigBtn)
        vlay.addLayout(hlay)

        hlay = QtGui.QHBoxLayout(w)
        self.FigNameText = QtGui.QLineEdit()
        self.FigNameText.setFont(QtGui.QFont('',8))
        self.FigNameText.setMaximumHeight(25)
        self.ChangeTabLabelBtn = QtGui.QPushButton('Set Current Fig Label')
        self.ChangeTabLabelBtn.setFont(QtGui.QFont('',8))
        self.ChangeTabLabelBtn.clicked.connect(self.ChangeCurTabLabel_proc)
        hlay.addWidget(self.FigNameText)
        hlay.addWidget(self.ChangeTabLabelBtn)
        vlay.addLayout(hlay)
        dock0.setWidget(w)

        ############ add a dockable toolbox widget
        dock1 = QtGui.QDockWidget('Analisys Centered', self)
        dock1.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        
        w = QtGui.QWidget(dock1)
        #mainlay = QtGui.QVBoxLayout(w)
        showDock1Action.triggered.connect(dock1.show)

        ### h5 file operations group
        vlay = QtGui.QVBoxLayout(w)
        vlay.setMargin(2)
        vlay.setSpacing(2)

        hlay = QtGui.QHBoxLayout()
        self.AnalisysTypeCombo = QtGui.QComboBox()
        self.AnalisysTypeCombo.addItems(['PSTH','Autocorrelation','Crosscorrelation','Spectrum'])
        self.AnalisysTypeCombo.setFont(QtGui.QFont('',8))
        lbl = QtGui.QLabel('Analisys Type')
        lbl.setFont(QtGui.QFont('',8))
        hlay.addWidget(lbl)
        hlay.addWidget(self.AnalisysTypeCombo)
        vlay.addLayout(hlay)

        # add a spin box to select the number of columns
        hlay = QtGui.QHBoxLayout()
        self.nColumnsAxesSpin = QtGui.QSpinBox()
        self.nColumnsAxesSpin.setRange(0,10)
        self.nColumnsAxesSpin.setValue(6)
        lbl = QtGui.QLabel('Number of Columns')
        lbl.setFont(QtGui.QFont('',8))
        hlay.addWidget(lbl)
        hlay.addWidget(self.nColumnsAxesSpin)
        vlay.addLayout(hlay)

        # time limits
        hlay = QtGui.QHBoxLayout()
        self.tWin1Spin = QtGui.QDoubleSpinBox()
        #self.tWin1Spin.setMaximumHeight(20)
        self.tWin1Spin.setRange(0,5)
        self.tWin1Spin.setValue(1)
        self.tWin1Spin.setSingleStep(0.1)
        self.tWin1Spin.setFont(QtGui.QFont('',8))
        
        self.tWin2Spin = QtGui.QDoubleSpinBox()
        #self.tWin2Spin.setMaximumHeight(20)
        self.tWin2Spin.setRange(0,5)
        self.tWin2Spin.setValue(2)
        self.tWin2Spin.setSingleStep(0.1)
        self.tWin2Spin.setFont(QtGui.QFont('',8))
        self.timePerBinSpin = QtGui.QSpinBox()
        self.timePerBinSpin.setRange(5,500)
        self.timePerBinSpin.setValue(20)
        lbl = QtGui.QLabel('Twin1')
        lbl.setFont(QtGui.QFont('',8))
        hlay.addWidget(lbl)
        hlay.addWidget(self.tWin1Spin)
        hlay.addStretch(1)
        lbl = QtGui.QLabel('Twin2')
        lbl.setFont(QtGui.QFont('',8))
        hlay.addWidget(lbl)
        hlay.addWidget(self.tWin2Spin)
        lbl = QtGui.QLabel('Resolution (milisec/bin)')
        lbl.setFont(QtGui.QFont('',8))
        hlay.addWidget(lbl)
        hlay.addWidget(self.timePerBinSpin)
        vlay.addLayout(hlay)

        #ylim spin
        hlay = QtGui.QHBoxLayout()
        self.ylimSpin = QtGui.QSpinBox()
        self.ylimSpin.setFont(QtGui.QFont('',8))
        self.ylimSpin.setValue(50)
        hlay.addWidget(QtGui.QLabel('PSTH Ylim'))
        hlay.addWidget(self.ylimSpin)
        vlay.addLayout(hlay)
        
        # Plot Btn
        self.PlotRasterBtn = QtGui.QPushButton('Plot Raster')
        self.PlotRasterBtn.setFont(QtGui.QFont('', 8, weight=0))
        self.PlotRasterBtn.clicked.connect(self.PlotRaster_proc)
        vlay.addWidget(self.PlotRasterBtn)

        # units table widget
        self.UnitsTable = QtGui.QTableWidget(0,2, self)
        vlay.addWidget(self.UnitsTable)
        for k in range(self.UnitsTable.columnCount()):
            self.UnitsTable.setColumnWidth(k, 60)
        self.UnitsTable.setHorizontalHeaderLabels(['Unit','Plot?'])
        
        # select all select none buttons
        hlay = QtGui.QHBoxLayout()
        self.SelectAllBtn = QtGui.QPushButton('Select All')
        self.SelectAllBtn.setFont(QtGui.QFont('',8))
        self.SelectAllBtn.setMaximumHeight(20)
        self.SelectAllBtn.clicked.connect(self.SelectAll_proc)
        self.SelectNoneBtn = QtGui.QPushButton('Select None')
        self.SelectNoneBtn.setFont(QtGui.QFont('',8))
        self.SelectNoneBtn.setMaximumHeight(20)
        self.SelectNoneBtn.clicked.connect(self.SelectNone_proc)
        hlay.addWidget(self.SelectAllBtn)
        hlay.addWidget(self.SelectNoneBtn)
        vlay.addLayout(hlay)

        # create en event selecting combobox
        hlay = QtGui.QHBoxLayout()
        self.EventSelectCombo = QtGui.QComboBox()
        self.EventSelectCombo.setFont(QtGui.QFont('',8))
        self.EventSelectCombo.setMaximumHeight(20)
        hlay.addWidget(QtGui.QLabel('Event'))
        hlay.addWidget(self.EventSelectCombo)
        vlay.addLayout(hlay)
        
        # add the toolbox widget to the docking area
        dock1.setWidget(w)

        ############ add a dockable unit centered toolbox widget
        dock2 = QtGui.QDockWidget('Unit Centered Analisys', self)
        dock2.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        showDock2Action.triggered.connect(dock2.show)
        w = QtGui.QWidget(dock2)
        vlay = QtGui.QVBoxLayout(w)
        vlay.setMargin(2)
        vlay.setSpacing(2)

        # add a unit selector combo box
        hlay = QtGui.QHBoxLayout()
        self.ChannelSelectCombo = QtGui.QComboBox(w)
        self.ChannelSelectCombo.setFont(QtGui.QFont('',8))
        self.ChannelSelectCombo.currentIndexChanged.connect(self.UpdateUnitSelectCombo_proc)
        self.UnitSelectCombo = QtGui.QComboBox(w)
        self.UnitSelectCombo.setFont(QtGui.QFont('',8))
        hlay.addWidget(self.ChannelSelectCombo)
        hlay.addWidget(self.UnitSelectCombo)
        vlay.addLayout(hlay)

        # add a spin box to select the number of columns
        hlay = QtGui.QHBoxLayout()
        self.nColumnsUnitAnalisys = QtGui.QSpinBox()
        self.nColumnsUnitAnalisys.setRange(0,10)
        self.nColumnsUnitAnalisys.setValue(3)
        self.nColumnsUnitAnalisys.setFont(QtGui.QFont('',8))
        lbl = QtGui.QLabel('Number of Columns')
        lbl.setFont(QtGui.QFont('',8))
        hlay.addWidget(lbl)
        hlay.addWidget(self.nColumnsUnitAnalisys)
        vlay.addLayout(hlay)

        # add an analisys table
        self.AnalisysTable = QtGui.QTableWidget(0,5,w)
        for k in range(self.AnalisysTable.columnCount()):
            self.AnalisysTable.setColumnWidth(k,80)
        self.AnalisysTable.setColumnWidth(2,50)
        self.AnalisysTable.setColumnWidth(3,50)
        self.AnalisysTable.verticalHeader().setVisible(False)
        self.AnalisysTable.setHorizontalHeaderLabels(['Analisys',
                                                      'Event',
                                                      'TWin1',
                                                      'TWin2',
                                                      'Unit 2'])
        self.AnalisysTable.horizontalHeader().setFont(QtGui.QFont('',8))
        vlay.addWidget(self.AnalisysTable)
        dock2.setWidget(w)


        ### each created analisys creates an axes
        hlay = QtGui.QHBoxLayout()
        # add analisys btn
        self.AddAnalisysBtn = QtGui.QPushButton('Add Analisys', w)
        self.AddAnalisysBtn.setFont(QtGui.QFont('',8))
        self.AddAnalisysBtn.setMaximumHeight(20)
        self.AddAnalisysBtn.clicked.connect(self.AddAnalisys_proc)
        hlay.addWidget(self.AddAnalisysBtn)

        #remove analisys btn
        self.RemoveAnalisysBtn = QtGui.QPushButton('Remove Analisys', w)
        self.RemoveAnalisysBtn.setFont(QtGui.QFont('',8))
        self.RemoveAnalisysBtn.setMaximumHeight(20)
        self.RemoveAnalisysBtn.clicked.connect(self.RemoveAnalisys_proc)
        hlay.addWidget(self.RemoveAnalisysBtn)
        vlay.addLayout(hlay)

        # Plot Btn
        self.PlotAnalisysBtn = QtGui.QPushButton('Plot Analisys')
        self.PlotAnalisysBtn.setFont(QtGui.QFont('', 8, weight=0))
        self.PlotAnalisysBtn.clicked.connect(self.PlotAnalisys_proc)
        vlay.addWidget(self.PlotAnalisysBtn)
        
        ############# add a figure tab widget
        self.MainFigTabWidget = QtGui.QTabWidget()
        self.MainFigTabWidget.setTabsClosable(True)
        self.MainFigTabWidget.setMovable(True)
        self.MainFigTabWidget.tabCloseRequested.connect(self.closeTab_proc)
        widget = QtGui.QWidget()
        
        vlay = QtGui.QVBoxLayout(widget)
        self.Figures = []
        self.Figures.append(MplWidget(widget))
        ntb = NavToolbar(self.Figures[-1], parent = widget)
        ntb.setIconSize(QtCore.QSize(15,15))
        vlay.setSpacing(0)
        vlay.setMargin(0)
        vlay.addWidget(self.Figures[-1])
        vlay.addWidget(ntb)
        widget.setLayout(vlay)

        self.MainFigTabWidget.addTab(widget, 'Figure 1')
        widget.setObjectName(str(self.MainFigTabWidget.count()))
        self.Figures[-1].setObjectName(str(self.MainFigTabWidget.count()))
        #self.MainLayout.addWidget(self.MainFigTabWidget)

        # add the dock to the left docking area
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea,  dock0)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea,  dock1)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea,  dock2)
        # set central widget
        self.setCentralWidget(self.MainFigTabWidget)

        # if running in linux set a certain style for the buttons and widgets
        if sys.platform == 'linux2':
            QtGui.QApplication.setStyle(QtGui.QStyleFactory.create('Plastique'))

        #self.MsgDlg = QtGui.QMessageBox(QtGui.QMessageBox.Information)

    ########################################################################################################
    ########################################################################################################
    ########################################################################################################

    def NewFigure_proc(self):
        widget = QtGui.QWidget(self.MainFigTabWidget)
        vlay = QtGui.QVBoxLayout(widget)
        self.Figures.append(MplWidget(widget))
        ntb = NavToolbar(self.Figures[-1], parent = widget)
        ntb.setIconSize(QtCore.QSize(15,15))
        vlay.setSpacing(0)
        vlay.setMargin(0)
        vlay.addWidget(self.Figures[-1])
        vlay.addWidget(ntb)
        widget.setLayout(vlay)
        self.MainFigTabWidget.addTab(widget, 'Figure '+str(len(self.Figures)))
        widget.setObjectName(str(self.MainFigTabWidget.count()))
        self.Figures[-1].setObjectName(str(self.MainFigTabWidget.count()))

    ########################################################################################################
        
    def SaveFig_proc(self):
        pass
        #SaveFigure
    
    ########################################################################################################
        
    def ChangeCurTabLabel_proc(self):
        indx = self.MainFigTabWidget.currentIndex()
        lbl = self.FigNameText.text()
        if lbl: self.MainFigTabWidget.setTabText(indx, lbl)
        
    ########################################################################################################
        
    def Settings_proc(self):
        if settings.edit()==1:
            self.WorkingDir = settings.WorkingDir
            
    ########################################################################################################
        
    def OpenFile_proc(self):
        fname = str(self.fileDialog.getOpenFileName(caption = 'Select an h5 File',
                                                    directory = self.WorkingDir,
                                                    filter = '*.h5'))

        if not fname: return
        self.h5file = tables.openFile(fname, mode = 'r')
        self.setWindowTitle("NeuroExplorer GUI "+fname)

        l = range(self.UnitsTable.rowCount())
        l.reverse()
        for k in l: self.UnitsTable.removeRow(k)
            
        row = 0
        vheaders = []
        ChanNames = []
        for k in self.h5file.listNodes('/Spikes'):
            ChanNames.append(k._v_name)
            leafs = k.__members__
            leafs.sort()
            for m in leafs:
                if m.find('Unit')!=-1:
                    self.UnitsTable.insertRow(row)
                    self.UnitsTable.setItem(row, 0, QtGui.QTableWidgetItem(m))
                    self.UnitsTable.setCellWidget(row, 1, QtGui.QCheckBox())
                    self.UnitsTable.setRowHeight(row, 20)
                    vheaders.append(k._v_name)
                    self.UnitsTable.item(row, 0).setTextAlignment(QtCore.Qt.AlignCenter)
                    row += 1
        self.UnitsTable.setVerticalHeaderLabels(vheaders)
        self.UnitsTable.setFont(QtGui.QFont('',8))
        self.UnitsTable.setAlternatingRowColors(True)

        self.EventsList = []
        self.EventSelectCombo.clear()
        if self.h5file.__contains__('/Non_Neural_Events'):
            for k in self.h5file.root.Non_Neural_Events.ton:
                self.EventSelectCombo.addItem(k._v_name)
                self.EventsList.append(k._v_name)
            for k in self.h5file.root.Non_Neural_Events.toff:
                self.EventSelectCombo.addItem(k._v_name)
                self.EventsList.append(k._v_name)

        # add the channel names to the ChannSelector
        self.ChannelSelectCombo.addItems(ChanNames)
        
    ########################################################################################################
        
    def CloseFile_proc(self):
        if hasattr(self, 'h5file') and self.h5file.isopen:
            self.h5file.close()
            self.setWindowTitle("NeuroExplorer GUI")

    ########################################################################################################
            
    def UpdateUnitSelectCombo_proc(self):
        self.UnitSelectCombo.clear()
        self.CurChan = str(self.ChannelSelectCombo.currentText())
        leafs = self.h5file.listNodes('/Spikes/'+self.CurChan)
        self.UnitNames = [k._v_name for k in leafs if str(k._v_name).find('Unit')!=-1]
        self.UnitSelectCombo.addItems(self.UnitNames)

    ########################################################################################################
        
    def AddAnalisys_proc(self):
        # first check whether there is an open file
        if not hasattr(self, 'h5file') or not self.h5file.isopen: return
        
        # first insert a row at the end
        self.AnalisysTable.insertRow(self.AnalisysTable.rowCount())

        # get the the index of the recently created row
        curRow = self.AnalisysTable.rowCount()-1

        # set the row height
        self.AnalisysTable.setRowHeight(curRow, 23)

        # create a combo box to put in the first column
        combo = QtGui.QComboBox()
        combo.addItems(['Waveform','PSTH','Autocorrelation','Croscorrelation','Spectrum'])
        combo.setFont(QtGui.QFont('',8))
        self.AnalisysTable.setCellWidget(curRow, 0, combo)

        # create another combo box to put in the second column
        combo = QtGui.QComboBox()
        combo.addItems(self.EventsList)
        combo.setFont(QtGui.QFont('',8))
        self.AnalisysTable.setCellWidget(curRow, 1, combo)

        # add a time window 1 spin box
        tWinSpin = QtGui.QDoubleSpinBox()
        tWinSpin.setRange(0,5)
        tWinSpin.setValue(1)
        tWinSpin.setSingleStep(0.1)
        tWinSpin.setFont(QtGui.QFont('',8))
        self.AnalisysTable.setCellWidget(curRow, 2, tWinSpin)
        
        # add a time window 1 spin box
        tWinSpin = QtGui.QDoubleSpinBox()
        tWinSpin.setRange(0,5)
        tWinSpin.setValue(2)
        tWinSpin.setSingleStep(0.1)
        tWinSpin.setFont(QtGui.QFont('',8))
        self.AnalisysTable.setCellWidget(curRow, 3, tWinSpin)
        

    ########################################################################################################

    def RemoveAnalisys_proc(self):
        if self.AnalisysTable.rowCount()>0:
            self.AnalisysTable.removeRow(self.AnalisysTable.rowCount()-1)
        
    ########################################################################################################
        
    def PlotRaster_proc(self):
        
        if not hasattr(self, 'h5file') or not self.h5file.isopen: return

        # get the list of the selected units to plot from the table
        units  = []
        units2 = []
        for k in range(self.UnitsTable.rowCount()):
            if self.UnitsTable.cellWidget(k,1).checkState() == 2:
                units.append('/%s/%s' % ( str(self.UnitsTable.verticalHeaderItem(k).text()),
                                      str(self.UnitsTable.item(k,0).text()) )
                         )
                units2.append(k)

        nUnits = len(units)
        nCols  = self.nColumnsAxesSpin.value()
        nRows  = int(np.ceil(nUnits/float(nCols)))

        # if there are no figures, create one
        if len(self.Figures) == 0: self.NewFigure_proc()
        
        # searches fot the particular figure
        for k in self.Figures:
            if k.objectName() == self.MainFigTabWidget.currentWidget().objectName():
                fig = k.figure
                break
        fig.clear()

        # create a grid to hold the axes
        gs = gridspec.GridSpec(nRows, nCols)

        # get the time window
        twin = [self.tWin1Spin.value()*1000, self.tWin2Spin.value()*1000]
        eventName = str(self.EventSelectCombo.currentText())
        
        # create axes       
        for j, k in enumerate(units2):
            # get the unit name from the vertical header
            chanName  = str(self.UnitsTable.verticalHeaderItem(k).text())
            unitName  = str(self.UnitsTable.item(k,0).text())
            self.PlotOneRaster_proc(fig, gs[j], chanName, unitName, eventName, twin)

        fig.tight_layout()
        fig.canvas.draw()

    ########################################################################################################

    def PlotOneRaster_proc(self, figHandle, subplotSpec, chanName, unitName, eventName, twin):

        # create axes in the given position of the gridspec
        gs0 = gridspec.GridSpecFromSubplotSpec(2, 1,
                                               subplot_spec = subplotSpec,
                                               hspace = 0.0,
                                               height_ratios = [2,1])

        # create the top axes to hold the raster
        ax0 = figHandle.add_subplot(gs0[0])
        ax0.set_yticklabels('')
        ax0.set_xticklabels('')

        # create axes on the bottom to hold the PSTH
        ax1 = figHandle.add_subplot(gs0[1])
        #ax1.set_yticklabels('')

        # get the event time stamp with the name eventName
        if eventName.find('on')!=-1:
            eventTS = self.h5file.getNode('/Non_Neural_Events/ton', name = eventName).read()
        elif eventName.find('off')!=-1:
            eventTS = self.h5file.getNode('/Non_Neural_Events/toff', name = eventName).read()

        # get the unit time stamps
        node      = self.h5file.getNode('/Spikes/'+chanName)
        TimeStamp = node.TimeStamp.read()
        unitIndx  = node.__getattr__(unitName).Indx.read()
        unitTS    = TimeStamp[unitIndx]

        # create empty lists to hold the data to plot
        trial = []; spikes = []

        # find the events around each time stamp
        for j, k in enumerate(eventTS):
            tmp = unitTS[( unitTS > k - twin[0] ) & ( unitTS < k + twin[1] )] - k
            spikes.extend(tmp)
            trial.extend(j*np.ones_like(tmp))
       
        # plot the data
        ax0.plot(spikes, trial,'|', color='k', alpha = .5)
        ax0.set_xlim(-twin[0], twin[1])
        ax0.set_ylim(0, j)
        ax0.axvline(x = 0, ls = '--', lw = 2, color = [1, 0, 0])
        ch = 'ch'+re.search('(?<=Chan_)[0-9]{3}', chanName).group()
        unit = 'u'+re.search('(?<=Unit)[0-9]{2}',unitName).group()
        if eventName.find('on') != -1:
            evt = 'on'+re.search('(?<=ton_)[0-9]{2}', eventName).group()
        else:
            evt = 'off'+re.search('(?<=toff_)[0-9]{2}', eventName).group()
            
        ax0.set_title('%s %s %s' % (ch, unit, evt), size = 10)
        #axRaster[n].set_ylabel('Trial No', size=8)

        # draw a PSTH
        nbins = int((twin[0]+twin[1])/float(self.timePerBinSpin.value()))
        h = np.histogram(spikes, nbins)
        fr = (h[0]/float(len(eventTS)))/(float(self.timePerBinSpin.value())/1000)
        ax1.bar(h[1][0:-1], fr, width = h[1][1]-h[1][0],
            color = [.5, .5, .5], edgecolor = '')
        ax1.set_ylabel('Spikes/Sec', fontsize = 8)
        ax1.set_ylim(0, self.ylimSpin.value())
        #axPSTH[n].set_xlabel('Time (ms)', size=8)
        #ax1.set_xlim(-twin[0], twin[1])
        #ax1.set_yticklabels('')
        ax1.axvline(x = 0, ls = '--', lw = 2, color = [1, 0, 0])
        self.spikes = spikes
            
    ########################################################################################################
        
    def PlotAnalisys_proc(self):
        # return if no h5file loaded
        if not hasattr(self, 'h5file') or not self.h5file.isopen: return

        # if there are no figures, create one
        if len(self.Figures) == 0: self.NewFigure_proc()
        
        # searches fot the particular figure and make that the current figure
        for k in self.Figures:
            if k.objectName() == self.MainFigTabWidget.currentWidget().objectName():
                fig = k.figure
                break
        fig.clear()

        # get parameters to create axes
        nAnalisys = self.AnalisysTable.rowCount()
        nCols     = self.nColumnsUnitAnalisys.value()
        nRows     = int(np.ceil(nAnalisys/float(nCols)))
        gs        = gridspec.GridSpec(nRows, nCols)

        # get parameters to get variables from the h5 file 
        chanName = str(self.ChannelSelectCombo.currentText())
        unitName = str(self.UnitSelectCombo.currentText())

        # set the tab label 
        self.MainFigTabWidget.setTabText(self.MainFigTabWidget.currentIndex(),
                                         chanName + ' ' + unitName)

        # get the variables of the particular unit
        node      = self.h5file.getNode('/Spikes/' + chanName)
        TimeStamp = node.TimeStamp.read()
        unitIndx  = self.h5file.getNode('/Spikes/' + chanName, unitName).Indx.read()
        unitTS    = TimeStamp[unitIndx]
        
        # create axes
        ax = []
        for k in range(nAnalisys):
            analisysType = self.AnalisysTable.cellWidget(k, 0).currentText()
            eventName    = str(self.AnalisysTable.cellWidget(k,1).currentText())
            twin         = [self.AnalisysTable.cellWidget(k, 2).value()*1000,
                            self.AnalisysTable.cellWidget(k, 3).value()*1000]

            # get the event time stamp with the name eventName
            if eventName.find('on')!=-1:
                eventTS = self.h5file.getNode('/Non_Neural_Events/ton', name = eventName).read()
            elif eventName.find('off')!=-1:
                eventTS = self.h5file.getNode('/Non_Neural_Events/toff', name = eventName).read()
            
            if analisysType == 'Waveform':
                wf = node.Waveforms.read()
                unitWf = wf[unitIndx,:]
                m = np.mean(unitWf, axis=0)
                sd = np.std(unitWf, axis=0)
                x = range(len(m))
                ax = fig.add_subplot(nRows, nCols, k+1)
                ax.plot(x, m, 'k', lw=3, label='waveform average')
                ax.fill_between(x, m+3*sd, m-3*sd, color = 'k', alpha=0.5, label = 'wf +-3 std')
                ax.fill_between(x, unitWf.max(axis=0), unitWf.min(axis=0), color = 'k', alpha=0.3, label = 'max/min')
                ax.legend()
                ax.grid()
                ax.set_title(analisysType, size=10)
                ax.set_xlim(0,len(m)-1)
                
            elif analisysType == 'PSTH':
                
                self.PlotOneRaster_proc(fig, gs[k], chanName, unitName, eventName, twin)
                                
            elif analisysType == 'Autocorrelation':
                spikes = [];
                for n in eventTS:
                    tmp = unitTS[( unitTS > n - twin[0] ) & ( unitTS < n + twin[1] )] - n
                    spikes.extend(tmp)

                dUnitTS = np.diff(spikes)
                c = np.correlate(dUnitTS, dUnitTS, mode='full')
                ax = fig.add_subplot(nRows, nCols, k+1)
                ax.plot(c, 'k')
                                
            elif analisysType == 'Croscorrelation':
                pass

            elif analisysType == 'Spectrum':
                spikes = [];
                for n in eventTS:
                    tmp = unitTS[( unitTS > n - twin[0] ) & ( unitTS < n + twin[1] )] - n
                    spikes.extend(tmp)

                dUnitTS = np.diff(spikes)
                c = np.correlate(dUnitTS, dUnitTS, mode='full')
                s = np.abs(np.fft.fft(c))
                ax = fig.add_subplot(nRows, nCols, k+1)
                ax.plot(s[0:len(s)/2], 'k')

        fig.tight_layout()
        fig.canvas.draw()
            
    ########################################################################################################
        
    def closeEvent(self,  *event):
        ''' reimplementation of the closeEvent that closes the h5file before killing the window'''
        if hasattr(self, 'h5file') and self.h5file.isopen:
            self.h5file.close()
        self.deleteLater()

    ########################################################################################################

    def closeTab_proc(self, n):
        reply = QtGui.QMessageBox.question(self,
                                           'Message',
                                           'Are you sure you want to close it?',
                                           QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
                                           QtGui.QMessageBox.No)
        if reply == QtGui.QMessageBox.Yes:
            self.Figures[n].close()
            self.Figures.pop(n)
            self.MainFigTabWidget.removeTab(n)        

    ########################################################################################################
        
    def SelectAll_proc(self):
        if not hasattr(self, 'h5file') or not self.h5file.isopen: return
        for k in range(self.UnitsTable.rowCount()):
            w = self.UnitsTable.cellWidget(k, 1)
            w.setChecked(True)

    ########################################################################################################
    
    def SelectNone_proc(self):
        if not hasattr(self, 'h5file') or not self.h5file.isopen: return
        for k in range(self.UnitsTable.rowCount()):
            w = self.UnitsTable.cellWidget(k, 1)
            w.setChecked(False)

    ########################################################################################################
    ########################################################################################################
        
if __name__ == '__main__':
    if not QtGui.QApplication.instance():
        app = QtGui.QApplication(sys.argv)
        sys.exit(app.exec_())
    nex = NeuroExplorer()
    nex.show()
