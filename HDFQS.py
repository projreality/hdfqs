from tables import *

class HDFQS:

  def __init__(self, filename):
    fd = openFile(filename, mode="w");
    root = fd.root;

    fd.createGroup(root, "Location");
    fd.createGroup(root, "Health");
    fd.createGroup(root, "Environment");
    fd.createGroup(root, "Activity");
    fd.createGroup(root, "Context");
    fd.createGroup(root, "Sources");

    fd.close();
