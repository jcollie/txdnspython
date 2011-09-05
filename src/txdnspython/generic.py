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
        """
        Initialize.

        @param reactor: reactor to use to schedule delayed calls (used to implement timeouts)
        @type reactor: object that implements L{twisted.internet.interfaces.IReactorTime}
        @param one_rr_per_rrset: put each RR into its own RRset
        @type one_rr_per_rrset: C{bool}
        """

        self.reactor = reactor
        """
        Object that implements
        L{twisted.internet.interfaces.IReactorTime} - used to schedule
        delayed calls to implement timeouts.
        """

        self.one_rr_per_rrset = one_rr_per_rrset
        """Whether to put each RR into its own RRset"""

        self.pending = {}
        """
        L{dict} for keeping track of queries that have been sent to
        the remote nameserver but have not been responded to. The
        dictionary is indexed by the C{id} parameter of the
        L{dns.message.Message} object (the query ID).  The values are
        tuples of L{dns.message.Message},
        L{twisted.internet.defer.Deferred}, and
        L{twisted.internet.base.DelayedCall} (or C{None} if there is
        no timeout associated with the query).
        """

    def _process_response(self, wire_data):
        """
        Process the raw data retrieved from the remote name server.
        Match up the response with the original query and fire the
        L{twisted.internet.defer.Deferred} that is associated with the
        query.  Cancel the L{twisted.internet.base.DelayedCall} that
        may be associated with the query as well.

        @param wire_data: the raw data received from the remote DNS
        server, after removing any framing that may be required by the
        underlying transport.
        @type wire_data: C{str}
        """

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
        """
        Actually send the query over the wire and handle bookeeping.

        @param wire_data: the raw data that is to be sent over the
        wire, created by calling to_wire() on the query object, plus
        any framing that may be needed by the underlying transport.
        @type wire_data: C{str}

        @param query: the query
        @type query: L{dns.message.Message}

        @param query_response: a deferred that will be fired when a
        response is available or a failure has occurred.
        @type query_response: L{twisted.internet.defer.Deferred}

        @param timeout: The number of seconds to wait before the query
        times out. If C{None}, the default, wait forever.
        @type timeout: C{float}
        """
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
        """Callback used to implement request timeouts.

        @param query_id: the ID of the query that timed out.
        @type query_id: C{int}
        """

        if self.pending.has_key(query_id):
            query, query_response, delayed_call = self.pending.pop(query_id)
            query_response.errback(failure.Failure(dns.exception.Timeout()))
