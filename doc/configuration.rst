.. _carbon_configuration:

=============
Configuration
=============

Shinken Carbon module
=======================

Carbon module declaration
---------------------------

Add and modify the following configuration in *carbon.cfg*

::

    define module {
       module_name carbon
       module_type carbon

       # Specify exact host (optional)
       host        0.0.0.0
       port        2003
       multicast   False

       # Interval is the time in second to wait for grouping many metrics from the same couple of host/service
       # inside the same perfdata.
       # By default it's 10 second
       # Example:
       # My carbon client send a metric M1 and a metric M2 for a service S on host H
       # If the time between M1 and M2 is < to 10 s , M1 and M2 are in the same perfdata for S
       # If the time between M1 and M2 is > to 10s, M1 are in a first perfdata. M2 will come inside the next perfdata
       interval    10

       # Select which collectd plugin you want to group
       # Example :
       # grouped_collectd_plugins     cpu, df
       # This will group all 'cpu' plugin instances in one service called 'cpu' with all perf datas : cpu-0-wait, cpu-1-wait, cpu-0-idle, cpu-1-idle, ....
       #  AND yhis will group all 'df' plugin instances in one service called 'df' with all perf datas : df-complex-root-free, ....
       # If grouped_collectd_plugins is empty
       # This will not group plugin instances and you will have this following services : cpu-0, cpu-1, df-root, ...
       #
       # grouped_carbon_plugins
    }
.. important:: You have to be sure that the *carbon.cfg* will be loaded by Shinken (watch in your shinken.cfg)


Parameters details
~~~~~~~~~~~~~~~~~~

:host:                          Bind address. Default: 0.0.0.0
:port:                          Bind port. Default: 2003
:multiscast:                    Default: False
:interval:                      Time to wait other data for a couple of host/Service to merge it inside the same perfdata Default: 10
:grouped_collectd_plugins:      List of collectd plugins where plugin instances will be group by plugin. Default: *empty*. Example: cpu,df,disk,interface


Receiver/Arbiter daemon configuration
-------------------------------------

Simply declare the module:

::

  modules carbon



Carbon client configuration
============================

Your carbon client must use the plaintext protocol ( http://graphite.readthedocs.io/en/latest/feeding-carbon.html#the-plaintext-protocol )

The metric path must respect the collectd naming schema ( ```host.plugin[-plugin_instance].type[-type_instance]``` )

The client must use TCP for the connection and send data to the defined host and port.