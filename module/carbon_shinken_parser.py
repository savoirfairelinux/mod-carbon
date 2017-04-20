import re

from .carbon_parser import (
    Reader,
    Values as _Values, Data as _Data,
    DEFAULT_INTERVAL
)


class Data(_Data):

    def __init__(self, *a, **kw):
        self.grouped_collectd_plugins = kw.pop('grouped_collectd_plugins', [])
        self.interval = kw.pop('interval', DEFAULT_INTERVAL)
        super(Data, self).__init__(*a, **kw)

    def get_srv_desc(self):
        """
        :param item: A carbon Data instance.
        :return: The Shinken service name related by this carbon stats item.
        """
        res = self.plugin
        if self.plugin not in self.grouped_collectd_plugins:
            if self.plugininstance:
                res += '-' + self.plugininstance
        # Dirty fix for 1.4.X:
        return re.sub(r'[' + "`~!$%^&*\"|'<>?,()=" + ']+', '_', res)

    def get_metric_name(self):
        res = self.type
        if self.plugin in self.grouped_collectd_plugins:
            if self.plugininstance:
                res += '-' + self.plugininstance
        if self.typeinstance:
            res += '-' + self.typeinstance
        return res

    def get_name(self):
        return '%s;%s' % (self.host, self.get_srv_desc())


class Values(Data, _Values):
    pass


class ShinkenCarbonReader(Reader):

    def __init__(self, *a, **kw):
        self.grouped_collectd_plugins = kw.pop('grouped_collectd_plugins', [])
        self.interval = kw.pop('interval', DEFAULT_INTERVAL)
        super(ShinkenCarbonReader, self).__init__(*a, **kw)

    def Values(self):
        return Values(interval=self.interval,
                      grouped_collectd_plugins=self.grouped_collectd_plugins)
