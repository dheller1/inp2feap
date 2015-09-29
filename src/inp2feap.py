# -*- coding: utf-8 -*-

"""

   inp2feap
   
   
   This program is used to convert finite element models from the Abaqus .inp format to a FEAP input file.
   Its behavior is controlled completely by a configuration file following the JSON-syntax which must be
   specified when running inp2feap. The configuration file states which .inp file will be read and how
   exactly it will be processed.
   See the main documentation for inp2feap on Github for information on how to use as well as possibilities
   and limitations of the program. Advanced knowledge of finite element methods will probably be required
   to make any sense of the information.
   
   https://www.github.com/dheller1/inp2feap
   
   The program is provided as is without any warranties. Feel free to use and/or modify as needed.
   
   Dominik Heller, September 2015
   dominik.heller1@gmail.com
   
"""

import os, sys, json

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

class Node:
   """ A node in a finite element model is an entity comprising an id for identification and
   spatial coordinates (x,y) for 2d or (x,y,z) for 3d models, respectively. 
   Nodes are connected to other nodes via elements to form the finite element mesh. """
   def __init__(self, *args):
      global xMin, xMax, yMin, yMax, zMin, zMax
      
      if len(args) == 3: # id, x, y
         self.nDim = 2
         self.id = int(args[0])
         self.x = float(args[1])
         self.y = float(args[2])
         
      elif len(args) == 4: # id, x, y, z
         self.nDim = 3
         self.id = int(args[0])
         self.x = float(args[1])
         self.y = float(args[2])
         self.z = float(args[3])
         
      else:
         raise ValueError("Invalid number of arguments (%d)!" % len(args))
      
   def __str__(self):
      if self.nDim == 2: 
         s = '%8d, 0, %14.8f, %14.8f\n' % (self.id, self.x, self.y)
      elif self.nDim == 3:
         s = '%8d, 0, %14.8f, %14.8f, %14.8f\n' % (self.id, self.x, self.y, self.z)
      return s
      
class Element:
   """ Nodes in a finite element model are connected via elements to form the mesh.
   The number of nodes per element (often called 'nel') can vary depending on the
   type of element (e.g. beam element with 2 nodes, quadrilateral shell element with
   4 nodes), the order of ansatz functions (quadratic beam: 3 nodes), and more.
   
   Currently, all elements in a model read by inp2feap must have the same number of nodes.
   The order of nodes in the node list is not arbitrary, it can determine the element
   orientation and might lead to errors if it is set not correctly.
   
   Important member variables:
      - id        (int)            Unique id to distinguish each element
      - nodes     (list of ints)   List of node IDs belonging to the element
      - matn      (int)            Can be used to assign each element a distinct material number in FEAP
   """
   def __init__(self, *args):
      if len(args) < 2:
         raise ValueError("Too few arguments (%d) for element!" % len(args))
      
      self.numNodes = len(args)-1
      
      self.id = int(args[0])
      self.nodes = []
      for a in args[1:]:
         if type(a) == int or len(a)>0: self.nodes.append(int(a))
         
      self.matn = 1
      self.duplicate = []
         
   def __str__(self):
      s = "%8d, %d" % (self.id, self.matn)
      for n in self.nodes: s += ", %d" % n
      s += "\n"
      return s
   
class NodeSet:
   """ A node set is a collection of nodes with a name.
   It is possible to define specific boundary condition or load statements for all nodes within a node set.
   As an example, in a shell model with intersections, a formulation is often used where nodes at
   which intersections are present comprise 6 degrees of freedom, while other nodes comprise 5 DOFs.
   By assigning all intersection nodes to a node set, the 6th DOF can be made available only on nodes in the
   set while being locked on all other nodes. 
   """
   def __init__(self, *args):
      self.nodes = []
      self.name = "Unnamed nset"
      self.setBoun = ""
      self.setLoad = ""
      
   def __str__(self):
      self.nodes = sorted(self.nodes)
      
      if len(self.setBoun) > 0:
         s = "boun ** NSET=%s\n" % self.name 
         for node in self.nodes:
            s += "%d, 0, %s\n" % (node, self.setBoun)
      
      if len(self.setLoad) > 0:
         s = "load ** NSET=%s\n" % self.name 
         for node in self.nodes:
            s += "%d, 0, %s\n" % (node, self.setLoad)
      
      return s

class ElSet:
   """ An ElSet (element set) is a collection of elements with a name.
   It is mainly used to be able to assign a specific material number in FEAP to elements in a set
   (setMat parameter).
   """
   def __init__(self, *args):
      self.elems = []
      self.name = "Unnamed elset"
      self.setMat = 1
      self.generate = False
      self.duplicate = []
      
class AbaqusMesh:
   """ An AbaqusMesh object gathers all mesh information from an Abaqus model which is currently
   read from inp2feap, that is: Nodes, elements, node sets, element sets.   
   """
   def __init__(self):
      self.nodes = []
      self.elems = []
      self.nsets = []
      self.elsets = []
      
class InpFileParser:
   """ This class serves to be able to read an Abaqus .inp-file as an input file and extract
   all relevant information regarding nodes, elements, node sets, and element sets.
   
   It must be initialized with a filename. The number of nodes per element, 'nodesPerElem',
   can be set or determined automatically. Currently, all elements must comprise the same number
   of nodes.
   The method Parse() then reads and interprets the .inp file, returning an AbaqusMesh object
   on success.
   
   Some basic error handling and warning functionality is present and the parser has been tested
   with several different input files. Nonetheless, careful inspection of the read data should
   be carried out in case of any problems.
   """
   READ_NODES = 1
   READ_ELEMS = 2
   READ_NSET = 3
   READ_ELSET = 4
   UNKNOWN = 0
   
   def __init__(self, filename=None, nodesPerElem=None):
      """ Initialize the parser with a filename and (optionally) number of nodes per element. """
      self.filename = filename
      self.nodesPerElem = nodesPerElem
      
   def Parse(self):
      readMode = InpFileParser.READ_NODES
      
      numNodesKnown = (self.nodesPerElem!=None)
      numNodes = self.nodesPerElem if self.nodesPerElem != None else -1
      nDim = 3
      
      nodes = []
      elems = []
      nsets = []
      elsets = []
      
      elemInput = []
      
      ignoredLines = []
      
      print "Parsing input file '%s'." % self.filename
      
      with open(self.filename, 'r') as f:
         for lineNumber, line in enumerate(f.readlines()):
            #print lineNumber, line
            if line.startswith("*"):
               if line.strip().split(',')[0] == "*Node":
                  readMode = InpFileParser.READ_NODES
                  continue
               elif line.strip().split(',')[0] == "*Element":
                  readMode = InpFileParser.READ_ELEMS
                  elemInput = [] # list of all integer values read while in READ_ELEMS mode
                  continue
               elif line.strip().split(',')[0] == "*Nset":
                  readMode = InpFileParser.READ_NSET
                  curNset = NodeSet()
                  nsetName = "UNKNOWN_NSET"
                  assignmentPairs = line.split(",")
                  for p in assignmentPairs:
                     if p.count('=') == 0: continue
                     var, val = p.split('=')
                     var = var.strip(); val = val.strip();
                     if var == 'nset':
                        nsetName = val
                        
                  curNset.name = nsetName
                  nsets.append(curNset)
               elif line.strip().split(',')[0] == "*Elset":
                  readMode = InpFileParser.READ_ELSET
                  curElset = ElSet()
                  elsetName = "UNKNOWN_ELSET"
                  args = line.split(",")
                  for p in args:
                     if p.strip() == 'generate': curElset.generate=True
                     elif p.count('=') > 0:
                        var, val = p.split('=')
                        var = var.strip(); val = val.strip();
                        if var == 'elset':
                           elsetName = val
                           
                  curElset.name = elsetName
                  elsets.append(curElset)
                  
               else:
                  readMode = InpFileParser.UNKNOWN # skip comments and lines with unknown input
                  
                  # check if elemInput list is empty, otherwise there might be misaligned input data
                  if len(elemInput) != 0:
                     print "Warning: There are still %d unprocessed element input entries." % len(elemInput) 
            
            else:
               if readMode == InpFileParser.READ_NODES:
                  n = Node(*line.strip().split(','))
                  if nDim == -1: nDim = n.nDim
                  elif nDim != n.nDim:
                     print "Warning: Node %d spatial dimension %d doesn't match previous dimension %d." % (n.id, n.nDim, nDim)
                     nDim = n.nDim
                  nodes.append(n)
                     
               elif readMode == InpFileParser.READ_ELEMS:
                  if not numNodesKnown:
                     e = Element(*line.strip().split(','))
                     if numNodes == -1:
                        numNodes = e.numNodes
                        print ".Assuming %d nodes per element." % e.numNodes
                     elif numNodes != e.numNodes:
                        print "Warning: Element %d's number of nodes %d doesn't match previous number of nodes %d." % (e.id, e.numNodes, numNodes)
                        numNodes = e.numNodes
                     elems.append(e)
                  
                  else:
                     ints = []
                     for s in line.strip().split(','):
                        if s!="": ints.append(int(s))
                     elemInput.extend(ints)
                     
                     # check length of input list, try to create new elements as they come
                     while len(elemInput)>= (1+numNodes): # first number is the element ID
                        curElem, elemInput = elemInput[:1+numNodes], elemInput[1+numNodes:] # separate current element input from elemInput list
                        e = Element(*curElem)
                        elems.append(e)
                        
               elif readMode == InpFileParser.READ_NSET:
                  for s in line.strip().split(','):
                     if s.strip()!="": curNset.nodes.append(int(s))
                     
               elif readMode == InpFileParser.READ_ELSET:
                  if curElset.generate:
                     args = line.strip().split(',')
                     if len(args)!= 3: raise BaseException("Error: Invalid number of arguments (%d) for generated Elset - need 3 args (from, to, increment)" % len(args))
                     start, end, inc = int(args[0]), int(args[1]), int(args[2])
                     for e in xrange(start, end+1, inc):
                        curElset.elems.append(e)                  
                  
                  else: 
                     for s in line.strip().split(','):
                        if s.strip()!="": curElset.elems.append(int(s))
                  
               elif readMode == InpFileParser.UNKNOWN:
                  ignoredLines.append(lineNumber+1)
         
      print ".Parsed %d nodes (ndim=%d) and %d elements (nodes per element=%d)." % (len(nodes), nDim, len(elems), numNodes)
      if len(nsets)>0:
         print ".Parsed %d node sets and %d element sets" % (len(nsets), len(elsets))
      if len(ignoredLines)>0: print ".Ignored lines with unknown input: " + ", ".join([str(l) for l in ignoredLines])
      
      print "Successfully read input file." 
      
      mesh = AbaqusMesh()
      mesh.nodes = nodes
      mesh.elems = elems
      mesh.nsets = nsets
      mesh.elsets = elsets
      
      return mesh
   
class CustomInput:
   """ This is a rudimentary helper class allowing to generate custom input blocks for FEAP input files.
   It will just print the contents of its 'block' member variable to open the block (e.g. 'vbou' to start
   defining additional boundary conditions) and continue printing 
   
   Important member variables:
      - block     (str)            Type of input command (e.g. 'vbou', 'link', 'eloa', anything.
      - cards     (list of strs)   List of input card as specified for the respective FEAP command,
                                   separated by line breaks when written to the FEAP input file. 
      - pos       (int)            Determines the position of the custom input block. If pos <= 0,
                                   the custom input is written before applying boun/load commands
                                   emanating from node sets. For pos > 0 it is written afterwards
                                   (in this case, one could also include it into the footer).
   """
   def __init__(self, block="UNKNOWN", pos=1, cards=[]):
      self.block = block
      self.pos = pos
      self.cards = cards
      
   def __str__(self):
      s = ""
      s+= self.block + "\n"
      s+= "\n".join(self.cards)
      return s
            
class ConfigFileParser:
   """ Parser to read and interpret the JSON-style configuration file required to run this program.
   That file includes all required information to completely convert an Abaqus '.inp' file to a FEAP
   input file. It specifies the .inp-file, the file to write to, header and footer, and more. For a
   complete list, refer to the project documentation.
   Please note that the Python JSON parser is very restrictive, small syntax errors such as extra
   commas at the end of a list may already lead to non-readable files.
   
   A ConfigFileParser object is initialized with the config file and invoked with Build(), which will
   subsequently read and interpret the JSON config file, the Abaqus .inp file, header and footer
   and assemble all information to produce the FEAP output file which is also specified in the JSON
   config file.
   Provided all input is correct and no errors occur, all what the inp2feap main routine does is
   initializing a ConfigFileParser object with a JSON file specified as a command line parameter
   or by interactive input and call Build().
   
   This class includes some definitions on how what it expects in the JSON config file. Make sure
   to extend them when adding further functionality.
   """
   REQUIRED_VARS = ["input", "output"]
   KNOWN_VARS = ["input", "output", "nodesPerElem", "header", "footer", "centerMesh", "elsets", "nsets", "customInput"]
   ASSUMED_TYPES = { "input" : str, "output" : str, "nodesPerElem" : int, "header" : str, "footer" : str, "centerMesh" : bool, "nsets" : list, "elsets" : list, "customInput" : dict}
   
   CHILD_REQUIRED_VARS = { "elsets" : ["name"],
                           "nsets" :  ["name"],
                           "customInput" : ["block", "pos", "cards"] }
   CHILD_KNOWN_VARS = { "elsets" : ["name", "setMat", "duplicate"],
                        "nsets" :  ["name", "setBoun", "setLoad"],
                        "customInput" : ["block", "pos", "cards"]}
   CHILD_ASSUMED_TYPES = { "elsets": {"name" : str, "setMat" : int, "duplicate" : int},
                           "nsets":  {"name" : str, "setBoun" : str, "setLoad" : str},
                           "customInput" : {"block" : str, "pos" : int, "cards" : list}}
   
   def __init__(self, confFile=None):
      self.confFile = confFile
      
      self.inputFile = None  # abaqus .inp file to read mesh data from
      self.outputFile = None # feap iFoobar file to write data to
      self.headerFile = None # optional header file to insert before coor/elem blocks
      self.footerFile = None # optional footer file to append after all mesh data has been written
      
      self.nodesPerElem = None # nodes per element
      self.centerMesh = False  # center mesh
      
      self.headerString = ""
      self.footerString = ""
      
      self.elsets = []
      self.nsets = []
      self.customInputs = []
       
      pass
   
   def _ParseCustomInput(self, inp):
      """ Parse JSON substring specifying a custom input. """
      for var in ConfigFileParser.CHILD_REQUIRED_VARS["customInput"]:
         if var not in inp.keys():
            print "Error: Required parameter '%s' not found in custom input. Aborting." % (var)
            return 1
            
      for var, value in inp.iteritems():
         if var not in ConfigFileParser.CHILD_KNOWN_VARS["customInput"]:
            print "Warning: Unknown parameter '%s' in custom input. Will be ignored." % (var)
            
            if type(value) == unicode: value = str(value)
            
            if type(value) != ConfigFileParser.CHILD_ASSUMED_TYPES["customInput"][var]:
               print "Warning: Unsupported type '%s' for parameter '%s' in custom input." % (type(value), var)
               
      ci = CustomInput(inp["block"], inp["pos"], inp["cards"])
      return ci

   
   def _ParseElsets(self, elsets):
      """ Parse JSON substring specifying an element set. """
      elsetObjs = []
      
      for elset in elsets:
         for elsetVar in ConfigFileParser.CHILD_REQUIRED_VARS["elsets"]:
            if elsetVar not in elset.keys():
               print "Error: Required parameter '%s' not found in elset. Aborting." % (elsetVar)
               return 1
            
         elsetObj = ElSet()
               
         for elsetVar, elsetValue in elset.iteritems():
            if elsetVar not in ConfigFileParser.CHILD_KNOWN_VARS["elsets"]:
               print "Warning: Unknown parameter '%s' in elset. Will be ignored." % (elsetVar)
            
            if type(elsetValue) == unicode: elsetValue = str(elsetValue)
            
            if type(elsetValue) != ConfigFileParser.CHILD_ASSUMED_TYPES["elsets"][elsetVar]:
               print "Warning: Unsupported type '%s' for parameter '%s' in elset." % (type(elsetValue), elsetVar)
               
            if elsetVar == "name": elsetObj.name = str(elsetValue)
            elif elsetVar == "setMat" : elsetObj.setMat = int(elsetValue)
            elif elsetVar == "duplicate" : elsetObj.duplicate.append( int(elsetValue) )
         
         elsetObjs.append(elsetObj)
         
      return elsetObjs
   
   def _ParseNsets(self, nsets):
      """ Parse JSON substring specifying a node set. """
      nsetObjs = []
      
      for nset in nsets:
         for nsetVar in ConfigFileParser.CHILD_REQUIRED_VARS["nsets"]:
            if nsetVar not in nset.keys():
               print "Error: Required parameter '%s' not found in nset. Aborting." % (nsetVar)
               return 1
            
         nsetObj = NodeSet()
               
         for nsetVar, nsetValue in nset.iteritems():
            if nsetVar not in ConfigFileParser.CHILD_KNOWN_VARS["nsets"]:
               print "Warning: Unknown parameter '%s' in nset. Will be ignored." % (nsetVar)
            
            if type(nsetValue) == unicode: nsetValue = str(nsetValue)
            
            if type(nsetValue) != ConfigFileParser.CHILD_ASSUMED_TYPES["nsets"][nsetVar]:
               print "Warning: Unsupported type '%s' for parameter '%s' in nset." % (type(nsetValue), nsetVar)
               
            if nsetVar == "name": nsetObj.name = str(nsetValue)
            elif nsetVar == "setBoun" : nsetObj.setBoun = str(nsetValue)
            elif nsetVar == "setLoad" : nsetObj.setLoad = str(nsetValue)
         
         nsetObjs.append(nsetObj)
         
      return nsetObjs
   
   def _ParseConfig(self, confFile=None):
      """ Invoked as a main routine to parse the specified JSON config file. """
      if confFile is not None: self.confFile = confFile
      if self.confFile is None:
         raise ValueError("Error: No config file specified for parser!")
      
      self.workingDir = os.path.dirname(os.path.relpath(self.confFile))
      
      elsetObjs = []
      nsetObjs = []
      
      with open(self.confFile, 'r') as f:
         try: conf = json.load(f)
         except Exception as e: raise BaseException("Couldn't load JSON from %s. " % self.confFile + str(e))
         
         for var in ConfigFileParser.REQUIRED_VARS:
            if var not in conf.keys():
               print "Error: Required parameter '%s' not found in config file. Aborting." % (var)
               return EXIT_FAILURE
         
         for var, value in conf.iteritems():
            if var not in ConfigFileParser.KNOWN_VARS:
               print "Warning: Unknown parameter '%s' in config file. Will be ignored." % (var)
               continue
            
            if type(value) == unicode: value = str(value)
            
            if type(value) != ConfigFileParser.ASSUMED_TYPES[var]:
               print "Warning: Unsupported type '%s' for parameter '%s'." % (type(value), var)
            
            if var == "input": self.inputFile = str(value)
            elif var == "output": self.outputFile = str(value)
            elif var == "header": self.headerFile = str(value)
            elif var == "footer": self.footerFile = str(value)
            
            elif var == "centerMesh": self.centerMesh = bool(value)
            
            elif var == "nodesPerElem": self.nodesPerElem = int(value)
            
            elif var == "elsets":
               elsetObjs = self._ParseElsets(value)
            elif var == "nsets":
               nsetObjs = self._ParseNsets(value)
            
            elif var == "customInput":
               ci = self._ParseCustomInput(value)
               self.customInputs.append(ci)
               
      print "Successfully parsed config file '%s'." % self.confFile
      print ".Found instructions for %d nsets and %d elsets." % (len(nsetObjs), len(elsetObjs))
      print ".Found %d custom input blocks." % (len(self.customInputs))
      
      self.customInputs.sort(key=lambda ci: ci.pos)
      
      self.conf_nsets = nsetObjs
      self.conf_elsets = elsetObjs
      
      return EXIT_SUCCESS
   
   def _ParseInputFile(self, inputFile):
      """ Called to parse the Abaqus .inp file with the help of an InpFileParser object. """
      ifp = InpFileParser(inputFile)
      if self.nodesPerElem:
         ifp.nodesPerElem = self.nodesPerElem
      return ifp.Parse()
   
   def Build(self, confFile=None):
      """ Execute the complete build process from .inp to FEAP. This is the only
      function that should be invoked from outside. """
      
      # parse conf file
      if EXIT_SUCCESS == self._ParseConfig(confFile):
         
         # parse .inp file (mesh)
         mesh = self._ParseInputFile(os.path.join(self.workingDir, self.inputFile))
         
         # parse header and footer
         
         if self.headerFile: 
            with open(os.path.join(self.workingDir, self.headerFile), 'r') as f:
               self.headerString = f.read()
         if self.footerFile:
            with open(os.path.join(self.workingDir, self.footerFile), 'r') as f:
               self.footerString = f.read()
         
         # assign materials to mesh's ELSETS
         for conf_elset in self.conf_elsets:
            found = False 
            # try to find this elset (from config file) in mesh and assign specified material number
            for mesh_elset in mesh.elsets:
               if conf_elset.name == mesh_elset.name:
                  found = True
                  mesh_elset.setMat = conf_elset.setMat
                  print ".Setting material number %d for all elements in elset %s." % (mesh_elset.setMat, mesh_elset.name)
                  if len(conf_elset.duplicate) > 0:
                     mesh_elset.duplicate = conf_elset.duplicate
                     print ".Elset %s will be duplicated (materials %s)." % (mesh_elset.name, conf_elset.duplicate) 
                  break
            if not found: print "Warning: Couldn't find elset '%s' (specified in %s) in mesh %s." % (conf_elset.name, self.confFile, self.inputFile)
         
         # set element materials according to the elset they belong to
         for e in mesh.elems:
            for elset in mesh.elsets:
               if e.id in elset.elems:
                  e.matn = elset.setMat
                  # duplicate elements in any 'duplicate' elsets
                  if len(elset.duplicate)>0: e.duplicate = elset.duplicate
               
         # duplicate elements
         newElems = []
         for e in mesh.elems:
            if len(e.duplicate)>0:
               for matn in e.duplicate:
                  newId = mesh.elems[-1].id + len(newElems) + 1
                  duplicatedElem = Element(newId, *e.nodes)
                  duplicatedElem.matn = matn
                  newElems.append(duplicatedElem)
                  
         mesh.elems.extend(newElems)
            
         # assign boundary conditions to mesh's NSETS
         for conf_nset in self.conf_nsets:
            found = False
            # try to find this nset (from config file) in mesh and set boundary conditions
            for mesh_nset in mesh.nsets:
               if conf_nset.name == mesh_nset.name:
                  found = True
                  mesh_nset.setBoun = conf_nset.setBoun
                  mesh_nset.setLoad = conf_nset.setLoad
                  if len(conf_nset.setBoun)>0: print ".Adding 'boun' card '%s' for all nodes in nset %s." % (mesh_nset.setBoun, mesh_nset.name)
                  if len(conf_nset.setLoad)>0: print ".Adding 'load' card '%s' for all nodes in nset %s." % (mesh_nset.setLoad, mesh_nset.name)
                  break
            if not found: print "Warning: Couldn't find nset '%s' (specified in %s) in mesh %s." % (conf_nset.name, self.confFile, self.inputFile)
            
         # translate origin to center of mesh?
         if self.centerMesh:
            xMin = yMin = zMin = 1.e12
            xMax = yMax = zMax = -1.e12
            
            for n in mesh.nodes:
               if (n.x < xMin): xMin = n.x
               if (n.y < yMin): yMin = n.y
               if (n.z < zMin): zMin = n.z
               if (n.x > xMax): xMax = n.x
               if (n.y > yMax): yMax = n.y
               if (n.z > zMax): zMax = n.z
               
            lx = xMax - xMin
            ly = yMax - yMin
            lz = zMax - zMin
            dx = -xMin - lx/2.
            dy = -yMin - ly/2.
            dz = -zMin - lz/2.
            if not dx==dy==dz==0.:
               print ".Translating mesh from bounding box [%.2f,%.2f]x[%.2f,%.2f]x[%.2f,%.2f] by (%.2f,%.2f,%.2f) to new bounding box [%.2f,%.2f]x[%.2f,%.2f]x[%.2f,%.2f]." % \
                     (xMin,xMax,yMin,yMax,zMin,zMax, dx, dy, dz, xMin+dx, xMax+dx, yMin+dy, yMax+dy, zMin+dz, zMax+dz)
               for n in mesh.nodes:
                  n.x += dx; n.y += dy; n.z += dz
                  
         # write output
         with open(self.outputFile, 'w') as f:
            # write header
            if self.headerFile: f.write(self.headerString + "\n")
            
            # write nodes
            f.write('coor\n')
            for n in mesh.nodes: f.write(str(n))
            
            # write elems
            f.write('\nelem\n')
            for e in mesh.elems: f.write(str(e))
            
            # write all custom input blocks with pos < 0 before nset-boun-blocks
            for ci in self.customInputs:
               if ci.pos >= 0: break
               f.write('\n')
               f.write(str(ci))
               f.write('\n')
            
            # write boun/load-blocks generated from node sets
            for nset in mesh.nsets:
               if len(nset.setBoun)>0 or len(nset.setLoad)>0:
                  f.write('\n')
                  f.write(str(nset))
                  f.write('\n')
                  
            # write the rest of the custom input (could be in the footer as well)
            for ci in self.customInputs:
               if ci.pos < 0: continue
               f.write('\n')
               f.write(str(ci))
               f.write('\n')
            
            # write footer
            if self.footerFile: f.write("\n" + self.footerString)
            
            print "File %s written." % self.outputFile
         
         return EXIT_SUCCESS
      

def main():
   if len(sys.argv) > 1:
      inputFile = sys.argv[1]
   else:
      inputFile = raw_input("Input file: ")
      
   parser = ConfigFileParser(inputFile)
   parser.Build()
   return

if __name__=="__main__":
   main()