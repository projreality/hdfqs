import numpy;
import os;
import re;
from tables import *

class HDFQS:

################################################################################
################################# CONSTRUCTOR ##################################
################################################################################
  def __init__(self, path=None):
    self.manifest = { };
    if (path is not None):
      self.register_directory(path);

################################################################################
################################### REGISTER ###################################
################################################################################
  def register(self, filename):
    fd = openFile(filename, mode="r");
    for group in fd.root:
      for table in group:
        tm = [ x["time"] for x in table ];
        path = "/" + group._v_name + "/" + table.name;
        if (not self.manifest.has_key(path)):
          self.manifest[path] = [ { "filename": filename, "start": tm[0], "stop": tm[-1] } ];
        else:
          self.manifest[path].append({ "filename": filename, "start": tm[0], "stop": tm[-1] });
    fd.close();

################################################################################
############################## REGISTER DIRECTORY ##############################
################################################################################
  def register_directory(self, path):
    git_dir = re.compile("^" + path + "/.git");
    is_hdf5 = re.compile("^.*\.h5$");
    for direntry in os.walk(path):
      if (git_dir.match(direntry[0])):
        continue;
      for filename in direntry[2]:
        if (not is_hdf5.match(filename)):
          continue;
        full_path = os.path.join(direntry[0], filename);
        self.register(full_path);

################################################################################
#################################### QUERY #####################################
################################################################################
  def query(self, path, start, stop):
    files = [ ];
    for entry in self.manifest[path]:
      if ((entry["start"] <= stop) and (entry["stop"] >= start)):
        files.append(entry["filename"]);

    return files;

################################################################################
##################################### LOAD #####################################
################################################################################
  def load(self, path, start, stop, time_field="time", value_field="value"):
    files = self.query(path, start, stop);
    data = None;
    for f in files:
      fd = openFile(f, mode="r");
      t = fd.getNode(path);
      data_from_file = numpy.ma.array([ [ x[time_field], x[value_field] ] for x in fd.getNode(path).where("(%s >= %d) & (%s <= %d)" % ( time_field, start, time_field, stop )) ]);
      if (data is None):
        data = data_from_file;
      else:
        data = numpy.concatenate(( data, data_from_file ));
      fd.close();

    if (data is None):
      return numpy.transpose(numpy.array([ [ ], [ ] ]));
    else:
      return data;

################################################################################
############################### INITIALIZE FILE ################################
################################################################################
  @staticmethod
  def initialize_file(filename):
    fd = openFile(filename, mode="w");
    root = fd.root;

    fd.createGroup(root, "Location");
    fd.createGroup(root, "Health");
    fd.createGroup(root, "Environment");
    fd.createGroup(root, "Activity");
    fd.createGroup(root, "Context");
    fd.createGroup(root, "Sources");

    fd.close();

