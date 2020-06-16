Implementation of HTTP client, server and proxy using `mHTTPConnections`.

`cHTTPClient`
-------------
Implements a HTTP client that can make direct requests to HTTP servers.

`cHTTPClientUsingProxyServer`
-----------------------------
Implements a HTTP client that can make requests to HTTP servers through a
single HTTP proxy.

`cHTTPServer`
-------------
Implements a HTTP server.


`cHTTPClientSideProxyServer`
-----------------------------
Implements a HTTP proxy server that can forward requests from HTTP clients to
HTTP servers. Offers the option to MitM secure connections by generating SSL
certificates for the relevant domains.