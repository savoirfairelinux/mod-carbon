mod-carbon
==========

Shinken module for listening data from Carbon client (Currently only in plaintext)

A data in plaintext respect the following pattern

```<metric path> <metric value> <metric timestamp>```

The metric path must respect the collectd naming schema
```host.plugin[-plugin_instance].type[-type_instance]```

(see here : https://collectd.org/wiki/index.php/Plugin:Write_Graphite)

Based on mod-collectd ( https://github.com/shinken-monitoring/mod-collectd/ )