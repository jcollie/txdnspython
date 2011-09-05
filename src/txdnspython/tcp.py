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
import collections
import time

from twisted.internet import defer
from twisted.internet.protocol import Protocol
from twisted.internet.protocol import ClientFactory
from twisted.python import failure
from twisted.python import log

import dns.exception
import dns.message

import txdnspython.generic

class TcpDnsClientProtocol(txdnspython.generic.GenericDnsClientProtocol, Protocol):
    def __init__(self, reactor, one_rr_per_rrset, ready):
        txdnspython.generic.GenericDnsClientProtocol.__init__(self, reactor, one_rr_per_rrset)
        self.ready = ready
        self.buffer = ''
        self.waiting_for = None

    def connectionMade(self):
        self.ready.callback(self)

    def connectionLost(self, reason):
        for id, (query, query_response, delayed_call) in self.pending.items():

            if delayed_call and delayed_call.active():
                delayed_call.cancel()

            query_response.errback(reason)

        self.pending.clear()

    def dataReceived(self, data):
        self.buffer += data
        while True:
            if self.waiting_for is None and len(self.buffer) < 2:
                return

            if self.waiting_for is None and len(self.buffer) >= 2:
                (self.waiting_for,) = struct.unpack('!H', self.buffer[:2])
                self.buffer = self.buffer[2:]

            if self.waiting_for > len(self.buffer):
                return

            wire_data = self.buffer[:self.waiting_for]
            self.buffer = self.buffer[self.waiting_for:]
            self.waiting_for = None

            self._process_response(wire_data)

    def send_query(self, query, query_response, timeout = None):
        wire_data = query.to_wire()
        self._send_query(struct.pack('!H', len(wire_data)) + wire_data,
                         query,
                         query_response,
                         timeout)

class TcpDnsClientFactory(ClientFactory):
    def __init__(self, reactor, one_rr_per_rrset):
        self.reactor = reactor
        self.one_rr_per_rrset = one_rr_per_rrset
        self.ready = defer.Deferred()

    def buildProtocol(self, addr):
        return TcpDnsClientProtocol(self.reactor, self.one_rr_per_rrset, self.ready)

class TcpDnsClient(object):
    def __init__(self, reactor, address, port = 53, one_rr_per_rrset = False, source = '', source_port = 0):
        """Initialize the client object.
        
        @param reactor: reactor
        @type reactor: twisted.internet.ReactorBase or subclass
        @param address: where to send the message
        @type address: string containing an IPv4 address
        @param port: The port to which to send the message.  The default is 53.
        @type port: int
        @param source: source address.  The default is the IPv4 wildcard address.
        @type source: string
        @param source_port: The port from which to send the message.
        The default is 0.
        @type source_port: int
        @param one_rr_per_rrset: Put each RR into its own RRset
        @type one_rr_per_rrset: bool
        """

        self.reactor = reactor
        self.queued = collections.OrderedDict()
        self.factory = TcpDnsClientFactory(self.reactor, one_rr_per_rrset)
        self.protocol = None
        self.factory.ready.addCallback(self._cbConnected)

        connector = self.reactor.connectTCP(address, port, self.factory, bindAddress=(source, source_port))

    def _cbConnected(self, result):
        self.protocol = result

        # now send all of the queued messages that were waiting for the
        # protocol to connect
        for query, query_response, delayed_call in self.queued.values():
            if delayed_call:
                delayed_call.cancel()
                timeout = delayed_call.getTime() - time.time()
                self.protocol.send_query(query, query_response, timeout)

            else:
                self.protocol.send_query(query, query_response, None)

        self.queued.clear()

    def send_query(self, query, timeout = None):
        """Send a query to the nameserver.

        @param query: the query
        @type query: dns.message.Message object
        @param timeout: The number of seconds to wait before the query times out.
        If None, the default, wait forever.
        @type timeout: float
        @rtype: twisted.internet.defer.Deferred object
        """

        query_response = defer.Deferred()

        if self.protocol is None:
            if timeout:
                delayed_call = self.reactor.callLater(timeout, self._timeout, query.id)

            else:
                delayed_call = None

            self.queued[query.id] = (query, query_response, delayed_call)

        else:
            self.protocol.send_query(query, query_response, timeout)

        return query_response

    def _timeout(self, query_id):
        if self.queued and self.queued.has_key(query_id):
            query, query_response, delayed_call = self.queued[query_id]
            del self.queued[query_id]
            query_response.errback(failure.Failure(dns.exception.Timeout()))

        elif self.protocol:
            self.protocol._timeout(query_id)

    def close(self):
        self.protocol.transport.loseConnection()
        self.protocol = None
