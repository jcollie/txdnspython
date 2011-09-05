# -*- mode: python; coding: utf-8 -*-

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import struct

from twisted.trial import unittest
from twisted.test import proto_helpers
from twisted.internet import selectreactor
from twisted.internet import defer
from twisted.internet import task

import txdnspython.tcp

import dns.message
import dns.exception

class TcpTest(unittest.TestCase):
    def setUp(self):
        self.reactor = selectreactor.SelectReactor()
        self.clock = task.Clock()
        self.reactor.callLater = self.clock.callLater
        self.factory = txdnspython.tcp.TcpDnsClientFactory(self.reactor, False)
        self.proto = self.factory.buildProtocol(('127.0.0.1', 53))
        self.transport = proto_helpers.StringTransport()
        self.proto.makeConnection(self.transport)

    def test_send_query(self):
        query = dns.message.make_query('www.google.com.', 'A')
        query_response = defer.Deferred()
        self.proto.send_query(query, query_response, None)
        wire_data = query.to_wire()
        wire_data = struct.pack('!H', len(wire_data)) + wire_data
        self.assertEqual(wire_data, self.transport.value())

    def test_timeout(self):
        query = dns.message.make_query('www.google.com.', 'A')
        query_response = defer.Deferred()
        self.proto.send_query(query, query_response, 5.0)
        self.clock.advance(5.0)
        self.assertFailure(query_response, dns.exception.Timeout)
