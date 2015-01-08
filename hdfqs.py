# Copyright 2014, 2015 Samuel Li
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

"""
HDFQS Python Library

This module contains the class and all functions required for reading from and writing to HDFQS data stores.
"""

import numpy as np;
import os;
import pandas as pd;
import re;
import tables;

__version__ = "1.1.0";

class HDFQS:
  """
  This class wraps all functionality to read from and write to an HDFQS data store.
  """

################################################################################
################################# CONSTRUCTOR ##################################
################################################################################
  def __init__(self, path, register=True):
    """
    Create an HDFQS object given the path to the HDFQS data store.

    This function automatically runs :meth:`register_directory` on the HDFQS root.

    Parameters
    ----------
    path : str
      Path of root of HDFQS data store.
    """

    self.path = path;
    self.fd = None;
    self.filters = tables.Filters(complevel=1, complib="zlib", shuffle=True, fletcher32=True);
    self.manifest_path = os.path.join(self.path, "manifest.py");
    if (register):
      if (os.path.exists(self.manifest_path)):
        temp = { };
        execfile(self.manifest_path, temp);
        self.manifest = temp["manifest"];
        self.register_directory();
      else:
        self.reregister_all();

################################################################################
################################### REGISTER ###################################
################################################################################
  def register(self, filename, write_manifest=True):
    """
    Register a file in the HDFQS manifest.

    All HDF5 files within the HDFQS data store need to be registered in the manifest in order to be queried by HDFQS. The manifest associates all data tables with the HDF5 files that contain part of the table, along with the time range contained in each file.

    Note - all new files in the HDFQS data store are automatically registered when the HDFQS object is created. The use of this function is only required if new files are added into the HDFQS data store after the HDFQS object has been initialized.

    Parameters
    ----------
    filename : str
      Path of file to register. Can be relative to HDFQS root.
    write_manifest : bool
      Whether or not to write the updated manifest to the manifest file (default is True).
    """

    filename = os.path.join(self.path, filename); # If an absolute path is given, it does not get appended to the HDFQS path
    relpath = self.get_relpath(filename);

    if (relpath in self.manifest["FILES"]):
      return;

    fd = tables.openFile(filename, mode="r");
    self.manifest["FILES"][relpath] = True;
    for location in fd.root:
      for group in location:
        for table in group:
          if (type(table) != tables.Table):
            continue;
          if (table.shape == ( 0, )):
            continue;
          location_name = location._v_name;
          group_name = group._v_name;
          table_name = table.name;
          path = "/" + location_name + "/" + group_name + "/" + table_name;
          if (table.cols.time.is_indexed):
            start = table.cols.time[table.colindexes["time"][0]];
            stop = table.cols.time[table.colindexes["time"][-1]];
          else:
            start = min(row["time"] for row in table);
            stop = max(row["time"] for row in table);
          if (not self.manifest.has_key(path)):
            self.manifest[path] = [ { "filename": relpath, "start": start, "stop": stop } ];
          else:
            self.manifest[path].append({ "filename": relpath, "start": start, "stop": stop });

          if (location_name not in self.manifest["ROOT"]):
            self.manifest["ROOT"][location_name] = { };
          if (group_name not in self.manifest["ROOT"][location_name]):
            self.manifest["ROOT"][location_name][group_name] = { };
          if (table_name not in self.manifest["ROOT"][location_name][group_name]):
            self.manifest["ROOT"][location_name][group_name][table_name] = [ start, stop ];
          else:
            ( old_start, old_stop ) = self.manifest["ROOT"][location_name][group_name][table_name];
            self.manifest["ROOT"][location_name][group_name][table_name] = [ np.minimum(start, old_start), np.maximum(stop, old_stop) ];
    fd.close();

    if (write_manifest):
      self.write_manifest();

################################################################################
############################## REGISTER DIRECTORY ##############################
################################################################################
  def register_directory(self, path=""):
    """
    Register all HDF5 files in the specified directory.

    See documentation for :meth:`register` regarding automatic registration during initialization.

    Parameters
    ----------
    path : str
      Path of directory to register (default is the HDFQS root). Path can be relative to HDFQS root.
    """

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
          relpath = self.get_relpath(full_path);
          if (relpath not in self.manifest["FILES"]):
            print full_path;
            self.register(full_path, write_manifest=False);
            changed = True;
      elif (is_hdf5.match(subdir)): # Is an HDF5 file in the root
        if (subdir not in self.manifest["FILES"]):
          print subdir;
          self.register(subdir, write_manifest=False);
          changed = True;

    if ((changed) or (not os.path.exists(self.manifest_path))):
      self.write_manifest();

################################################################################
############################### RE-REGISTER ALL ################################
################################################################################
  def reregister_all(self):
    """
    Clear the manifest and reregister all HDF5 files in HDFQS data store.

    Use of this function is generally not necessary, unless damage to the manifest file is suspected.
    """

    self.manifest = { "FILES": { }, "ROOT": { } };
    self.register_directory();

################################################################################
##################################### LOAD #####################################
################################################################################
  def load(self, path, start, stop, numpts=0, time_field="time", value_field="value"):
    """
    Return data from the specified table and time range.

    This function loads data in the HDFQS data store from the specified data table within the specified time range. Note that the time range includes the endpoints. For tables with multiple value fields (e.g. x, y, z), only a single value field may be loaded. An optional parameter can specify the number of datapoints to return, in which case the specified number of datapoints, as evenly spaced as possible within the time range, will be returned.

    Parameters
    ----------
    path : str
      HDF5 path to the data table.
    start : int64
      Start of time range, in ns since the epoch.
    stop : int64
      End of time range, in ns since the epoch.
    numpts : int
      Number of points to return. Default is 0 (return all points within the time range).
    time_field : str
      Name of the time field in the table (default is "time").
    value_field : str
      Name of the value field to load (default is "value").

    Returns
    -------
    data : numpy.ma.array
      An Nx2 array containing the requested data. The first column is the time, the second column is the value.
    """

    files = self.query(path, start, stop);
    data = None;
    for f in files:
      fd = tables.openFile(os.path.join(self.path, f), mode="r");
      t = fd.getNode(path);
      if (len(t) < 2):
        continue;
      if (numpts == 0): # load all points
        data_from_file = np.ma.array([ [ x[time_field], x[value_field] ] for x in fd.getNode(path).where("(%s >= %d) & (%s <= %d)" % ( time_field, start, time_field, stop )) ]);
      else:
        temp = t[0:2];
        time_res = t[1][time_field] - t[0][time_field];
        stride_time = (stop - start) / np.float64(numpts);
        stride = int(np.floor(stride_time / time_res));
        if (stride > 0):
          data_from_file = np.ma.array([ [ x[time_field], x[value_field] ] for x in fd.getNode(path).where("(%s >= %d) & (%s <= %d)" % ( time_field, start, time_field, stop ), step=stride) ]);
        else: # more pixels than datapoints in time range
          data_from_file = np.ma.array([ [ x[time_field], x[value_field] ] for x in fd.getNode(path).where("(%s >= %d) & (%s <= %d)" % ( time_field, start, time_field, stop )) ]);
      if (len(data_from_file) > 0):
        if (data is None):
          data = data_from_file;
        else:
          data = np.concatenate(( data, data_from_file ));
      fd.close();

    if (data is None):
      return np.transpose(np.ma.array([ [ ], [ ] ]));
    else:
      return data;

################################################################################
################################## GET FIELDS ##################################
################################################################################
  def get_fields(self, path):
    """
    Return all fields in a data table.

    Parameters
    ----------
    path : str
      HDF5 path to the data table.

    Returns
    -------
    fields : list
      List containing the fields of the data table.

    Raises
    ------
    Exception
      Specified path does not exist.
    """

    files = self.query(path, 0, np.Inf);
    if (len(files) == 0):
      raise Exception("Nonexistant path: \"%s\"" % path);
    else:
      filename = files[0];
      fd = tables.openFile(os.path.join(self.path, filename));
      table = fd.getNode(path);
      fields = table.colnames;
      fd.close();
      return fields;

################################################################################
################################### SANITIZE ###################################
################################################################################
  def sanitize(self, filename, min_time=31536000000000000L, index=True):
    """
    Sanitize all tables in specified file.

    For each table in the file, this function removes all data entries with an invalid time (any time before the specified minimum time), and optionally adds a completely-sorted index on the time column (to speed up loading data).

    Parameters
    ----------
    filename : str
      Name of HDF5 file (absolute or relative to HDFQS root).
    min_time : int64
      Earliest valid time, in ns since the epoch (default is 1/1/1971 00:00:00 UTC).
    index : bool
      Whether or not to create a completely-sorted index on the time column (default is True).
    """

    filename = os.path.join(self.path, filename);
    fd = tables.openFile(filename, mode="a");
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
############################## SANITIZE DIRECTORY ##############################
################################################################################
  def sanitize_directory(self, path, no_links=False, min_time=31536000000000000L, index=True):
    """
    Sanitize all files in the specified directory.
    
    Run :meth:`sanitize` on all HDF5 files in the specified directory, recursing through all subdirectories. Links may be optionally ignored, for use with git annex. In this case, all files added into git annex can be assumed to be sanitized, while files not yet added (or which have been unlocked) will be sanitized.

    Parameters
    ----------
    path : str
      Path of directory to sanitize.
    no_links : bool
      Whether or not to ignore symlinks (default is False).
    min_time : int64
      Earliest valid time, in ns since the epoch (default is 1/1/1971 00:00:00 UTC).
    index : bool
      Whether or not to create a completed-sorted index on the time column (Default is False).

    Raises
    ------
    OSError
      Specified path does not exist.
    """

    path = os.path.join(self.path, path);
    if (not os.path.exists(path)):
      raise OSError("Invalid path - \"%s\"" % ( path ));
    for filename in os.listdir(path):
      if ((filename == ".git") or (filename == "raw")):
        continue;

      full_path = os.path.join(path, filename);
      if (os.path.isdir(full_path)):
        self.sanitize_directory(full_path, min_time=min_time, index=index);
      elif (no_links and os.path.islink(full_path)):
        continue;
      elif (filename[-3:] == ".h5"):
        self.sanitize(full_path, min_time=min_time, index=index);

################################################################################
################################ GET LOCATIONS #################################
################################################################################
  def get_locations(self):
    """
    Return all locations within HDFQS data store.
  
    Returns
    -------
    locations : list
      List containing all locations within HDFQS data store.
    """

    return self.manifest["ROOT"].keys();

################################################################################
################################ GET CATEGORIES ################################
################################################################################
  def get_categories(self, location):
    """
    Return all categories within specified location

    There are two ways to call this function. Either specify the location::

      get_categories({location});

    or specify the HDF5 path to the location::

      get_categories({path_in_hdf5});

    Parameters
    ----------
    location : str
      Location under which to search for categories. This may instead be a string containing the path in HDF5 to the location (must start with a "/").

    Returns
    -------
    categories : str
      List containing all categories within the specified location.

    Raises
    ------
    NonexistantLocationException : :class:`NonexistantLocationException`
      Specified path or :samp:`/{location}` does not exist.
    """

    try:
      if (location[0] == "/"):
        location = location[1:];
      return self.manifest["ROOT"][location].keys();
    except:
      raise NonexistantLocationException("Invalid location \"%s\"" % ( location ));

################################################################################
################################## GET TABLES ##################################
################################################################################
  def get_tables(self, location, category=None):
    """
    Return all tables within specified category

    There are two ways to call this function. Either specify the location and category separately::

      get_tables({location}, {category});

    or specify the HDF5 path to the category::

      get_tables({path_in_hdf5});

    Parameters
    ----------
    location : str
      Location containing the specified category. This may instead be a string containing the path in HDF5 to the category (must start with a "/").
    category : str
      Category under which to search for tables. Omit this parameter if specifying the category as a path in HDF5 (see :literal:`location` above).

    Returns
    -------
    tables : str
      List containing all tables within the specified location.

    Raises
    ------
    NonexistantLocationException : :class:`NonexistantLocationException`
      Specified path or :samp:`/{location}/{category}` does not exist.
    """

    try:
      if (category is None):
        x = re.match("/(.+)/(.+)", location);
        location = x.group(1);
        category = x.group(2);
      return self.manifest["ROOT"][location][category].keys();
    except:
      raise NonexistantLocationException("Invalid location/category: \"%s\", \"%s\"" % ( location, category ));

################################################################################
################################ GET TIME RANGE ################################
################################################################################
  def get_time_range(self, location, category=None, table=None):
    """
    Return the minimum and maximum time of data in the specified table.

    There are two ways to call this function. Either specify the location, category, and table separately::

      get_time_range({location}, {category}, {table});

    or specify the HDF5 path to the table::

      get_time_range({path_in_hdf5});

    Parameters
    ----------
    location : str
      Location containing the specified category. This may instead be a string containing the path in HDF5 to the table (must start with a "/").
    category : str
      Category containing the specified table. Omit this parameter if specifying the table as a path in HDF5 (see :literal:`location` above).
    table : str
      Table to query for minimum and maximum time of data. Omit this parameter if specifying the table as a path in HDF5 (see :literal:`location` above).

    Returns
    -------
    time_range : list
      List containing minuimum time as element 0, maximum time as element 1.

    Raises
    ------
    NonexistantLocationException : :class:`NonexistantLocationException`
      Specified path or :samp:`/{location}/{category}/{table}` does not exist.
    """

    try:
      if ((category is None) and (table is None)):
        x = re.match("/(.+)/(.+)/(.+)", location);
        location = x.group(1);
        category = x.group(2);
        table = x.group(3);
      return self.manifest["ROOT"][location][category][table];
    except:
      raise NonexistantLocationException("Invalid location/category/table: \"%s\", \"%s\", \"%s\"" % ( location, category, table ));

################################################################################
#################################### EXISTS ####################################
################################################################################
  def exists(self, location, category=None, table=None):
    """
    Check if a specified location/category/table exists.

    There are two ways to call this function. Either specify the location, category, and table separately::

      exists({location}); # check existance of location
      exists({location}, {category}); # check existance of category
      exists({location}, {category}, {table}); # check existance of table

    or specify the HDF5 path to the table::

      exists({path_in_hdf5});

    Parameters
    ----------
    location : str
      If :literal:`category` and :literal:`table` are omitted, this location is checked for existance. Alternately, this may instead be a string containing the path in HDF5 to the table (must start with a "/").
    category : str
      If :literal:`table` is omitted, this category under the specified location is checked for existance. Omit this parameter if specifying as a path in HDF5 (see :literal:`location` above).
    table : str
      Table to check for existance. Omit this parameter if specifying as a path in HDF5 (see :literal:`location` above).

    Returns
    -------
    existance : bool
      True if specified location/category/table exists, False otherwise.

    Raises
    ------
    NonexistantLocationException : :class:`NonexistantLocationException`
      Specified path, :samp:`/{location}`, :samp:`/{location}/{category}`, or :samp:`/{location}/{category}/{table}` does not exist.
    """

    try:
      if ((category is None) and (table is None) and (location[0] == "/")):
        tokens = location.split("/");
        location = tokens[1];
        if (len(tokens) > 2):
          category = tokens[2];
        else:
          category = None;
        if (len(tokens) > 3):
          table = tokens[3];
        else:
          table = None;
      try:
        if (table is not None):
          temp = self.manifest["ROOT"][location][category][table];
        elif (category is not None):
          temp = self.manifest["ROOT"][location][category];
        else:
          temp = self.manifest["ROOT"][location];
        return True;
      except KeyError:
        return False;
    except:
      raise NonexistantLocationException("Invalid location/category/table: \"%s\", \"%s\", \"%s\"" % ( location, category, table ));

################################################################################
################################## OPEN FILE ###################################
################################################################################
  def open_file(self, filename):
    """
    Open HDF5 file to perform write operations to.

    Parameters
    ----------
    filename : str
      Name of file. May be relative to HDFQS root.
    """

    filename = os.path.join(self.path, filename);
    self.fd = tables.openFile(filename, mode="a");

################################################################################
#################################### WRITE #####################################
################################################################################
  def write(self, path, df, tz=None, data=None, cols=None, name="", filters=None, units=None):
    """
    Write data into HDFQS data store.

    There are two ways of calling this function, depending on the format of the data to write. To write a Pandas dataframe::

      write({path}, {dataframe});

    Note that the dataframe must have a column named "time" (dtype np.int64) and a column named "tz" (dtype np.int8).

    To write a numpy array::

      write({path}, {time array}, {timezone array}, {data array}, {columns list});

    The dimensions of the array must be:

    +------+------------------+
    | Name |Dimension         |
    +======+==================+
    | time | ( N, )           |
    +------+------------------+
    | tz   | ( N, )           |
    +------+------------------+
    | data | ( N, P )         |
    +------+------------------+
    | cols | list of length P |
    +------+------------------+

    where N is the number of datapoints, P is the number of data columns (excluding time and tz).

    Note that :meth:`open_file` must have been called previously to specify a file to write to.

    Parameters
    ----------
    path : str
      HDF5 path to data table.
    df : pd.DataFrame
      Data to write, including the :literal:`time` and :literal:`tz` columns. Alternately, this can be a :literal:`np.ndarray(dtype=np.int64)` containing the time data.
    tz : np.ndarray(dtype=np.int8)
      Timezone values. Omit this parameter if writing a Pandas DataFrame (see :literal:`df` above).
    data : np.ndarray
      Data to write. Omit this parameter if writing a Pandas DataFrame (see :literal:`df` above).
    cols : list
      Names of the columns in :literal:`data`. Omit this parameter if writing a Pandas DataFrame (see :literal:`df` above).
    name : str
      Descriptive name of table (passed to :literal:`tables.createTable`).
    filters : tables.Filters
      PyTables filter for the table (passed to :literal:`tables.createTable`).
    units : dict
      Units for each of the columns, not including :literal:`time` and :literal:`tz`. The keys are the column names, the values are strings containing the units. Units for :literal:`time` and :literal:`tz` will be added automatically. This will be written to the table's :literal:`units` attribute. If not specified, a dict will be created with units specified for :literal:`time` and :literal:`tz` only.

    Raises
    ------
    NoFileOpenException : :class:`NoFileOpenException`
      :literal:`write` was called before :meth:`open_file`, or after :meth:`close_file`.
    InconsistentArgumentsException : :class:`InconsistentArgumentsException`
      If writing a Pandas DataFrame, must omit :literal:`tz`, :literal:`data`, and :literal:`cols`. If writing numpy arrays, must specify :literal:`tz`, :literal:`data`, and :literal:`cols`.
    """

    if (self.fd is None):
      raise(NoFileOpenException);

    # Generate DataFrame from data
    if ((tz is not None) and (data is not None) and (cols is not None)):
      tm = df;
      df = self.generate_df(tm, tz, data, cols);
    elif ((tz is not None) or (data is not None) or (cols is not None)):
      raise InconsistentArgumentsException("Must either pass DataFrame by itself, or pass time, timezone, data, columns");
    try: # Check if table exists
      t = self.fd.getNode(path);
    except tables.exceptions.NoSuchNodeError:
      # Parse where and name
      temp = path.rfind("/");
      where = path[:temp];
      table_name = path[temp+1:];
      # Create description
      descr = HDFQS.create_description(df);
      # Create table
      if (filters is None):
        filters = self.filters;
      t = self.fd.createTable(where, table_name, descr, name, filters=filters, createparents=True);
      if (units is None):
        units = { "time": "ns since the epoch", "tz": "15 min blocks from UTC" };
      elif (type(units) == dict):
        units["time"] = "ns since the epoch";
        units["tz"] = "15 min blocks from UTC";
      else:
        raise Exception("units must be a dict");
      t.attrs["units"] = units;
    # Add data
    t.append(df.values.tolist());
    # Create index
    if (not t.cols.time.is_indexed):
      t.cols.time.create_csindex();
    t.flush();

################################################################################
################################## CLOSE FILE ##################################
################################################################################
  def close_file(self):
    """
    Close HDF5 file being used for write operations.
    """

    if (self.fd is not None):
      self.fd.close();
      self.fd = None;

################################################################################
########################## INTERNAL UTILITY FUNCTIONS ##########################
################################################################################

################################################################################
################################# GET RELPATH ##################################
  def get_relpath(self, path):
    """
    Return path relative to HDFQS root.

    If the path is not within the HDFQS root, then return the path as is.

    Parameters
    ----------
    path : str
      Path of an HDF5 file.

    Returns
    -------
    relpath : str
      Path of specified file relative to HDFQS root, or absolute path if not within HDFQS root.
    """

    if (path.startswith(self.path)):
      return os.path.relpath(path, self.path);
    else:
      return path;

################################################################################
#################################### QUERY #####################################
  def query(self, path, start, stop):
    """
    Return filenames containing data from the specified table and time range.

    Parameters
    ----------
    path : str
      HDF5 path to data table.
    start : int64
      Start of time range, in ns since the epoch.
    stop : int64
      End of time range, in ns since the epoch.

    Returns
    -------
    files : list
      List of filenames which contain the specified data in the specified time range.
    """

    files = [ ];
    for entry in self.manifest[path]:
      if ((entry["start"] <= stop) and (entry["stop"] >= start)):
        files.append(entry["filename"]);

    return files;

################################################################################
################################# GENERATE DF ##################################
  def generate_df(self, tm, tz, data, cols):
    """
    Generate a Pandas DataFrame from numpy arrays.

    See table under :meth:`write` for a summary of the required shape of the various numpy arrays.

    Parameters
    ----------
    tm : np.ndarray(dtype=np.int64)
      Time data. Shape must be ( N, ), where N is the number of data points.
    tz : np.ndarray(dtype=np.int8)
      Timezone values. Shape must be ( N, ), where N is the number of data points.
    data : np.ndarray
      Data to write. Shape must be ( N, P ), where N is the number of data points, P is the number of data columns.
    cols : list
      Names of the columns in :literal:`data`. Must have length P, where P is the number of data columns (excluding time and timezone).

    Returns
    -------
    df : pd.DataFrame
      Pandas DataFrame containing the data.

    Raises
    ------
    InconsistentDimensionsException : :class:`InconsistentDimensionsException`
      Dimensions of :literal:`time`, :literal:`tz`, :literal:`data`, and/or :literal:`cols` are not consistent. See Parameters above, or summary table under :meth:`write`.
    """

    # Check consistency of dimensions
    if ((tm.shape[0] != tz.shape[0]) or (tm.shape[0] != data.shape[0]) or (data.shape[1] != len(cols))):
      raise InconsistentDimensionsException("Dimensions of tm %s, tz %s, data %s, cols (%d) not consistent" % ( str(tm.shape), str(tz.shape), str(data.shape), len(cols) ));

    tm = tm.astype(np.int64);
    tz = tz.astype(np.int8);
    df = pd.DataFrame(dict(time=tm, tz=tz));
    for i in range(len(cols)):
      df[cols[i]] = data[:,i];

    return df;

################################################################################
################################ WRITE MANIFEST ################################
  def write_manifest(self):
    """
    Write manifest to manifest file.
    """

    fd = open(self.manifest_path, "w");
    fd.write("manifest = " + repr(self.manifest) + "\n");
    fd.close();

################################################################################
############################## CREATE DESCRIPTION ##############################
  @staticmethod
  def create_description(df):
    """
    Create a PyTables description dict from a Pandas DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
      Dataframe to base description on (dtypes are automatically converted to PyTables column types).

    Returns
    -------
    descr : dict
      PyTables description generated from the column dtypes of the dataframe.
    """

    descr = dict();
    cols = df.columns.tolist();
    dtypes = df.dtypes.tolist();
    for i in range(len(cols)):
      col = cols[i];
      col_dtype = dtypes[i];
      descr[col] = tables.Col.from_dtype(col_dtype, pos=i);

    return descr;

################################################################################
################################## EXCEPTIONS ##################################
################################################################################
class NonexistantLocationException(Exception):
  pass;

class NoFileOpenException(Exception):
  pass;

class InconsistentArgumentsException(Exception):
  pass;

class InconsistentDimensionsException(Exception):
  pass;
