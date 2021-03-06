from ROOT import *
import ROOT
from array import array
from lib.util.Logger import Logger
from lib.util.MiscTools import AreSame,belongsTo,return_filenames
import os


class FitResultReader(object):
    """Reads the tree with fit information and gives back the
       information relevant for plotng the limits or measurements.
    """
    def __init__(self, POIs=None, file_names=None, combine_method=None):
        self.log = Logger().getLogger(self.__class__.__name__, 10)

        self.combine_method = combine_method
        self.combine_result = None
        self.global_best_fit = {}  #best fit from all the files.
        self.global_best_fit_dict= {}  #contains one best fit per input file
        self.ll_values_dict = {}
        self.ul_values_dict = {}
        self.contours = {}
        self.contour_graph= {}
        self._has_parsed_combine_result_already = False
        self.set_POI(POIs)
        self.set_files(file_names)

    def set_POI(self, POIs):
        """Provide a list of POIs in terms of python list
           of strings or string with POIs separated by ";:*, "
        """
        self.POI = []
        assert isinstance(POIs, list) or isinstance(POIs, str), "POIs should be provided either as list of strings or as string with \";: \" as delimiters. "
        if isinstance(POIs, list):
            self.POI = POIs
        elif isinstance(POIs, str):
            import re
            POIs = re.sub('[;:, ]+',':',POIs) #pois can be split by ";:*, " - we don't care
            self.POI = POIs.split(":")

        for poi in self.POI:
            self.global_best_fit.update({poi : None})
            self.log.debug('Initializing the best fit dictionary {0}'.format(self.global_best_fit))

        self.log.debug('Setting POI list to {0}'.format(self.POI))

    def set_files(self, file_names, start_dir = "."):
        """Set the list of output files from combine that will be used.
           One can use the start dir and filename pattern to run on all
           files that are found recursively on the path.
        """
        self.file_list = []
        assert isinstance(file_names, list) or isinstance(file_names, str), "File names should be provided either as list of strings or as string with \";,: \" as delimiters. "
        assert isinstance(start_dir, str), "The start directory should be provided as string."
        if isinstance(file_names, list):
            self.file_list = file_names
        elif isinstance(file_names, str):
            raise ValueError, 'Please provide a list of strings for the file names. The option with strings only doesn\'t work for the moment. :('
            self.file_list = return_filenames(start_dir, self.file_list)

        print 'File list = ', self.file_list
        self.log.debug('Loaded {0} files.'.format(len(self.file_list)))
        self._has_parsed_combine_result_already = False  #has to be set to False so that the limits and best fits are recalculated when new file is set.

    def _get_crossings_for_limits(self, list_of_segments, cl=0.68):
        """Internal function for getting the Y values from given
           TGraph objets. It is used to get POI limits for particular
           confidence level.
        """
        assert belongsTo(float(cl),0,1), "Confidence level has to be given in interval [0,1]"
        quantileExpected = 1 - cl
        values=[]
        for seg in list_of_segments:
            #ll_seg is a TGraph
            xmin = TMath.MinElement(seg.GetN(),seg.GetX())
            xmax = TMath.MaxElement(seg.GetN(),seg.GetX())
            if belongsTo(quantileExpected, xmin, xmax):
                values.append(seg.Eval(quantileExpected))
        return values

    def get_graph(self, contour_axis="x:y:z", dims = 1, y_offset=0.0, z_offset=0.0):
        """Returns the full likelihood scan graph.
           Specify contour_axis= "2*deltaNLL" or "1-quantileExpected"
           The last axis provided should be
        """
        import re
        contour_axis = re.sub('[;:]+',':',contour_axis) #can be split by ";: " - we don't care
        try:
            self.contour_graph[contour_axis]
        except KeyError:
            contour_axis_list = contour_axis.split(":")
            dims = len(contour_axis_list)
            assert 1<dims<=3, "We can accept 2 to 3 axis for the graph. You provided {0}.Please behave :)".format(dims)
            assert ('deltaNLL' in contour_axis_list[-1] or 'quantileExpected' in contour_axis_list[-1]), 'Your last axis has to contain either deltaNLL or quantileExpected.'
            import copy
            #required_branches = copy.deepcopy(contour_axis_list)
            required_branches = []
            #Solve to accept even a formula as the axis.
            if 'deltaNLL' in contour_axis_list[-1]:
                #self.log.debug('deltaNLL in contour_axis_list: {0}'.format(contour_axis_list[-1]) )
                contour_axis_list[-1] = str(contour_axis_list[-1]).replace('deltaNLL','t.deltaNLL')
                #required_branches[-1] = 'deltaNLL'
                required_branches.append('deltaNLL')
                #self.log.debug('deltaNLL is an estimator: {0}'.format(contour_axis_list[-1]) )

            elif 'quantileExpected' in contour_axis_list[-1]:
                contour_axis_list[-1] = contour_axis_list[-1].replace('quantileExpected', 't.quantileExpected')
                #required_branches[-1] = 'quantileExpected'
                required_branches.append('quantileExpected')
                #self.log.debug('quantileExpected is an estimator: {0}'.format(contour_axis_list[-1]) )

            self.log.debug('Changing names of pois for evaluation of formula later: N_poi = {0} N_axis= {1}'.format(len(self.POI),len(contour_axis_list[:-1])))
            for poi_id in range(len(self.POI)):
                for axis_id in range(len(contour_axis_list[:-1])):
                    self.log.debug('Changing names of pois for evaluation of formula later: poi_id = {0} axis_id = {1}'.format(poi_id, axis_id))
                    if self.POI[poi_id]=='r':
                        contour_axis_list[axis_id] = 't.r'
                    else:
                        contour_axis_list[axis_id] = contour_axis_list[axis_id].replace(self.POI[poi_id],'t.{0}'.format(self.POI[poi_id]))
                    #required_branches[axis_id] = self.POI[poi_id]
                    required_branches.append(self.POI[poi_id])

            self.log.debug('Contour axis list changed for evaluation of formula to {0}'.format(contour_axis_list))


            if dims==2:
                self.contour_graph[contour_axis] = TGraph()
            elif dims==3:
                self.contour_graph[contour_axis] = TGraph2D()

            self.contour_graph[contour_axis].SetNameTitle(contour_axis,contour_axis.replace(':',';') )


            self.log.debug('Graph {0} is being created from the tree in {1}'.format(contour_axis, self.file_list[0]))

            rootfile = TFile.Open(self.file_list[0],'READ')
            if not rootfile:
                raise IOError, 'The file {0} either doesn\'t exist or cannot be open'.format(self.file_list[0])
            t = rootfile.Get('limit')

            required_branches = list(set(required_branches))
            self.log.debug('Required branches are : {0}'.format(required_branches))
            for axis in range(dims):
                assert t.GetListOfBranches().FindObject(required_branches[axis]), "The branch \"{0}\" doesn't exist.".format(required_branches[axis])

            t.SetBranchStatus("*", False)
            #for axis in range(dims):
                #t.SetBranchStatus(required_branches[axis], True)
            for branch in required_branches:
                t.SetBranchStatus(branch, True)

            #x_y_z_list = []
            x_y_z_set = set()
            x_y_set = set()
            #x_y_dict= dict()

            for en in range(1,t.GetEntriesFast()):
                t.GetEntry(en)
                if AreSame(t.quantileExpected,1):
                    #skip all the global fit entries (case when hadding scan outputs)
                    self.log.debug("This entry ({0}) is coming from global fit. Skipping.".format(en))
                    continue

                if dims==2:
                    X = eval(contour_axis_list[0])
                    Y = eval(contour_axis_list[1])
                    x_y_set.add((X,Y))
                    if en%100 == 0:
                        #self.log.debug('Inputs X={0} Y={1}'.format(eval('t.{0}'.format(required_branches[0])),eval('t.{0}'.format(required_branches[1]))))
                        self.log.debug('Entry={2} X={0} Y={1}'.format(X,Y, en))
                    #self.contour_graph[contour_axis].SetPoint(en-1,X,Y)

                elif dims==3:
                    X = eval(contour_axis_list[0])
                    Y = eval(contour_axis_list[1])
                    Z = eval(contour_axis_list[2])
                    #x_y_z_list.append((X,Y,Z))
                    if en%100 == 0:#FIXME WARNING This is just to read less points
                        x_y_z_set.add((X,Y,Z))
                    if en%1000 == 0:
                        #t.Show()
                        self.log.debug('Entry={3} X={0} Y={1} Z={2}'.format(X,Y,Z, en))
                    #self.contour_graph[contour_axis].SetPoint(en-1,X,Y,Z)
            self.log.debug('Setting points of graph from sorted lists.')
            if dims==2:
                i_elem=0
                for point in sorted(list(x_y_set)):
                    self.contour_graph[contour_axis].SetPoint(i_elem,point[0],point[1]+y_offset)
                    i_elem+=1
            elif dims==3:
                i_elem=0
                for point in sorted(list(x_y_z_set)):
                    self.contour_graph[contour_axis].SetPoint(i_elem,point[0],point[1]+y_offset,point[2]+z_offset)
                    i_elem+=1
            del x_y_set
            del x_y_z_set

            #if dims==3:
                ##TGraph2D is too slow (Delunay triangulation) - we want to give back a TH2D
                #th2d = self.contour_graph[contour_axis].GetHistogram("empty")
                #self.log.debug("Copyng TGraph2D to TH2D EMPTY histo with nx = {0}, ny = {1}".format(th2d.GetXaxis().GetNbins(),th2d.GetYaxis().GetNbins() ))
                #for point in x_y_z_list:
                    #th2d.SetBinContent(th2d.GetXaxis().FindBin(point[0]),th2d.GetYaxis().FindBin(point[1]),point[2])
                    ##self.log.debug('TH2D filled with value={0}. Current entries = {1}'.format(point, th2d.GetEntries()))
                #import copy
                #self.contour_graph[contour_axis] = copy.deepcopy(th2d)
                #self.log.debug('TH2D given to contour {0} of type {1}'.format(self.contour_graph[contour_axis], type(self.contour_graph[contour_axis])))
            self.log.debug('Returning filled graph.')
        return self.contour_graph[contour_axis]


    def ll_values(self, POI, cl = 0.68):
        """returns a list of lower limits for a given level for a given POI
        """
        if not self._has_parsed_combine_result_already:
            self._parse_combine_result()
        assert belongsTo(float(cl),0,1), "Confidence level has to be given in interval [0,1]"
        cl_name = "{1}_CL@{0:.2f}".format(cl, POI)
        try:
            self.ll_values_dict[cl_name]
        except KeyError:
            self.ll_values_dict[cl_name] = self._get_crossings_for_limits(self.raising_segments[POI], float(cl))
            self.log.debug('Creating limit for C.L.@{0}'.format(cl))
        else:
            self.log.debug('Returning existing limit for C.L.@{0}'.format(cl))
        return self.ll_values_dict[cl_name]

    def ul_values(self, POI, cl = 0.68):
        """returns a list of lower limits for a given level for a given POI
        """
        if not self._has_parsed_combine_result_already:
            self._parse_combine_result()
        assert belongsTo(float(cl),0,1), "Confidence level has to be given in interval [0,1]"
        cl_name = "{1}_CL@{0:.2f}".format(cl, POI)
        try:
            self.ul_values_dict[cl_name]
        except KeyError:
            self.ul_values_dict[cl_name] = self._get_crossings_for_limits(self.falling_segments[POI], float(cl))
            self.log.debug('Creating limit for C.L.@{0}'.format(cl))
        else:
            self.log.debug('Returning existing limit for C.L.@{0}'.format(cl))

        return self.ul_values_dict[cl_name]

    def best_fit(self, POI):
        """Get the best fit value fora particular POI
        """
        if not self._has_parsed_combine_result_already:
            self._parse_combine_result()
        try:
            self.global_best_fit[POI]
        except KeyError:
            raise KeyError, 'The POI name \"{0}\" is invalid.'.format(POI)
        else:
            return float(self.global_best_fit[POI])


    def is_set_ll(self,POI, cl=0.68):
        assert belongsTo(float(cl),0,1), "Confidence level has to be given in interval [0,1]"
        cl_name = "{1}_CL@{0:.2f}".format(cl, POI)
        try:
            self.ll_values_dict[cl_name]
        except KeyError:
            raise KeyError, 'The POI name \"{0}\" is invalid.'.format(POI)
        else:
            return (len(self.ll_values_dict[cl_name])>0)

    def is_set_ul(self,POI, cl=0.68):
        assert belongsTo(float(cl),0,1), "Confidence level has to be given in interval [0,1]"
        cl_name = "{1}_CL@{0:.2f}".format(cl, POI)
        try:
            self.ul_values_dict[cl_name]
        except KeyError:
            raise KeyError, 'The POI name \"{0}\" is invalid.'.format(POI)
        else:
            return (len(self.ul_values_dict[cl_name])>0)

    def is_set_best_fit(self,POI):
        try:
            self.global_best_fit[POI]
        except KeyError:
            raise KeyError, 'The POI name \"{0}\" is invalid.'.format(POI)
        else:
            return (self.global_best_fit[POI]!=None)

    def get_results_dict(self, POI, option='standard', rescale_expression='', invert_LL_UL=False):
        """Returns a dict with best fit values and limits at 68(95)%
        """
        self.log.info('Compiling the fit results dictionary...')
        if option.lower()=='standard':
            #import collections
            #self.limits_dict = collections.OrderedDict()
            self.limits_dict={}
            self.limits_dict['BF']  = self.best_fit(POI)
            self.limits_dict['LL68']= self.ll_values(POI, 0.68)
            self.limits_dict['LL95']= self.ll_values(POI, 0.95)
            self.limits_dict['UL68']= self.ul_values(POI, 0.68)
            self.limits_dict['UL95']= self.ul_values(POI, 0.95)

            self.log.debug('Limits are: {0}'.format(self.limits_dict))

            import copy
            return_dict = copy.deepcopy(self.limits_dict)  #because dict is mutable... we don't want the initial dict to be changed

            if POI in rescale_expression:  #the rescale must contain the formula with the POI string inside
                for key in return_dict.keys():
                    if isinstance(return_dict[key],float):
                        the_value = return_dict[key]
                        return_dict[key] = eval(rescale_expression.replace(POI,str(return_dict[key])))
                        self.log.debug('Rescaling {3} value with {0}: {1} ---> {2}'.format(rescale_expression, the_value,return_dict[key], key ))
                    elif isinstance(return_dict[key],list):
                        for val_i in range(len(return_dict[key])):
                            the_value = return_dict[key][val_i]
                            return_dict[key][val_i] = eval(rescale_expression.replace(POI,str(return_dict[key][val_i])))
                            self.log.debug('Rescaling {3} value with {0}: {1} ---> {2}'.format(rescale_expression, the_value,return_dict[key][val_i], key ))

                if invert_LL_UL:
                    return_dict['UL68'],return_dict['LL68'] = return_dict['LL68'],return_dict['UL68']
                    return_dict['UL95'],return_dict['LL95'] = return_dict['LL95'],return_dict['UL95']
            return return_dict
        else:
            raise RuntimeError,'The option {0} is still not implemented. Do you want to volonteer? :)'.format(option)



    def get_contours(self, contour_axis, limits = None):
        """Return dict of lists of TGraph contours with a given confidence level.
           The keys are levels...
           The code taken from http://root.cern.ch/root/html534/tutorials/hist/ContourList.C.html
        """
        self.log.debug('Extracting contours for {0} at levels {1}'.format(contour_axis, limits))

        if limits==None:
            limits=['0.68','0.95']  #default limit values

        import re
        import copy
        contour_axis = re.sub('[;:]+',':',contour_axis) #can be split by ";: " - we don't care
        n_missing=0
        for limit in limits:
            try:
                #if the contours exist, we will return them imediatelly
                self.contours[contour_axis][str(limit)]
            #except KeyError:
            except:
                n_missing+=1
                self.get_graph(contour_axis)

        if n_missing==0:
            self.log.debug('Contour exist. Returning.')
            return self.contours[contour_axis]
        else:
            #initialize contours
            self.contours[contour_axis]={}
        #for level in limits:
            #self.contours[str(level)]=[]
        self.log.debug('Contours before extracting {0}'.format(self.contours))

        graph_contours = self.contour_graph[contour_axis].Clone("graph_contours")
        self.log.debug('Contour is of type {0}'.format(type(graph_contours)))
        #import array
        contours = array('d',[float(lim) for lim in limits])

        #if isinstance(graph_contours,plotLimit.TH2D):
        if 'TH2D' in str(type(graph_contours)):
            graph_contours.SetContour(len(contours), contours)
            c = TCanvas("c","Contour List",0,0,600,600)
            c.cd()
            graph_contours.Draw("CONT Z LIST")
            c.Update() #// Needed to force the plotting and retrieve the contours in TGraphs
            conts = gROOT.GetListOfSpecials().FindObject("contours")
            #// Get Contours
            #conts = gROOT.GetListOfSpecials().FindObject("contours")
            contLevel = None
            curv      = None
            TotalConts= 0

            if (conts == None):
                print "*** No Contours Were Extracted!\n"
                TotalConts = 0
                return
            else:
                TotalConts = conts.GetSize()

            print "TotalConts = %d\n" %(TotalConts)
            #tgraph_list = {}

            #self.contours[contour_axis]
            for i in reversed(range(0,TotalConts)):
                #last contour is the first in the contour array
                contLevel = conts.At(i)
                self.contours[contour_axis][str(limits[i])] = []
                print "Contour %d has %d Graphs\n" %(i, contLevel.GetSize())
                for j in range(0,contLevel.GetSize()):
                    #tgraph_list.append(copy.deepcopy(contLevel.At(j)))
                    self.contours[contour_axis][str(limits[i])].append(copy.deepcopy(contLevel.At(j)))

        #elif isinstance(graph_contours,plotLimit.TGraph2D):
        #elif 'TGraph2D' in str(type(graph_contours)):
            ## Create a struct
            ##import string
            ##limits_string = string.join(limits,',')
            ##gROOT.ProcessLine("Float_t MyContourLevels[] = {{{0}}}".format(string.join(limits,',')))
            ##from ROOT import MyContourLevels
            ##Create branches in the

            #c = TCanvas("c_tgraph2D","Contour List",0,0,600,600)
            #graph_contours.Draw("COLZ")
            ###c.Update()
            #for limit in limits:
                    #self.log.debug('Doing the contours for {0}'.format(limit))
                    #conts = graph_contours.GetContourList(float(limit))
                    #for j in range(0,conts.GetSize()):
                        #self.log.debug('Adding contour: level={0} i={1} '.format(limit,j))
                        #self.contours[contour_axis][str(limit)].append(copy.deepcopy(conts.At(j)))

        c = TCanvas("c_tgraph2D","Contour List",0,0,600,600)
        graph_contours.Draw("COLZ")
        c.Update()
        for limit in limits:

                conts = graph_contours.GetContourList(float(limit))
                self.log.debug('Doing the contours for {0}: #contours = {1}'.format(limit, conts.GetSize()))
                self.contours[contour_axis][str(limit)] = []
                for j in range(0,conts.GetSize()):
                    self.log.debug('Adding contour: level={0} i={1} '.format(limit,j))
                    self.contours[contour_axis][str(limit)].append(copy.deepcopy(conts.At(j)))


        self.log.debug('Contour for {0} is of type={1}.'.format(contour_axis,type(self.contours[contour_axis])))
        print self.contours[contour_axis]
        #we return dict with keys=limits and values=lists of TGraph objects
        return self.contours[contour_axis]

    def set_combine_method(self,combine_method):
        """Set method in order to know how the limit trees look like.
        """
        self.combine_method = combine_method

    def _get_TGraph_from_segment(self, segment):
        """Create TGraph from list of tuples(qe, poi, dNLL)
        """
        qe_vals  = array('d', [t[0] for t in segment])
        poi_vals = array('d', [t[1] for t in segment])
        return TGraph(len(segment), qe_vals, poi_vals)

    def _parse_combine_result(self, combine_method="MultiDimFit"):
        """Parsing the combine result and filling the contour information.
           Should be run on first demand of any information.
        """
        self._has_parsed_combine_result_already = True
        self.log.debug("Parsing the combine output files for method = {0}".format(combine_method))
        assert len(self.file_list)>0, "There is no files to read."
        #assert len(self.file_list)==1, "Currently, we allow only one file from combine output. The implementation is still lacking this feature..."

        #containers for TGraph raising and falling segments
        self.falling_segments =  {poi:[] for poi in self.POI}
        self.raising_segments = {poi:[] for poi in self.POI}

        for poi in self.POI:
            for root_file_name in self.file_list:
                root_file_name =  self.file_list[0]
                #get the TTree and enable relevant branches (POI, quantileExpected, deltaNLL)
                self.log.debug("Parsing the combine output file = {0}".format(root_file_name))
                rootfile = ROOT.TFile.Open(root_file_name,'READ')
                if not rootfile:
                    raise IOError, 'The file {0} either doesn\'t exist or cannot be open'.format(root_file_name)
                t = rootfile.Get('limit')
                assert t.GetListOfBranches().FindObject(poi), "The branch \"{0}\" doesn't exist.".format(poi)

                #don't read uninteresting branches
                t.SetBranchStatus("*", False)
                t.SetBranchStatus("quantileExpected", True)
                t.SetBranchStatus(poi, True)
                t.SetBranchStatus("deltaNLL", True)


                #get the best fit
                if self.global_best_fit[poi] == None:
                    t.GetEntry(0)
                    if AreSame(t.quantileExpected,1) and AreSame(t.deltaNLL, 0):  #This is true if combine has found a good minimum.
                        self.global_best_fit[poi] = eval('t.{0}'.format(poi))
                        self.global_best_fit_dict.update({poi : {'best_fit' : eval('t.{0}'.format(poi)), 'quantileExpected' : t.quantileExpected, '2*deltaNLL' : 2*t.deltaNLL}} )
                        self.log.debug("Global best fit in file {0} = {1}".format(root_file_name, self.global_best_fit_dict))


                is_raising = False
                #we want to find the first trend of the function
                ien = 1
                tmp_list_qe_poi_dNLL = []
                while True:
                    t.GetEntry(ien)
                    if ien==1:
                        qe_prev = t.quantileExpected
                    if t.quantileExpected > qe_prev:
                        is_raising=True
                        break
                    elif t.quantileExpected < qe_prev:
                        is_raising=False
                        break
                    qe_prev = t.quantileExpected
                    ien+=1
                self.log.debug('Detected trend of first interval: Raising = {0}, Falling = {1}'.format(is_raising, (not is_raising)))

                self.log.debug('Searching for intervals at 68(95)% C.L.')
                tmp_list_qe_poi_dNLL = []
                is_trend_changed = False
                n_entries = t.GetEntriesFast()
                for en in range(1,n_entries+1):  #add +1 to range so that to save all the entries into the segments
                    if en < n_entries:  #if not passed the last entry
                        t.GetEntry(en)
                        # set x=quantileExpected and y=POI and create segments
                        qe, poi_value, dNLL  = t.quantileExpected, eval('t.{0}'.format(poi)), t.deltaNLL
                        #adding check of change of poi_value in case we have multidim fit.
                        #if the value is same as previous, we just skip.
                        if en==1:
                            poi_value_prev = poi_value
                        if AreSame(poi_value,poi_value_prev):
                            poi_value_prev = poi_value
                            continue


                        #check if trend is change, and then change the bool is_raising which will show which vector should be filled
                        if (en > 2):
                            if ((qe < qe_prev) and is_raising) or ((qe > qe_prev) and not is_raising):
                                is_trend_changed = True
                                self.log.debug('Trend of the segment has changed at entry {0}.'.format(en))
                                self.log.debug('**********************************************')

                    #fill tmp_list_qe_poi_dNLL until we see that the trend is changed
                    #then put that list into self.raising_segments or self.falling_segments and clear the tmp_list_qe_poi_dNLL
                    if is_trend_changed or en==n_entries:
                        if is_raising:

                            self.raising_segments[poi].append(self._get_TGraph_from_segment(tmp_list_qe_poi_dNLL))
                            #self.log.debug('Appending segment to self.raising_segments[{1}]: {0}'.format(tmp_list_qe_poi_dNLL, poi))
                        else:
                            self.falling_segments[poi].append(self._get_TGraph_from_segment(tmp_list_qe_poi_dNLL))
                            #self.log.debug('Appending segment to self.falling_segments[{1}]: {0}'.format(tmp_list_qe_poi_dNLL, poi))

                        self.log.debug('Raising_segments state: {0}'.format(self.raising_segments))
                        self.log.debug('Falling_segments state: {0}'.format(self.falling_segments))
                        #delete all elements from the tmp list
                        del tmp_list_qe_poi_dNLL[:]
                        #change the state of raising/falling interval
                        is_raising = (not is_raising)
                        is_trend_changed = False

                    if en < n_entries:
                        #fill tmp_list_qe_poi_dNLL
                        tmp_list_qe_poi_dNLL.append((qe, poi_value, dNLL))
                        #self.log.debug('Entry = {2} Raising = {0}, Falling = {1}'.format(is_raising, (not is_raising), en))
                        #self.log.debug('Entry = {4} Filling tmp_list_qe_poi_dNLL (size={0}) with : qe = {1}, poi_value = {2}, dNLL = {3}'.format(len(tmp_list_qe_poi_dNLL),qe, poi_value, dNLL, en ))
                        qe_prev = qe
                        #is_trend_changed = False



