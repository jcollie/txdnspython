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

from twisted.internet import defer
from twisted.internet.protocol import DatagramProtocol
from twisted.python import log

import txdnspython.generic

class UdpDnsClientProtocol(txdnspython.generic.GenericDnsClientProtocol, DatagramProtocol):
    def __init__(self, reactor, address, port, one_rr_per_rrset):
        txdnspython.generic.GenericDnsClientProtocol.__init__(self, reactor, one_rr_per_rrset)
        self.address = address
        self.port = port

    def startProtocol(self):
        self.transport.connect(self.address, self.port)
        
    def datagramReceived(self, data, (address, port)):
        self._process_response(data)

    def send_query(self, query, query_response, timeout = None):
        wire_data = query.to_wire()
        self._send_query(wire_data,
                         query,
                         query_response,
                         timeout)

class UdpDnsClient(object):
    def __init__(self, reactor, address, port = 53, one_rr_per_rrset = False, source = '', source_port = 0):
        self.reactor = reactor
        self.protocol = UdpDnsClientProtocol(self.reactor, address, port, one_rr_per_rrset)
        self.reactor.listenUDP(source_port, self.protocol, interface = source)

    def send_query(self, query, timeout = None):
        query_response = defer.Deferred()
        self.protocol.send_query(query, query_response, timeout)
        return query_response

    def close(self):
        self.protocol.transport.loseConnection()
        self.protocol = None
