import ssl;
from mDebugOutput import cWithDebugOutput;
from .cBufferedSocket import cBufferedSocket;
from .fbSocketExceptionIsClosedConnection import fbSocketExceptionIsClosedConnection;

class cSSLContext(cWithDebugOutput):
  class cSSLContextException(Exception):
    def __init__(oSelf, sMessage, sDetails):
      oSelf.sMessage = sMessage;
      oSelf.sDetails = sDetails;
      Exception.__init__(oSelf, sMessage, sDetails);
  class cSSLException(cSSLContextException):
    pass;
  class cSSLHostnameException(cSSLContextException):
    pass;
  @classmethod
  def foForServerWithHostnameAndCertificateFilePath(cClass, sHostname, sCertificateFilePath):
    # Server side with everything in one file
    oPythonSSLContext = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH);
    oPythonSSLContext.load_cert_chain(certfile = sCertificateFilePath);
    sHostname
    return cClass(sHostname, oPythonSSLContext, bServerSide = True);
  
  @classmethod
  def foForServerWithHostnameAndKeyAndCertificateFilePath(cClass, sHostname, sKeyFilePath, sCertificateFilePath):
    # Server side with certificate and private key in separate files
    oPythonSSLContext = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH);
    try:
      oPythonSSLContext.load_cert_chain(keyfile = sKeyFilePath, certfile = sCertificateFilePath);
    except ssl.SSLError, oError:
      oError.message = "Cannot load certificate chain (keyfile = %s, certfile = %s): %s" % (sKeyFilePath, sCertificateFilePath, oError.message);
      raise;
    return cClass(sHostname, oPythonSSLContext, bServerSide = True);
  
  @classmethod
  def foForClientWithHostnameAndCertificateFilePath(cClass, sHostname, sCertificateFilePath):
    # Client side with key pinning
    oPythonSSLContext = ssl.create_default_context(cafile = sCertificateFilePath);
    oPythonSSLContext.verify_mode = ssl.CERT_REQUIRED;
    oPythonSSLContext.check_hostname = False;
    return cClass(sHostname, oPythonSSLContext, bServerSide = False);
  
  @classmethod
  def foForClientWithHostname(cClass, sHostname):
    # Client side
    oPythonSSLContext = ssl.create_default_context();
    oPythonSSLContext.load_default_certs();
    oPythonSSLContext.verify_mode = ssl.CERT_REQUIRED;
    oPythonSSLContext.check_hostname = False;
    return cClass(sHostname, oPythonSSLContext, bServerSide = False);

  def __init__(oSelf, sHostname, oPythonSSLContext, bServerSide):
    oSelf.__sHostname = sHostname;
    oSelf.__oPythonSSLContext = oPythonSSLContext;
    oSelf.__bServerSide = bServerSide;
  
  @property
  def fbServerSide(oSelf):
    return oSelf.__sHostname is None;
  
  @property
  def fbClientSide(oSelf):
    return oSelf.__sHostname is not None;
  
  @property
  def sHostname(oSelf):
    assert oSelf.__sHostname, \
        "Server-side certificates do not have a hostname.";
    return oSelf.__sHostname;
  
  def fAddCertificateAuthority(oSelf, oCertificateAuthority):
    oSelf.__oPythonSSLContext.load_verify_locations(oCertificateAuthority.sCertificatePath);
  
  def foWrapSocket(oSelf, oPythonSocket, nTimeoutInSeconds, bCheckHostname = None):
    oSelf.fEnterFunctionOutput(oPythonSocket = oPythonSocket, bCheckHostname = bCheckHostname);
    try:
      if bCheckHostname is None:
        bCheckHostname = not oSelf.__bServerSide;
      if nTimeoutInSeconds <= 0:
        raise oSelf.cSSLException("Timeout before socket could be secured.", repr(oException));
      try:
        oPythonSocket.settimeout(nTimeoutInSeconds);
        oSSLSocket = oSelf.__oPythonSSLContext.wrap_socket(
          sock = oPythonSocket,
          server_side = oSelf.__bServerSide,
          server_hostname = None if oSelf.__bServerSide else oSelf.__sHostname,
          do_handshake_on_connect = False,
        );
      except ssl.SSLError as oException:
        # The SSL negotiation failed, which leaves the socket in an unknown state so we will close it.
        oPythonSocket.close(); 
        raise oSelf.cSSLException("Could not create secure socket.", repr(oException));
      except Exception as oException:
        if fbSocketExceptionIsClosedConnection(oException):
          raise cBufferedSocket.cConnectionClosedException(
            "Connection closed while negotiating secure connection",
            "exception = %s" % repr(oException),
          );
        oSelf.fStatusOutput("Exception while wrapping socket in SSL: %s" % repr(oException));
        raise;
      try:
        oSSLSocket.do_handshake();
      except ssl.SSLError as oException:
        # The SSL negotiation failed, which leaves the socket in an unknown state so we will close it.
        oPythonSocket.close(); 
        raise oSelf.cSSLException("Could not negotiate a secure connection.", repr(oException));
      except Exception as oException:
        if fbSocketExceptionIsClosedConnection(oException):
          raise cBufferedSocket.cConnectionClosedException(
            "Connection closed while negotiating secure connection",
            "exception = %s" % repr(oException),
          );
        oSelf.fStatusOutput("Exception while performing SSL handshake: %s" % repr(oException));
        raise;
      if bCheckHostname:
        oRemoteCertificate = oSSLSocket.getpeercert();
        assert oRemoteCertificate, \
            "No certificate!?";
        try:
          ssl.match_hostname(oRemoteCertificate, oSelf.__sHostname);
        except ssl.CertificateError as oException:
          # The SSL negotiation succeeded, but the hostname is incorrect so we did not get a reference to the wrapped
          # socket. This leaves oSocket in a non-useful state so we will close it.
          oPythonSocket.close();
          raise oSelf.cSSLHostnameException("The host name does not match the certificate.", repr(oException));
        except ssl.SSLError as oException:
          # The SSL negotiation failed, which leaves the socket in an unknown state so we will close it.
          oPythonSocket.close(); 
          raise oSelf.cSSLException("Could not check the hostname against the certificate.", repr(oException));
      return oSelf.fxExitFunctionOutput(oSSLSocket);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fCheckHostname(oSelf, oPythonSSLSocket):
    oSelf.fEnterFunctionOutput(oPythonSSLSocket = oPythonSSLSocket);
    try:
      try:
        ssl.match_hostname(oPythonSSLSocket.getpeercert(), oSelf.__sHostname);
      except ssl.CertificateError as oException:
        oPythonSSLSocket.shutdown(socket.SHUT_RDWR);
        oPythonSSLSocket.close();
        raise oSelf.cSSLHostnameException("The server reported an incorrect hostname for the secure connection", repr(oException));
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fsToString(oSelf):
    sDetails = oSelf.__sHostname + (" (server side)" if oSelf.__bServerSide else "");
    return "%s{%s}" % (oSelf.__class__.__name__, sDetails);
