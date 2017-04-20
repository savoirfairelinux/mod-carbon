.. _carbon_installation:

============
Installation
============


Download
========

The Carbon module is available here:
  * https://github.com/savoirfairelinux/mod-carbon

Requirements
============

The Carbon module requires:

  * Python 2.6+
  * Shinken 2.0+

Installation
============

Copy the carbon module folder from the git repository to your shinken/modules directory (set by *modules_dir* in shinken.cfg)

Manual installation
~~~~~~~~~~~~~~~~~~~

For example, if your modules dir is '/var/lib/shinken/modules':

::

  cd /var/lib/shinken/modules
  wget https://github.com/savoirfairelinux/mod-carbon/archive/master.zip -O mod-carbon.zip
  unzip mod-carbon.zip