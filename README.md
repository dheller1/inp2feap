# inp2feap #
-----------------------

Convert Abaqus .inp job files into input files for the research FEM code FEAP.


## Overview ##

*inp2feap* is a lightweight python script allowing to convert (some) finite element meshes from Abaqus to FEAP.
To get started, you need an Abaqus job file `.inp` and you must write a JSON-format configuration script, specifying how to process the input data.  

As the most basic functionality, only nodal coordinates and element connections are converted from `.inp` file format to FEAP's `coor` and `elem` blocks.
Optionally, header and footer files can be provided to add further instructions required by FEAP, as otherwise only an incomplete input file is written where nodes, elements and some boundary conditions are given.  
In addition, boundary conditions can be automatically set on node sets (*nsets*) using the FEAP command `boun`.
Element material numbers can be specified using Abaqus's element sets (*elsets*).

## Example ##

As an example we consider a shell discretization of a representative unit cell in a honeycomb sandwich panel.
The Abaqus job file is given in `examples/HexCell.inp`, it contains all nodes and elements, three element sets (`SET-ELEM_UNTEN`, `SET-ELEM_OBEN`, representing upper and lower face layers of the sandwich panel, and `SET-ELEM_WAENDE` for the cell walls), as well as a node set `SET-NODE-FHG6`, specifying some nodes where additional boundary conditions have to be set.  

`example/honeycomb.json` is the accompanying configuration file for this input file.  
Going through line by line, making sure to follow the JSON syntax:
 
- `"input" : "HexCell.inp", `  Specify the Abaqus job input file to read from.  
- `"output" : "iHexCell", ` File to write to (FEAP input file).
- `"nodesPerElem" : 4, ` Specify number of nodes per element (4-node quadrilateral here).
- `"header" : "header.inc", ` Contents of this file will be inserted before any generated `coor`/`elem` blocks.
- `"footer" : "footer.inc", ` Accordingly, contents of this file will be appended after any generated blocks. Here, the footer contains among other things the material definitions used in FEAP.
- `"centerMesh" : true, ` Optional. Allows to translate the origin to the center of the bounding box of all nodes.
- `"elsets" : [ { "name" : "SET-ELEM_UNTEN", "setMat" : 1 }, { "name" : "SET-ELEM_OBEN", "setMat" : 2 },`
  `  { "name" : "SET-ELEM_WAENDE", "setMat" : 3 }],`  
  Specify material number for all elements in element sets.
- `"customInput" : { "block" : "vbou", "pos" : -1, "cards" : ["-99.,99.,-99.,99.,-99.,99.,0,0,0,0,0,1"]}, `  
  Custom input allows to write any FEAP block and explicitly stating its input cards. With *pos*<0 the input is placed after `coor`/`elem` blocks, but before any automatically generated boundary conditions. This command locks the 6th DOF in the whole mesh.
- `"nsets" : [{	"name" : "SET-NODE-FHG6", "setBoun" : "0, 0, 0, 0, 0, 0" }],`  
  A `boun` block will be written, containing an input card for all nodes in this node set and freeing all b.c.s (i.e. freeing the 6th DOF again but only on intersection nodes).

**Note:** All file paths are relative to the `.json` config file.

To build the according FEAP input file for this example, just type:  
  `python inp2feap.py ../example/honeycomb.json`

## Limitations and issues ##

As of now, *inp2feap* has only been tested with 3d 4-node quadrilaterals.  
In theory, elements with an arbitrary number of nodes can be used as long as a FEAP element is present with a compatible node numbering.
For 2d models, however, the code must be modified.

Mixing elements with different numbers of nodes is not supported.
*inp2feap* can not distinguish between different parts in a job file, so keep them simple.
Only nodes, elements, nsets and elsets will be read from the input file, nothing else (like boundary conditions, loads, etc.)

## Config file documentation ##

Config files must follow valid JSON syntax.
Some error handling is present for required/optional parameters as well as data types, but don't rely too much on it.

See `examples/honeycomb.json` for an example config file with all required and optional parameters.

The following parameters can be used to specify *inp2feap*'s behavior:

- `"input"` - required. Abaqus job file (`.inp`) from where the mesh will be read.
- `"output"` - required. File to write the output (the FEAP input file) to.
- `"header"` - optional. Contents of this file will be inserted before any generated `coor`/`elem` blocks. Could contain the `feap` command and specifying a solver (`solv`).
- `"footer"` - optional. Contents of this file will be appended after any generated blocks. Could contain additional boundary conditions, loads, `mate` and `macr` blocks for FEAP.
- `"nodesPerElem"` - optional. Specify number of nodes per element. Meshes with elements with different numbers of nodes are not yet supported. Can be omitted, in which case the number of nodes is automatically determined. In case anything goes wrong, try to specify it explicitly.
- `"elsets"` - optional. If specified, must contain an array of element sets which each have a `"name"` (string) and `"setMat"` (int) parameter. *inp2feap* will look for elsets with the given name in the input file and assign the given material number to all elements in that elset.  
A warning will be issued should an element set specified in the config file not be found in the job file.
- `"nsets"` - optional. If specified, must contain an array of node sets which each have a `"name"` (string) and may have a `"setBoun"` (string) parameter. If `"setBoun"` is given, a `boun` block will be written to the output file, where each node in this node set has its boundary conditions set to the value of `"setBoun"`. Consult the FEAP manual for information on how the syntax must look like.  
A warning will be issued should a node set specified in the config file not be found in the job file.
- `"customInput"` - optional, may occur multiple times. If specified, must contain a child object with `"block"` (string), `"pos"` (int) and `"cards"` (array of strings) parameters. `"block"` should be a FEAP mesh command (e.g. `"vbou"`) which will be written to the output file, using the input cards `"cards"`. If `"pos"`<0, the block will be written in between `elem` blocks and automatically generated `boun` blocks from `"nsets"`. For `"pos"`>0, the block will be written after the `boun` blocks but before the footer. Multiple `"customInput`"s will be written in ascending order of their `"pos`".
- `"centerMesh"` - optional (true/false). If specified and true, the origin of the coordinate system will be translated to the center of the bounding box of all nodes.