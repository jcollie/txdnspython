Twisted / DNS Python
====================

txdnspython is a way to use [dnspython][1] to create and manipulate
DNS messeages and then send those messages over the network using
[Twisted's][2] asynchronous networking.

dnspython has two interfaces for sending DNS data over the network -
dns.resolver.query and the tcp, udp, and xfr methods in the dns.query
module.  txdnspython currently can replace the dns.query.tcp and
dns.query.udp methods from dnspython.

An Example
----------

Here's an example of how to send a query (the code can be found in
examples/simple_udp_query.py):

    from twisted.internet import reactor
    
    import txdnspython
    
    import dns.message
    
    def printresult(result):
        print result
        reactor.stop()
    
    def printerror(reason):
        print reason
        reactor.stop()
    
    client = txdnspython.UdpDnsClient(reactor, '8.8.8.8')
    
    query_response = client.send_query(dns.message.make_query('www.google.com.', 'A'))
    query_response.addCallback(printresult)
    query_response.addErrback(printerror)
    reactor.run()

Running the Examples
--------------------

The example code can be run like this:

    PYTHONPATH=src python examples/simple_udp_query.py

Generating API Documentation
----------------------------

From the root of the source tree run this command:

    PYTHONPATH=src epydoc --html txdnspython

You'll need [epydoc][3] installed of course.

[1]: http://www.dnspython.org/ "dnspython"
[2]: http://twistedmatrix.com/ "Twisted"
[3]: http://epydoc.sourceforge.net/ "epydoc"
