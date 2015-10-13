# -*- coding: utf-8 -*-

import unittest, inp2feap

class TestNode(unittest.TestCase):
   def test_negative_id(self):
      """ Test if ValueError is raised when the node ID is negative. """
      with self.assertRaises(ValueError):
         inp2feap.Node(-22,0.7070,1.4142,-0.5)
      
   def test_data2d(self):
      """ Test if data is set correctly for a 2d node. """
      node = inp2feap.Node(1,3,4)
      self.assertEqual(node.id, 1)
      self.assertEqual(node.nDim, 2)
      self.assertEqual(node.x, 3)
      self.assertEqual(node.y, 4)
      
   def test_data3d(self):
      """ Test if data is set correctly for a 3d node. """
      node = inp2feap.Node(19,8,5,7)
      self.assertEqual(node.id, 19)
      self.assertEqual(node.nDim, 3)
      self.assertEqual(node.x, 8)
      self.assertEqual(node.y, 5)
      self.assertEqual(node.z, 7)
      
   def test_dataNd(self):
      """ Test if ValueError is raised when the number of coordinates is invalid (i.e. not 2 or 3). """
      for i in (0,1,4,5,6,7,236,196,9999):
         with self.assertRaises(ValueError):
            args = range(i) # list of i arbitrary numbers
            args.insert(0,17) # prepend some node id
            inp2feap.Node(*args)
            
   def test_dataTypes(self):
      """ Test if ValueError or TypeError is raised when any argument is not an integer. """
      testdata = ((1,2,3,"d"), (1,2,"c"), (1,"b",3,4), ("a",2,3))
      for d in testdata:
         with self.assertRaises((ValueError,TypeError)):
            inp2feap.Node(*d)
      
      
if __name__=="__main__":
   unittest.main()
      