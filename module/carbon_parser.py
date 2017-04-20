#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim: fileencoding=utf-8
# Copyright © 2017 Flavien Peyre <flavien.peyre@savoirfairelinux.com>
# Changed by Flavien Peyre :
# Replace the collectd binary protocol for parsing data to graphite
# plaintext protocol
# The code is based on mod-collectd, available here
# https://github.com/shinken-monitoring/mod-collectd
#
# Original copyright:
#       Copyright © 2009 Adrian Perez <aperez@igalia.com>
#
#       Distributed under terms of the GPLv2 license.

#
#       Updated by Rami Sayar for Collectd 5.1. Added DERIVE handling.
#       Updated by Grégory Starck with few enhancements.
#       - notably possibility to subclass Values and Notification.

"""
Carbon plaintext protocol implementation.
"""

import socket
import struct

from datetime import datetime
from select import select
from time import time
from copy import deepcopy

#############################################################################

DEFAULT_PORT = 2003
"""Default port"""

DEFAULT_IPv4_GROUP = "239.192.74.66"
"""Default IPv4 multicast group"""

DEFAULT_IPv6_GROUP = "ff18::efc0:4a42"
"""Default IPv6 multicast group"""

DEFAULT_INTERVAL = 10
"""Default interval for metric"""

#############################################################################

# https://github.com/graphite-project/carbon/blob/master/lib/carbon/protocols.py#L122-L124
# -> We can see carbon truncate line with len > 400 char
# In python, the size of a string is 38 + 1 per char
_BUFFER_SIZE = 445  # 445 > 438, ok we are safe.


#############################################################################


class CarbonException(Exception):
    pass


class CarbonValueError(CarbonException, ValueError):
    pass


class CarbonDecodeError(CarbonValueError):
    pass


class CarbonUnsupportedDSType(CarbonValueError):
    pass


class CarbonUnsupportedMessageType(CarbonValueError):
    pass


class CarbonBufferOverflow(CarbonValueError):
    pass


def decode_plaintext_packet(buf):
    """
    Decodes a packet in plaintext format.
    The metric name must respect the collectd naming schema
    """
    elem = buf.decode().split()
    metric_name = elem[0]
    val = elem[1]

    # Check if the value if a float or an int
    if '.' in val:
        val = float(val)
    else:
        val = int(val)
    # If we don't have a timestamp, we use current server time
    if len(elem) == 3:
        ts = float(elem[2])
    else:
        ts = time()

    yield metric_name, val, ts


class Data(object):
    time = None
    host = None
    plugin = None
    plugininstance = None
    type = None
    typeinstance = None

    def __init__(self, **kw):
        for k, v in kw.iteritems():
            setattr(self, k, v)

    @property
    def datetime(self):
        return datetime.fromtimestamp(self.time)

    @property
    def source(self):
        res = []
        if self.host:
            res.append(self.host)
        for attr in ('plugin', 'plugininstance', 'type', 'typeinstance'):
            val = getattr(self, attr)
            if val:
                res.append("/")
                res.append(val)
        return ''.join(res)

    def __str__(self):
        return "[%s] %s" % (self.time, self.source)


class Values(Data, list):
    """
    carbon Values
    contains a list of values associated with a particular carbon "element"
    """

    def __str__(self):
        return "%s %s" % (Data.__str__(self), list.__str__(self))


#############################################################################

class Parser(object):
    """
    Represent a carbon parser.
    Feed its `interpret´ method with some input and get Values instances.
    """
    Values = Values

    def receive(self):
        """
        Method used by the parser to get some data if you don't feed it
        explicitly with.
        If you want to make use of it you have to subclass and define it
        respecting the return format.
        :return: a 2-tuple : (buffer_read, address_read_from)
        The address_read_from format isn't enforced.
        """
        raise NotImplementedError

    def decode(self, buf=None):
        """
        Decodes a given buffer or the next received packet from `receive()´.
        :return: a generator yielding 3-tuples (name, value, timestamp).
        """
        if buf is None:
            buf = self.receive()
        return decode_plaintext_packet(buf)

    def interpret_opcodes(self, iterable):
        """
        :param iterable: An iterable of 3-tuples (metric_name ,value, ts).
        :return: A generator yielding Values instances based on the iterable.
        :raise: The generator, when yielding results, can raise a CarbonException
        (or subclass) instance if there is a decode error.
        """
        vl = self.Values()

        # We parse our packet to obtain the collectd naming's schema informations,
        # the value and the timestamp:
        # format of metric_name :
        # host.plugin[-plugin_instance].type[-type_instance]

        for metric_name, value, ts in iterable:
            plugin_instance = None
            compl_instance = None
            host, plugin, compl = metric_name.split('.')

            if '-' in plugin:
                plugin, plugin_instance = plugin.split('-')

            if '-' in compl:
                compl, compl_instance = compl.split('-')

            vl.time = ts
            vl.host = host
            vl.plugin = plugin
            vl.plugininstance = plugin_instance
            vl.type = compl
            vl.typeinstance = compl_instance
            vl[:] = [value]

            yield deepcopy(vl)

    def interpret(self, input=None):
        """
        Interprets an explicit or implicit `input´ "sequence" if given.

        :param input:
            If None or not given -> A fresh packet will be read from the socket.
            Then the packet will be decode().

            If a basestring -> It will also be decode().

            After what the result of decode()
            (a generator which yields 3-tuple (name, value, timestamp))
            is given to interpret_opcodes() which will then yield carbon `Values´  instances.

            If the `input´ initial value isn't None nor a basestring then it's directly given to
            interpret_opcodes(), you have to make sure the `input´ has the correct format.

        :return: A generator yielding carbon `Values´  instances.

        :raise:
            When a read on the socket is needed, it's not impossible to raise some IO exception.
            Otherwise no raise should occur to return the generator.
            But the returned generator can raise (subclass-)`CarbonException´ instance
            if a decode problem occurs.
        """
        if isinstance(input, (type(None), basestring)):
            input = self.decode(input)
        return self.interpret_opcodes(input)


class Reader(Parser):
    """
    Network reader for a plaintext carbon data.
    Open UDP/TCP connection on a given address.
    For UDP, the address can be a multicast group address.
    Reader handles reading data when it arrives.
    """

    def __init__(self, udp, tcp):
        """
        :param udp: A dict with a host and a port for a TCP connection .
        :param tcp: A dict with a host, a port and a multicast bollean for a UDP connection.
        :return: A ready to be used carbon Reader instance.
        """
        self._sock_tcp = None
        self._sock_udp = None

        self.udp, self.tcp = udp, tcp

        if self.tcp:
            self.ipv6_tcp = ":" in self.tcp['host']
            family, socktype, proto, canonname, sockaddr = socket.getaddrinfo(
                self.tcp['host'], self.tcp['port'],
                socket.AF_INET6 if self.ipv6_tcp else socket.AF_UNSPEC,
                socket.SOCK_STREAM, 0, socket.AI_PASSIVE)[0]

            self._sock_tcp = socket.socket(family, socktype, proto)
            self._sock_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock_tcp.bind(sockaddr)
            self._sock_tcp.listen(5)

        if self.udp:
            if self.udp['host'] is None:
                self.udp['multicast'] = True
                self.udp['host'] = DEFAULT_IPv4_GROUP

            self.ipv6_udp = ":" in self.udp['host']
            family, socktype, proto, canonname, sockaddr = socket.getaddrinfo(
                    None if self.udp['multicast'] else self.udp['host'], self.udp['port'],
                    socket.AF_INET6 if self.ipv6_udp else socket.AF_UNSPEC,
                    socket.SOCK_DGRAM, 0, socket.AI_PASSIVE)[0]

            self._sock_udp = socket.socket(family, socktype, proto)
            self._sock_udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock_udp.bind(sockaddr)

            if self.udp['multicast']:
                if hasattr(socket, "SO_REUSEPORT"):
                    self._sock_udp.setsockopt(
                        socket.SOL_SOCKET,
                        socket.SO_REUSEPORT, 1)

                val = None
                if family == socket.AF_INET:
                    assert "." in self.udp['host']
                    val = struct.pack("4sl",
                                      socket.inet_aton(self.udp['host']), socket.INADDR_ANY)
                elif family == socket.AF_INET6:
                    raise NotImplementedError("IPv6 support not ready yet")
                else:
                    raise ValueError("Unsupported network address family")

                self._sock_udp.setsockopt(
                    socket.IPPROTO_IPV6 if self.ipv6_udp else socket.IPPROTO_IP,
                    socket.IP_ADD_MEMBERSHIP, val)
                self._sock_udp.setsockopt(
                    socket.IPPROTO_IPV6 if self.ipv6_udp else socket.IPPROTO_IP,
                    socket.IP_MULTICAST_LOOP, 0)

    def receive(self):
        """ Receives a single raw carbon plaintext packet. """
        sock = []
        if self._sock_tcp:
            sock.append(self._sock_tcp)
        if self._sock_udp:
            sock.append(self._sock_udp)

        inputready, outputready, exceptready = select(sock, [], [])

        for s in inputready:
            if s == self._sock_tcp:
                connect, _ = self._sock_tcp.accept()
                return connect.recv(_BUFFER_SIZE)
            elif s == self._sock_udp:
                buf, addr_from = self._sock_udp.recvfrom(_BUFFER_SIZE)
                return buf
            else:
                print "unknown socket:", s

    def close(self):
        if self._sock_tcp:
            self._sock_tcp.close()
        if self._sock_udp:
            self._sock_udp.close()
