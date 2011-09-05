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
import time

from twisted.python import failure
from twisted.python import log

import dns.exception
import dns.message

class GenericDnsClientProtocol(object):
    def __init__(self, reactor, one_rr_per_rrset):
        self.reactor = reactor
        self.one_rr_per_rrset = one_rr_per_rrset
        self.pending = {}

    def _process_response(self, wire_data):
        (query_id,) = struct.unpack('!H', wire_data[:2])
        
        if query_id not in self.pending:
            log.msg('No query with ID {} found to match received response!'.format(query_id))
            return

        query, query_response, delayed_call = self.pending.pop(query_id)
        
        if delayed_call and delayed_call.active():
            delayed_call.cancel()

        response = dns.message.from_wire(wire_data,
                                         keyring = query.keyring,
                                         request_mac = query.mac,
                                         one_rr_per_rrset = self.one_rr_per_rrset)
        
        if query.is_response(response):
            query_response.callback(response)
            
        else:
            query_response.errback(failure.Failure(BadResponse()))

    def _send_query(self, wire_data, query, query_response, timeout):
        if timeout:
            if timeout <= 0:
                query_response.errback(dms.exception.Timeout)
                return

            delayed_call = self.reactor.callLater(timeout, self._timeout, query.id)

        else:
            delayed_call = None

        self.pending[query.id] = (query, query_response, delayed_call)
        self.transport.write(wire_data)

    def _timeout(self, query_id):
        if self.pending.has_key(query_id):
            query, query_response, delayed_call = self.pending.pop(query_id)
            query_response.errback(failure.Failure(dns.exception.Timeout()))
