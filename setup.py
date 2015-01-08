from distutils.core import setup;

fd = open("README");
long_description = fd.read();
fd.close();

setup(name              = "hdfqs",
      version           = "1.1.0",
      py_modules        = [ "hdfqs" ],
      author            = "Samuel Li",
      author_email      = "sam@projreality.com",
      url               = "http://www.projreality.com/hdfqs",
      description       = "HDFQS Python Library",
      long_description  = long_description,
      license           = "https://www.gnu.org/licenses/lgpl.html"
     );
