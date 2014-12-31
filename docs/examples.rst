Example
=======

The following examples assume you have copied HDFQS.py into your source tree as specified in :ref:`installation--including-directly-in-code`.

Download the `example HDFQS datastore <http://www.projreality.com/hdfqs/example.tgz>`_. Extract it into /tmp::

  cd /tmp
  tar -xvf [YOUR DOWNLOADED LOCATION]/example.tgz

In IPython, import the HDFQS module and instantiate the object with the example datastore::

  from HDFQS import HDFQS;
  hdfqs = HDFQS("/tmp/example");

You can see /tmp/example/2014/20140730.h5 get automatically registered in the manifest.

Use :meth:`get_fields` to see what fields are in the ``/office/Environment/temperature_office`` table::

  print(hdfqs.get_fields("/office/Environment/temperature_office"));

which returns::

  ['time', 'tz', 'value', 'raw']

Use :meth:`load` to load data::

  import calendar;
  import time;
  start = calendar.timegm(time.strptime("7/29/2014 4:00:00", "%m/%d/%Y %H:%M:%S"));
  stop = start + 3*3600; # Load 3 hours of data
  data = hdfqs.load("/office/Environment/temperature_office", start*1E9, stop*1E9);
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

