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

    ## Module:      Carbon
    ## Loaded by:   Arbiter, Receiver
    # Receive passive host and service results from a carbon client in plaintext format.
    # (Here : http://graphite.readthedocs.io/en/latest/feeding-carbon.html#the-plaintext-protocol )
    # The metric path send by the client must respect the collectd naming schema
    # (Here : https://collectd.org/wiki/index.php/Naming_schema )
    define module {
       module_name carbon
       module_type carbon

       # Activate and define the TCP connection
       use_tcp     True
       host_tcp    0.0.0.0
       port_tcp    2003

       # Activate and define the UDP connection
       use_udp     True
       host_udp    0.0.0.0
       port_udp    2003
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
       # grouped_collectd_plugins
    }

.. important:: You have to be sure that the *carbon.cfg* will be loaded by Shinken (watch in your shinken.cfg)


Parameters details
~~~~~~~~~~~~~~~~~~

:use_tcp:                       Activate the TCP connection
:host_tcp:                      Bind address for TCP connection. Default: 0.0.0.0
:port_tcp:                      Bind port for TCP connection. Default: 2003
:use_udp:                       Activate the UDP connection
:host_udp:                      Bind address for UDP connection. Default: 0.0.0.0
:port_udp:                      Bind port for TCP connection. Default: 2003
:multiscast:                    Activate multicast for UDP connection. Default: False
:interval:                      Time to wait (in s) other data for a couple of Host/Service to merge it inside the same perfdata Default: 10
:grouped_collectd_plugins:      List of collectd plugins where plugin instances will be group by plugin. Default: *empty*. Example: cpu,df,disk,interface


Receiver/Arbiter daemon configuration
-------------------------------------

Simply declare the module:

::

  modules carbon



Carbon client configuration
============================

Your carbon client must use the plaintext protocol ( http://graphite.readthedocs.io/en/latest/feeding-carbon.html#the-plaintext-protocol )

The metric path must respect the collectd naming schema ( ``host.plugin[-plugin_instance].type[-type_instance]`` )

The client can use TCP or UDP.

If you want group some metrics inside the same perfdata, you must send it in a smaller time than the interval parameter