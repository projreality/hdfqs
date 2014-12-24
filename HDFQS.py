# Copyright 2014 Samuel Li
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import numpy;
import os;
import re;
from tables import *

class HDFQS:

################################################################################
################################# CONSTRUCTOR ##################################
################################################################################
  def __init__(self, path):
    self.path = path;
    self.manifest_path = os.path.join(self.path, "manifest.py");
    if (os.path.exists(self.manifest_path)):
      temp = { };
      execfile(self.manifest_path, temp);
      self.manifest = temp["manifest"];
    else:
      self.manifest = { "FILES": { } };
    self.register_directory();

################################################################################
################################### REGISTER ###################################
################################################################################
  def register(self, filename):
    try:
      fd = openFile(filename, mode="r");
    except IOError:
      print "Error opening file %s" % ( filename );
      return;
    self.manifest["FILES"][filename] = True;
    for location in fd.root:
      for group in location:
        for table in group:
          if (type(table) != Table):
            continue;
          if (table.shape == ( 0, )):
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
  def register_directory(self, path=""):
    path = os.path.join(self.path, path);
    i = 0;
    is_hdf5 = re.compile("^.*\.h5$");
    changed = False;
    for subdir in os.listdir(path):
      if ((subdir == ".git") or (subdir == "raw") or (subdir == "manifest.py")):
        continue;
      subdir = os.path.join(path, subdir);
      if (os.path.isdir(subdir)): # Is a subdirectory
        for filename in os.listdir(subdir):
          if (not is_hdf5.match(filename)):
            i=i+1;
            continue;
          full_path = os.path.join(subdir, filename);
          if (full_path not in self.manifest["FILES"]):
            print full_path;
            self.register(full_path);
            changed = True;
      elif (is_hdf5.match(subdir)): # Is an HDF5 file in the root
        if (subdir not in self.manifest["FILES"]):
          print subdir;
          self.register(subdir);
          changed = True;

    if (changed):
      fd = open(self.manifest_path, "w");
      fd.write("manifest = " + repr(self.manifest) + "\n");
      fd.close();

################################################################################
############################### RE-REGISTER ALL ################################
################################################################################
  def reregister_all(self):
    self.manifest = { "FILES": { } };
    self.register_directory();

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
      if (len(t) < 2):
        continue;
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
################################## GET FIELDS ##################################
################################################################################
  def get_fields(self, path):
    files = self.query(path, 0, numpy.Inf);
    if (len(files) == 0):
      raise Exception("Nonexistant path: \"%s\"" % path);
    else:
      filename = files[0];
      fd = openFile(filename);
      table = fd.getNode(path);
      fields = table.colnames;
      fd.close();
      return fields;

################################################################################
#################################### CLEAN #####################################
################################################################################
  def clean(self, filename, min_time=31536000000000000L, index=True):
    fd = openFile(filename, mode="a");
    print filename;

    g = fd.root;
    for loc in g._v_children.items():
      loc = loc[1];
      for cat in loc._v_children.items():
        cat = cat[1];
        for t in cat._v_children.items():
          t = t[1];

          # Check if table is empty
          if (t.shape == ( 0, )):
            print "0%s" % ( t.name );
            continue;

          # Check for time before minimum
          bad_rows = t.read_where("time < min_time", { "min_time": min_time });
          if (bad_rows.shape[0] > 0):
            x = "-%s,%d" % ( t.name, t.shape[0] );
            tname = t.name;
            tnew = fd.createTable(cat, "%s_new" % ( tname ), t.description, t.title, filters=t.filters);
            t.attrs._f_copy(tnew);
            t.append_where(tnew, "time >= min_time", { "min_time": min_time });
            tnew.flush();
            t.remove();
            tnew.move(None, tname);
            x = "%s,%d,%d" % ( x, tnew.shape[0], bad_rows.shape[0] );
            print x;
            t = tnew;

          # Check if table is empty
          if (t.shape == ( 0, )):
            print "0%s" % ( t.name );
            continue;

          # Check for existance of time index
          if (index and (not t.cols.time.is_indexed)):
            print "*%s" % ( t.name );
            t.cols.time.create_csindex();

    fd.close();

################################################################################
############################### CLEAN DIRECTORY ################################
################################################################################
  def clean_directory(self, path, no_links=False, min_time=31536000000000000L, index=True):
    if (path[0] == os.path.sep):
      path = path[1:];
    path = os.path.join(self.path, path);
    if (not os.path.exists(path)):
      print("Invalid path - \"%s\"" % ( path ));
      return;
    for filename in os.listdir(path):
      if ((filename == ".git") or (filename == "raw")):
        continue;

      full_path = os.path.join(path, filename);
      if (os.path.isdir(full_path)):
        self.clean_directory(full_path, min_time=min_time, index=index);
      elif (no_links and os.path.islink(full_path)):
        continue;
      elif (filename[-3:] == ".h5"):
        self.clean(full_path, min_time=min_time, index=index);

