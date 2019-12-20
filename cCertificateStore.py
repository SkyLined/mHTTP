from mDebugOutput import cWithDebugOutput;
from .cSSLContext import cSSLContext;

class cCertificateStore(cWithDebugOutput):
  def __init__(oSelf):
    oSelf.__aoCertificateAuthorities = [];
    oSelf.__dsCertificateFilePath_by_sHostname = {};
    oSelf.__dsKeyFilePath_by_sHostname = {};
    oSelf.__doSSLContextForClient_by_sHostname = {};
    oSelf.__doSSLContextForServer_by_sHostname = {};
  
  def fAddCertificateAuthority(oSelf, oCertificateAuthority):
    assert not (oSelf.__doSSLContextForClient_by_sHostname or oSelf.__doSSLContextForServer_by_sHostname), \
        "Cannot add CAs after creating SSLContexts";
    oSelf.__aoCertificateAuthorities.append(oCertificateAuthority);
  
  def fAddCertificateFilePathForHostname(sHostname, sCertificateFilePath):
    oSelf.__dsCertificateFilePath_by_sHostname[sHostname] = sCertificateFilePath;
  
  def fAddCertificateAndKeyFilePathsForHostname(sHostname, sCertificateFilePath, sKeyFilePath):
    oSelf.__dsCertificateFilePath_by_sHostname[sHostname] = sCertificateFilePath;
    oSelf.__dsKeyFilePath_by_sHostname[sHostname] = sKeyFilePath;

  def foAddSSLContextForServerWithHostname(oSelf, oSSLContext, sHostname):
    assert sHostname not in oSelf.__doSSLContextForServer_by_sHostname, \
        "Cannot add two SSL contexts for the same server (%s)" % sHostname;
    oSelf.__doSSLContextForServer_by_sHostname[sHostname] = oSSLContext;
  
  def foGetSSLContextForServerWithHostname(oSelf, sHostname):
    oSelf.fEnterFunctionOutput(sHostname = sHostname);
    try:
      oSSLContext = oSelf.__doSSLContextForServer_by_sHostname.get(sHostname);
      if not oSSLContext:
        sCertificateFilePath = oSelf.__dsCertificateFilePath_by_sHostname.get(sHostname);
        if sCertificateFilePath:
          sKeyFilePath = oSelf.__dsKeyFilePath_by_sHostname.get(sHostname);
          if sKeyFilePath:
            oSSLContext = cSSLContext.foForServerWithHostnameAndKeyAndCertificateFilePath(sHostname, sKeyFilePath, sCertificateFilePath);
          else:
            oSSLContext = cSSLContext.foForServerWithHostnameAndCertificateFilePath(sHostname, sCertificateFilePath);
        else:
          for oCertificateAuthority in oSelf.__aoCertificateAuthorities:
            oSSLContext = oCertificateAuthority.foGetSSLContextForServerWithHostname(sHostname);
            if oSSLContext:
              break;
          else:
            raise AssertionError("No certificate file was found for %s and not CA has one either" % sHostname);
        oSelf.__doSSLContextForServer_by_sHostname[sHostname] = oSSLContext;
        for oCertificateAuthority in oSelf.__aoCertificateAuthorities:
          oSSLContext.fAddCertificateAuthority(oCertificateAuthority);
      return oSelf.fxExitFunctionOutput(oSSLContext);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetSSLContextForClientWithHostname(oSelf, sHostname):
    oSelf.fEnterFunctionOutput(sHostname = sHostname);
    try:
      oSSLContext = oSelf.__doSSLContextForClient_by_sHostname.get(sHostname);
      if not oSSLContext:
        sCertificateFilePath = oSelf.__dsCertificateFilePath_by_sHostname.get(sHostname);
        if sCertificateFilePath:
          oSSLContext = cSSLContext.foForClientWithHostnameAndCertificateFilePath(sHostname, sCertificateFilePath);
        else:
          oSSLContext = cSSLContext.foForClientWithHostname(sHostname);
        oSelf.__doSSLContextForClient_by_sHostname[sHostname] = oSSLContext;
        for oCertificateAuthority in oSelf.__aoCertificateAuthorities:
          oSSLContext.fAddCertificateAuthority(oCertificateAuthority);
      return oSelf.fxExitFunctionOutput(oSSLContext);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
