Example
=======

Reading data from HDFQS
-----------------------

Refer to :ref:`installation` to install HDFQS.

Download the `example HDFQS datastore <http://www.projreality.com/hdfqs/examples/example.tgz>`_. Extract it into /tmp::

  cd /tmp
  tar -xvf [YOUR DOWNLOADED LOCATION]/example.tgz

In IPython, import the HDFQS module and instantiate the object with the example datastore::

  from hdfqs import HDFQS;
  h = HDFQS("/tmp/example");

You can see /tmp/example/2014/20140730.h5 get automatically registered in the manifest.

Use :meth:`get_fields` to see what fields are in the ``/office/Environment/temperature_office`` table::

  print(h.get_fields("/office/Environment/temperature_office"));

which returns::

  ['time', 'tz', 'value', 'raw']

Use :meth:`load` to load data::

  import calendar;
  import time;
  start = calendar.timegm(time.strptime("7/29/2014 4:00:00", "%m/%d/%Y %H:%M:%S"));
  stop = start + 3*3600; # Load 3 hours of data
  data = h.load("/office/Environment/temperature_office", start*1E9, stop*1E9);
  print(data.shape);

which returns::

  (10557, 2)

The data can be plotted using matplotlib::

  import matplotlib.pyplot as plt;
  plt.plot(data[:,1]);
  plt.title("Temperature over Time");
  plt.xlabel("Time (s)");
  plt.ylabel("Temperature (deg C)");
  plt.show();

.. image:: /images/example.png
  :align: center

Writing numpy arrays to HDFQS
-----------------------------

First, create an empty HDFQS location::

  mkdir /tmp/example2/2015 --parents

Next, generate some random data::

  import matplotlib.pyplot as plt;
  import numpy as np;
  import time;
  np.random.seed(1);

  # Generate time
  start = time.mktime(time.strptime("1/2/2015 16:30:15", "%m/%d/%Y %H:%M:%S"));
  start = start * 1E9; # Time is specified in ns since the epoch.
  stop = start + 60*1E9;
  N = 61;
  tm = np.linspace(start, stop, N).astype(np.int64);

  # Generate timezone
  tz = (time.timezone/3600*4) * np.ones(( N, )); # timezone is number of 15 min blocks west of UTC

  # Generate random data
  data = np.linspace(20,30,N) + np.random.randn(N);
  data = data[:,np.newaxis]; # data array must have shape ( N, P ) - in this case P=1
  cols = [ "value" ];

  # Plot data
  plt.plot(tm, data);
  plt.title("Temperature over Time");
  plt.xlabel("Time (ns since the epoch)");
  plt.ylabel("Temperature (deg C)");
  plt.show();

.. image:: /images/temperature.png
  :align: center

While writing a Pandas DataFrame is the preferred method, we'll start with writing the numpy arrays directly::

  import hdfqs;
  fd = hdfqs.HDFQS("/tmp/example2");
  units = { "value": "deg C" };
  fd.open_file("2015/temperature.h5");
  fd.write("/self/Environment/temperature", tm, tz, data, cols, name="Temperature data", units=units);
  fd.close_file();

Now that we're done writing to the file, we will register it into the manifest::

  fd.register("2015/temperature.h5");

Next, we'll read data back from HDFQS::

  start = time.mktime(time.strptime("1/2/2015", "%m/%d/%Y"))*1E9;
  stop = time.mktime(time.strptime("1/3/2015", "%m/%d/%Y"))*1E9;
  x = fd.load("/self/Environment/temperature", start, stop)
  plt.plot(x[:,0], x[:,1]);
  plt.title("Temperature over Time");
  plt.xlabel("Time (ns since the epoch)");
  plt.ylabel("Temperature (deg C)");
  plt.show();

The plot should be identical to the plot above.

Writing a Pandas DataFrame to HDFQS
-----------------------------------

The example above was more simple, as there was only one data column. Data with multiple columns can be written fairly easily as well. However, a problem may arise when the data columns have different types.

For example, the above temperature data can also include a status word from the device measuring temperature, which could be used as an indication of the validity of the data. Say the status word only takes values from 0 to 15. It would be a waste to use :literal:`np.float64` for that column (resulting in :literal:`tables.Float64Col` in the table), and may also result in roundoff error in the floating-point value::

  status = np.zeros(N, dtype=np.int8);
  status[30] = 1;
  data[30,0] = 0;

Note that if we directly concatenate status to data, it will take the :literal:`np.float64` type::

  print(np.c_[data, status].dtype);

Instead, we will create a Pandas DataFrame for the data. Note that we manually add each column to enforce column order (passing a :literal:`dict` will result in the columns being added alphabetically).

::

  import pandas as pd;
  df = pd.DataFrame();
  df["time"] = tm;
  df["tz"] = tz;
  df["value"] = data[:,0];
  df["status"] = status;

Now, we can pass the DataFrame directly to the :meth:`write` function::

  fd.open_file("2015/temperature2.h5");
  fd.write("/self/Environment/temperature2", df);
  fd.close_file();
  fd.register("2015/temperature2.h5");

Next, we read back the data::

  temperature = fd.load("/self/Environment/temperature2", start, stop);
  status = fd.load("/self/Environment/temperature2", start, stop, value_field="status");

If we plot the data directly, the invalid data point is included in the plot::

  plt.plot(temperature[:,0], temperature[:,1]);
  plt.title("Temperature over Time (with invalid data point)");
  plt.xlabel("Time (ns since the epoch)");
  plt.ylabel("Temperature (deg C)");
  plt.show();

.. image:: /images/plot_with_invalid_data.png
  :align: center

Instead, we use :literal:`status` to mask the invalid data::

  mask = np.ma.getmaskarray(temperature);
  mask[:,1] = status[:,1] != 0;
  temperature.mask = mask;

Now, the plot will exclude the invalid data point::

  plt.plot(temperature[:,0], temperature[:,1]);
  plt.title("Temperature over Time");
  plt.xlabel("Time (ns since the epoch)");
  plt.ylabel("Temperature (deg C)");
  plt.show();

.. image:: /images/plot_with_mask.png
