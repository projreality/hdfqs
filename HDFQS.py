import numpy;
import os;
import re;
from tables import *

class HDFQS:

################################################################################
################################# CONSTRUCTOR ##################################
################################################################################
  def __init__(self, path=None, manifest={ }):
    self.manifest = manifest;
    if (not self.manifest.has_key("FILES")):
      self.manifest["FILES"] = [ ];
    if (path is not None):
      self.register_directory(path);

################################################################################
################################### REGISTER ###################################
################################################################################
  def register(self, filename):
    fd = openFile(filename, mode="r");
    self.manifest["FILES"].append(filename);
    for location in fd.root:
      for group in location:
        for table in group:
          if (type(table) != Table):
            continue;
          tm = [ x["time"] for x in table ];
          path = "/" + location._v_name + "/" + group._v_name + "/" + table.name;
          if (not self.manifest.has_key(path)):
            self.manifest[path] = [ { "filename": filename, "start": tm[0], "stop": tm[-1] } ];
          elif (len(tm) > 0):
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
        if (full_path not in self.manifest["FILES"]):
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
  def load(self, path, start, stop, numpts=0, time_field="time", value_field="value"):
    files = self.query(path, start, stop);
    data = None;
    for f in files:
      fd = openFile(f, mode="r");
      t = fd.getNode(path);
      if (numpts == 0): # load all points
        data_from_file = numpy.ma.array([ [ x[time_field], x[value_field] ] for x in fd.getNode(path).where("(%s >= %d) & (%s <= %d)" % ( time_field, start, time_field, stop )) ]);
      else:
        temp = t[0:2];
        time_res = t[1][time_field] - t[0][time_field];
        stride_time = (stop - start) / numpy.float64(numpts);
        stride = int(numpy.floor(stride_time / time_res));
        if (stride > 0):
          data_from_file = numpy.ma.array([ [ x[time_field], x[value_field] ] for x in fd.getNode(path).where("(%s >= %d) & (%s <= %d)" % ( time_field, start, time_field, stop ), step=stride) ]);
        else: # more pixels than datapoints in time range
          data_from_file = numpy.ma.array([ [ x[time_field], x[value_field] ] for x in fd.getNode(path).where("(%s >= %d) & (%s <= %d)" % ( time_field, start, time_field, stop )) ]);
      if (len(data_from_file) > 0):
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

