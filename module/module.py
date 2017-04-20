#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (C) 2017:
#    Flavien Peyre, flavien.peyre@savoirfairelinux.com
# Based on the code of mod-collectd, available here
# https://github.com/shinken-monitoring/mod-collectd
# Original copyrigth :
# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Gregory Starck, g.starck@gmail.com
#    Hartmut Goebel, h.goebel@goebel-consult.de
#    Thibault Cohen, thibault.cohen@savoirfairelinux.com
#
# This file is part of Shinken.
#
# Shinken is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Shinken is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Shinken.  If not, see <http://www.gnu.org/licenses/>.

"""
Carbon client Plugin for Receiver or arbiter
"""

import threading
import dummy_threading
import time
import traceback
from itertools import izip
from collections import namedtuple

#############################################################################

from shinken.basemodule import BaseModule
from shinken.external_command import ExternalCommand  # , ManyExternalCommand
from shinken.log import logger

#############################################################################

from .carbon_parser import (
    CarbonException,
    DEFAULT_PORT, DEFAULT_IPv4_GROUP, DEFAULT_INTERVAL
)
from .carbon_shinken_parser import (
    Data, Values, ShinkenCarbonReader
)

#############################################################################

properties = {
    'daemons': ['arbiter', 'receiver'],
    'type': 'carbon',
    'external': True,
}


#############################################################################

def get_instance(plugin):
    """
    This function is called by the module manager
    to get an instance of this module
    """
    if hasattr(plugin, "use_tcp"):
        use_tcp = plugin.use_tcp.lower() in ("yes", "true", "1")
    else:
        use_tcp = False

    if hasattr(plugin, 'host_tcp'):
        host_tcp = plugin.host_tcp
    else:
        host_tcp = "0.0.0.0"

    if hasattr(plugin, 'port_tcp'):
        port_tcp = int(plugin.port_tcp)
    else:
        port_tcp = DEFAULT_PORT

    if hasattr(plugin, "use_udp"):
        use_udp = plugin.use_udp.lower() in ("yes", "true", "1")
    else:
        use_udp = False

    if hasattr(plugin, 'host_udp'):
        host_udp = plugin.host_udp
    else:
        host_udp = DEFAULT_IPv4_GROUP
        multicast = True

    if hasattr(plugin, 'port_udp'):
        port_udp = int(plugin.port_udp)
    else:
        port_udp = DEFAULT_PORT

    if hasattr(plugin, "multicast"):
        multicast = plugin.multicast.lower() in ("yes", "true", "1")
    else:
        multicast = False

    if hasattr(plugin, 'interval'):
        interval = int(plugin.interval)
    else:
        interval = DEFAULT_INTERVAL

    if hasattr(plugin, 'grouped_collectd_plugins'):
        grouped_collectd_plugins = [name.strip()
                                    for name in plugin.grouped_collectd_plugins.split(',')]
    else:
        grouped_collectd_plugins = []

    udp = {}
    tcp = {}

    if use_udp:
        udp = {'host': host_udp, 'port': port_udp, 'multicast': multicast}
        logger.info("[Carbon] Using host=%s port=%d multicast=%d on UDP" % (host_udp, port_udp, multicast))

    if use_tcp:
        tcp = {'host': host_tcp, 'port': port_tcp}
        logger.info("[Carbon] Using host=%s port=%d on TCP" % (host_tcp, port_tcp))

    instance = CarbonArbiter(plugin, udp, tcp, interval, grouped_collectd_plugins)
    return instance


#############################################################################

MP = MetricPoint = namedtuple('MetricPoint',
                              'rawval val time here_time')


class Element(object):
    """ Element store service name and all perfdatas before send it in a external command """

    def __init__(self, host_name, sdesc, interval, last_sent=None):
        self.host_name = host_name
        self.sdesc = sdesc
        self.perf_datas = {}
        self.interval = interval
        if not last_sent:
            last_sent = time.time()
        # for the first time we'll wait 2*interval to be sure to get a complete data set :
        self.last_sent = last_sent + 2 * interval

    def _last_update(self, _op=max):
        """
        Return the maximal time of last reported perf data.
        If _op is different then returns that.
        :param _op: min or max
        :return:
        """
        return _op(met_pts[-1].here_time
                   for met_pts in self.perf_datas.values())

    @property
    def last_full_update(self):
        """
        :return: The last "full" update time of this element.
        i.e. the metric mininum last update own time.
        """
        return self._last_update(min)

    @property
    def send_ready(self):
        """
        :return: True if this element is ready to have its perfdata sent. False otherwise.
        """
        return (self.perf_datas and
                self._last_update() > self.last_sent and
                time.time() > self.last_sent + self.interval)

    def __str__(self):
        return '%s.%s' % (self.host_name, self.sdesc)

    def add_perf_data(self, mname, mvalues, mtime):
        """
        Add perf datas to this element.
        :param mname:   The metric name.
        :param mvalues: The metric read values.
        :param mtime:   The "epoch" time when the values were read.
        """
        if not mvalues:
            return

        res = []
        now = time.time()

        oldvalues = self.perf_datas.get(mname, None)
        if oldvalues is None:
            logger.info('%s : New perfdata: %s : %s' % (self, mname, mvalues))
            res.append(MP(mvalues, mvalues, mtime, now))
        else:
            for met_point, val in izip(oldvalues, mvalues):
                difftime = mtime - met_point.time
                if difftime < 1:
                    continue
                else:
                    res.append(MP(val, val, mtime, now))

        if res:
            self.perf_datas[mname] = res

    def get_command(self):
        """
        Look if this element has data to be sent to Shinken.
        :return
            - None if element has not all its perf data refreshed since last sent..
            - The command to be sent otherwise.
        """
        if not self.send_ready:
            return

        res = ''
        max_time = None
        for met_name, values_list in sorted(self.perf_datas.items(), key=lambda i: i[0]):
            for met_idx, met_pt in enumerate(values_list):
                value_to_str = lambda v: \
                    '%f' % v if isinstance(met_pt.val, float) else \
                    '%d' % v if isinstance(met_pt.val, int) else \
                    '%s' % v
                met_value = value_to_str(met_pt.val)
                res += ('{met_name}%s={met_value} ' % (
                    '_{met_idx}' if len(values_list) > 1 else ''
                )).format(**locals())
                if max_time is None or met_pt.here_time > max_time:
                    max_time = met_pt.here_time

        self.last_sent = time.time()
        return '[%d] PROCESS_SERVICE_OUTPUT;%s;%s;Carbon|%s' % (
            int(max_time), self.host_name, self.sdesc, res)


class CarbonArbiter(BaseModule):
    """ Main class for this carbon module """

    def __init__(self, modconf, udp, tcp,  interval, grouped_collectd_plugins=None,
                 use_dedicated_thread=False):
        BaseModule.__init__(self, modconf)
        self.udp = udp
        self.tcp = tcp
        self.interval = interval
        if grouped_collectd_plugins is None:
            grouped_collectd_plugins = []
        self.elements = {}
        self.grouped_collectd_plugins = grouped_collectd_plugins

        self.use_dedicated_thread = use_dedicated_thread
        th_mgr = (threading if use_dedicated_thread
                  else dummy_threading)
        self.lock = th_mgr.Lock()  # protect the access to self.elements
        self.send_ready = False

    def _read_carbon_packet(self, reader):
        """
        Read and interpret a packet from a carbon client.
        :param reader: A carbon Reader instance.
        """

        elements = self.elements
        lock = self.lock

        item_iterator = reader.interpret()
        while True:
            try:
                item = next(item_iterator)
            except StopIteration:
                break
            except CarbonException as err:
                logger.error('CarbonException: %s' % err)
                continue

            assert isinstance(item, Data)
            assert isinstance(item, Values)

            name = item.get_name()
            elem = elements.get(name, None)
            if elem is None:
                elem = Element(item.host,
                               item.get_srv_desc(),
                               self.interval)
                logger.info('Created %s ; interval=%s' % (elem, elem.interval))
            # now we can add this perf data:
            with lock:
                elem.add_perf_data(item.get_metric_name(), item, item.time)
                if name not in elements:
                    elements[name] = elem
                    # end for

    def _read_carbon(self, reader):
        while not self.interrupted:
            self._read_carbon_packet(reader)

    # When you are in "external" mode, that is the main loop of your process
    def main(self):

        use_dedicated_thread = self.use_dedicated_thread
        elements = self.elements
        lock = self.lock
        now = time.time()
        clean_every = 15
        report_every = 60
        next_clean = now + clean_every
        next_report = now + report_every
        n_cmd_sent = 0

        if not(self.udp or self.tcp):
            raise Exception('You must define a TCP or a UDP connection')

        reader = ShinkenCarbonReader(self.udp, self.tcp, interval=self.interval,
                                     grouped_collectd_plugins=self.grouped_collectd_plugins)
        try:
            if use_dedicated_thread:
                carbon_reader_thread = threading.Thread(target=self._read_carbon, args=(reader,))
                carbon_reader_thread.start()

            while not self.interrupted:

                if use_dedicated_thread:
                    time.sleep(1)
                else:
                    self._read_carbon_packet(reader)

                tosend = []
                with lock:
                    for elem in elements.itervalues():
                        cmd = elem.get_command()
                        if cmd:
                            tosend.append(cmd)
                # we could send those in one shot !
                # if it existed an ExternalCommand*s* items class.. TODO.
                for cmd in tosend:
                    self.from_q.put(ExternalCommand(cmd))
                n_cmd_sent += len(tosend)

                now = time.time()
                if now > next_clean:
                    next_clean = now + clean_every
                    if use_dedicated_thread:
                        if not carbon_reader_thread.isAlive() and not self.interrupted:
                            raise Exception('Carbon reader thread unexpectedly died.. exiting.')

                    todel = []
                    with lock:
                        for name, elem in elements.iteritems():
                            for perf_name, met_values in elem.perf_datas.items():
                                if met_values[0].here_time < now - 3 * elem.interval:
                                    # this perf data has not been updated for more than 3 intervals,
                                    # purge it.
                                    del elem.perf_datas[perf_name]
                                    logger.info('%s %s: 3*interval without data, purged.' % (
                                        elem, perf_name))
                            if not elem.perf_datas:
                                todel.append(name)
                        for name in todel:
                            logger.info('%s : not anymore updated > purged.' % name)
                            del elements[name]

                if now > next_report:
                    next_report = now + report_every
                    logger.info(
                        '%s commands reported during last %s seconds.' % (n_cmd_sent, report_every))
                    n_cmd_sent = 0

        except Exception as err:
            logger.error("[Carbon] Unexpected error: %s ; %s" % (err, traceback.format_exc()))
            raise
        finally:
            reader.close()
            if use_dedicated_thread:
                carbon_reader_thread.join()
