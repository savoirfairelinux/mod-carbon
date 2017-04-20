
from module.module import CarbonArbiter

from module import get_instance

from module.carbon_parser import decode_plaintext_packet
from module.carbon_parser import Parser

from module.module import Element

from shinken.objects.module import Module

import unittest2 as unittest
import time

basic_dict_modconf = dict(
    module_name='carbon',
    module_type='carbon'
)


class TestCarbonArbiter(unittest.TestCase):

    def setUp(self):

        self.basic_modconf = Module(basic_dict_modconf)

    def test_get_instance(self):
        result = get_instance(self.basic_modconf)
        self.assertIsInstance(result, CarbonArbiter)

    def test_init_defaults(self):
        arbiter = get_instance(self.basic_modconf)
        self.assertEqual(arbiter.tcp, {})
        self.assertEqual(arbiter.udp, {})
        self.assertEqual(arbiter.interval, 10)
        self.assertEqual(arbiter.grouped_collectd_plugins, [])

    def test_init_default_tcp_udp(self):
        modconf = Module(
            {
                'module_name': 'carbon',
                'module_type': 'carbon',
                'use_tcp': 'True',
                'use_udp': 'True'
            }
        )

        arbiter = get_instance(modconf)
        self.assertEqual(arbiter.tcp['host'], "0.0.0.0")
        self.assertEqual(arbiter.tcp['port'], 2003)
        self.assertEqual(arbiter.udp['host'], "239.192.74.66")
        self.assertEqual(arbiter.udp['port'], 2003)
        self.assertEqual(arbiter.udp['multicast'], False)

    def test_init(self):
        modconf = Module(
            {
                'module_name': 'carbon',
                'module_type': 'carbon',
                'use_tcp': 'True',
                'host_tcp': 'testhost',
                'port_tcp': '1111',
                'use_udp': 'True',
                'host_udp': 'testhost2',
                'port_udp': '1112',
                'multicast': 'False',
                'interval': '25',
                'grouped_collectd_plugins': 'disk,cpu,df'
            }
        )

        arbiter = get_instance(modconf)
        self.assertEqual(arbiter.tcp['host'], "testhost")
        self.assertEqual(arbiter.tcp['port'], 1111)
        self.assertEqual(arbiter.udp['host'], "testhost2")
        self.assertEqual(arbiter.udp['port'], 1112)
        self.assertEqual(arbiter.udp['multicast'], False)
        self.assertEqual(arbiter.interval, 25)
        self.assertEqual(arbiter.grouped_collectd_plugins, ['disk', 'cpu', 'df'])


class TestDecodePlaintextPacket(unittest.TestCase):
    def test_decode_plaintext(self):
        plaintext = "mycomputer.testcarbon.toto 10"
        data = decode_plaintext_packet(plaintext)
        value = data.next()
        self.assertEqual(value[0], "mycomputer.testcarbon.toto")
        self.assertEqual(value[1], 10)
        self.assertIsInstance(value[1], int)
        self.assertIsInstance(value[2], float)

        plaintext = "mycomputer.testcarbon.toto 10.4 1492439949.938185"
        data = decode_plaintext_packet(plaintext)
        value = data.next()
        self.assertEqual(value[0], "mycomputer.testcarbon.toto")
        self.assertEqual(value[1], 10.4)
        self.assertIsInstance(value[1], float)
        self.assertEqual(value[2], 1492439949.938185)
        self.assertIsInstance(value[2], float)

    def testInterpretOpcodes(self):
        parser = Parser()
        plaintext = "mycomputer.testcarbon.toto 10"
        packet_data = decode_plaintext_packet(plaintext)
        data = parser.interpret_opcodes(packet_data)
        value = data.next()
        self.assertEqual(value.host, "mycomputer")
        self.assertEqual(value.plugin, "testcarbon")
        self.assertEqual(value.type, "toto")
        self.assertIs(value.plugininstance, None)
        self.assertIs(value.typeinstance, None)

        plaintext = "mycomputer.testcarbon-1.toto-2 10.4"
        packet_data = decode_plaintext_packet(plaintext)
        data = parser.interpret_opcodes(packet_data)
        value = data.next()
        self.assertEqual(value.host, "mycomputer")
        self.assertEqual(value.plugin, "testcarbon")
        self.assertEqual(value.type, "toto")
        self.assertEqual(value.plugininstance, '1')
        self.assertEqual(value.typeinstance, '2')
        self.assertEqual(value[0], 10.4)


class TestElement(unittest.TestCase):
    def test_get_command(self):
        ts = 1492442591
        element = Element('mycomputer', 'testcarbon', 5, ts)
        ts = time.time()
        element.add_perf_data('toto', 10.43, ts)
        command = element.get_command()
        command = command.split()
        self.assertEqual(command[1],
                         'PROCESS_SERVICE_OUTPUT;mycomputer;testcarbon;Carbon|toto=10.430000')
