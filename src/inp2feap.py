'''
Created on 28.04.2015

@author: heller
'''

import os, sys, json

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

class Node:
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
   def __init__(self, *args):
      self.nodes = []
      self.name = "Unnamed nset"
      self.setBoun = ""
      
   def __str__(self):
      if len(self.setBoun) == 0: return
      
      self.nodes = sorted(self.nodes)
      
      s = "boun ** NSET=%s\n" % self.name 
      for node in self.nodes:
         s += "%d, 0, %s\n" % (node, self.setBoun)
      
      return s

class ElSet:
   def __init__(self, *args):
      self.elems = []
      self.name = "Unnamed elset"
      self.setMat = 1
      self.generate = False
      self.duplicate = []
      
class AbaqusMesh:
   def __init__(self):
      self.nodes = []
      self.elems = []
      self.nsets = []
      self.elsets = []
      
class InpFileParser:
   READ_NODES = 1
   READ_ELEMS = 2
   READ_NSET = 3
   READ_ELSET = 4
   UNKNOWN = 0
   
   def __init__(self, filename=None, nodesPerElem=None):
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
               if line.startswith("*Node"):
                  readMode = InpFileParser.READ_NODES
                  continue
               elif line.startswith("*Element"):
                  readMode = InpFileParser.READ_ELEMS
                  elemInput = [] # list of all integer values read while in READ_ELEMS mode
                  continue
               elif line.startswith("*Nset"):
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
               elif line.startswith("*Elset"):
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
   REQUIRED_VARS = ["input", "output"]
   KNOWN_VARS = ["input", "output", "nodesPerElem", "header", "footer", "centerMesh", "elsets", "nsets", "customInput"]
   ASSUMED_TYPES = { "input" : str, "output" : str, "nodesPerElem" : int, "header" : str, "footer" : str, "centerMesh" : bool, "nsets" : list, "elsets" : list, "customInput" : dict}
   
   CHILD_REQUIRED_VARS = { "elsets" : ["name"],
                           "nsets" :  ["name"],
                           "customInput" : ["block", "pos", "cards"] }
   CHILD_KNOWN_VARS = { "elsets" : ["name", "setMat", "duplicate"],
                        "nsets" :  ["name", "setBoun"],
                        "customInput" : ["block", "pos", "cards"]}
   CHILD_ASSUMED_TYPES = { "elsets": {"name" : str, "setMat" : int, "duplicate" : int},
                           "nsets":  {"name" : str, "setBoun" : str},
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
         
         nsetObjs.append(nsetObj)
         
      return nsetObjs
   
   def _ParseConfig(self, confFile=None):
      if confFile is not None: self.confFile = confFile
      if self.confFile is None:
         raise ValueError("Error: No config file specified for parser!")
      
      self.workingDir = os.path.dirname(os.path.relpath(self.confFile))
      
      elsetObjs = []
      nsetObjs = []
      
      with open(self.confFile, 'r') as f:
         try: conf = json.load(f)
         except: raise BaseException("Couldn't load JSON from %s." % self.confFile)
         
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
      ifp = InpFileParser(inputFile)
      if self.nodesPerElem:
         ifp.nodesPerElem = self.nodesPerElem
      return ifp.Parse()
   
   def Build(self, confFile=None):
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
                  print ".Adding 'boun' card '%s' for all nodes in nset %s." % (mesh_nset.setBoun, mesh_nset.name)
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
            if self.headerFile: f.write(self.headerString)
            
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
            
            # write boun-blocks generated from node sets
            for nset in mesh.nsets:
               if len(nset.setBoun)> 0:
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
            if self.footerFile: f.write(self.footerString)
            
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