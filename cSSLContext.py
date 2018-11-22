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
  class cSSLHostNameException(cSSLContextException):
    pass;
  @classmethod
  def foForServerWithHostNameAndCertificateFilePath(cClass, sHostName, sCertificateFilePath):
    # Server side with everything in one file
    oPythonSSLContext = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH);
    oPythonSSLContext.load_cert_chain(certfile = sCertificateFilePath);
    sHostName
    return cClass(sHostName, oPythonSSLContext, bServerSide = True);
  
  @classmethod
  def foForServerWithHostNameAndKeyAndCertificateFilePath(cClass, sHostName, sKeyFilePath, sCertificateFilePath):
    # Server side with certificate and private key in separate files
    oPythonSSLContext = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH);
    oPythonSSLContext.load_cert_chain(keyfile = sKeyFilePath, certfile = sCertificateFilePath);
    return cClass(sHostName, oPythonSSLContext, bServerSide = True);
  
  @classmethod
  def foForClientWithHostNameAndCertificateFilePath(cClass, sHostName, sCertificateFilePath):
    # Client side with key pinning
    oPythonSSLContext = ssl.create_default_context(cafile = sCertificateFilePath);
    oPythonSSLContext.verify_mode = ssl.CERT_REQUIRED;
    oPythonSSLContext.check_hostname = False;
    return cClass(sHostName, oPythonSSLContext, bServerSide = False);
  
  @classmethod
  def foForClientWithHostName(cClass, sHostName):
    # Client side
    oPythonSSLContext = ssl.create_default_context();
    oPythonSSLContext.load_default_certs();
    oPythonSSLContext.verify_mode = ssl.CERT_REQUIRED;
    oPythonSSLContext.check_hostname = False;
    return cClass(sHostName, oPythonSSLContext, bServerSide = False);

  def __init__(oSelf, sHostName, oPythonSSLContext, bServerSide):
    oSelf.__sHostName = sHostName;
    oSelf.__oPythonSSLContext = oPythonSSLContext;
    oSelf.__bServerSide = bServerSide;
  
  @property
  def fbServerSide(oSelf):
    return oSelf.__sHostName is None;
  
  @property
  def fbClientSide(oSelf):
    return oSelf.__sHostName is not None;
  
  @property
  def sHostName(oSelf):
    assert oSelf.__sHostName, \
        "Server-side certificates do not have a hostname.";
    return oSelf.__sHostName;
  
  def fAddCertificateAuthority(oSelf, oCertificateAuthority):
    oSelf.__oPythonSSLContext.load_verify_locations(oCertificateAuthority.sCertificatePath);
  
  def foWrapSocket(oSelf, oPythonSocket, nTimeoutInSeconds, bCheckHostName = None):
    oSelf.fEnterFunctionOutput(oPythonSocket = oPythonSocket, bCheckHostName = bCheckHostName);
    try:
      if bCheckHostName is None:
        bCheckHostName = not oSelf.__bServerSide;
      if nTimeoutInSeconds <= 0:
        raise oSelf.cSSLException("Timeout before socket could be secured.", repr(oException));
      try:
        oPythonSocket.settimeout(nTimeoutInSeconds);
        oSSLSocket = oSelf.__oPythonSSLContext.wrap_socket(
          sock = oPythonSocket,
          server_side = oSelf.__bServerSide,
          server_hostname = None if oSelf.__bServerSide else oSelf.__sHostName,
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
      if bCheckHostName:
        oRemoteCertificate = oSSLSocket.getpeercert();
        assert oRemoteCertificate, \
            "No certificate!?";
        try:
          ssl.match_hostname(oRemoteCertificate, oSelf.__sHostName);
        except ssl.CertificateError as oException:
          # The SSL negotiation succeeded, but the hostname is incorrect so we did not get a reference to the wrapped
          # socket. This leaves oSocket in a non-useful state so we will close it.
          oPythonSocket.close();
          raise oSelf.cSSLHostNameException("The host name does not match the certificate.", repr(oException));
        except ssl.SSLError as oException:
          # The SSL negotiation failed, which leaves the socket in an unknown state so we will close it.
          oPythonSocket.close(); 
          raise oSelf.cSSLException("Could not check the hostname against the certificate.", repr(oException));
      return oSelf.fxExitFunctionOutput(oSSLSocket);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fCheckHostName(oSelf, oPythonSSLSocket):
    oSelf.fEnterFunctionOutput(oPythonSSLSocket = oPythonSSLSocket);
    try:
      try:
        ssl.match_hostname(oPythonSSLSocket.getpeercert(), oSelf.__sHostName);
      except ssl.CertificateError as oException:
        oPythonSSLSocket.shutdown(socket.SHUT_RDWR);
        oPythonSSLSocket.close();
        raise oSelf.cSSLHostNameException("The server reported an incorrect hostname for the secure connection", repr(oException));
      oSelf.fExitFunctionOutput();
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def fsToString(oSelf):
    sDetails = oSelf.__sHostName + (" (server side)" if oSelf.__bServerSide else "");
    return "%s{%s}" % (oSelf.__class__.__name__, sDetails);
