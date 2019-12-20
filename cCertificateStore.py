from mDebugOutput import cWithDebugOutput;
from .cSSLContext import cSSLContext;

class cCertificateStore(cWithDebugOutput):
  def __init__(oSelf):
    oSelf.__aoCertificateAuthorities = [];
    oSelf.__dsCertificateFilePath_by_sHostName = {};
    oSelf.__dsKeyFilePath_by_sHostName = {};
    oSelf.__doSSLContextForClient_by_sHostName = {};
    oSelf.__doSSLContextForServer_by_sHostName = {};
  
  def fAddCertificateAuthority(oSelf, oCertificateAuthority):
    assert not (oSelf.__doSSLContextForClient_by_sHostName or oSelf.__doSSLContextForServer_by_sHostName), \
        "Cannot add CAs after creating SSLContexts";
    oSelf.__aoCertificateAuthorities.append(oCertificateAuthority);
  
  def fAddCertificateFilePathForHostName(sHostName, sCertificateFilePath):
    oSelf.__dsCertificateFilePath_by_sHostName[sHostName] = sCertificateFilePath;
  
  def fAddCertificateAndKeyFilePathsForHostName(sHostName, sCertificateFilePath, sKeyFilePath):
    oSelf.__dsCertificateFilePath_by_sHostName[sHostName] = sCertificateFilePath;
    oSelf.__dsKeyFilePath_by_sHostName[sHostName] = sKeyFilePath;

  def foAddSSLContextForServerWithHostName(oSelf, oSSLContext, sHostName):
    assert sHostName not in oSelf.__doSSLContextForServer_by_sHostName, \
        "Cannot add two SSL contexts for the same server (%s)" % sHostName;
    oSelf.__doSSLContextForServer_by_sHostName[sHostName] = oSSLContext;
  
  def foGetSSLContextForServerWithHostName(oSelf, sHostName):
    oSelf.fEnterFunctionOutput(sHostName = sHostName);
    try:
      oSSLContext = oSelf.__doSSLContextForServer_by_sHostName.get(sHostName);
      if not oSSLContext:
        sCertificateFilePath = oSelf.__dsCertificateFilePath_by_sHostName.get(sHostName);
        if sCertificateFilePath:
          sKeyFilePath = oSelf.__dsKeyFilePath_by_sHostName.get(sHostName);
          if sKeyFilePath:
            oSSLContext = cSSLContext.foForServerWithHostNameAndKeyAndCertificateFilePath(sHostName, sKeyFilePath, sCertificateFilePath);
          else:
            oSSLContext = cSSLContext.foForServerWithHostNameAndCertificateFilePath(sHostName, sCertificateFilePath);
        else:
          for oCertificateAuthority in oSelf.__aoCertificateAuthorities:
            oSSLContext = oCertificateAuthority.foGetSSLContextForServerWithHostName(sHostName);
            if oSSLContext:
              break;
          else:
            raise AssertionError("No certificate file was found for %s and not CA has one either" % sHostName);
        oSelf.__doSSLContextForServer_by_sHostName[sHostName] = oSSLContext;
        for oCertificateAuthority in oSelf.__aoCertificateAuthorities:
          oSSLContext.fAddCertificateAuthority(oCertificateAuthority);
      return oSelf.fxExitFunctionOutput(oSSLContext);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
  
  def foGetSSLContextForClientWithHostName(oSelf, sHostName):
    oSelf.fEnterFunctionOutput(sHostName = sHostName);
    try:
      oSSLContext = oSelf.__doSSLContextForClient_by_sHostName.get(sHostName);
      if not oSSLContext:
        sCertificateFilePath = oSelf.__dsCertificateFilePath_by_sHostName.get(sHostName);
        if sCertificateFilePath:
          oSSLContext = cSSLContext.foForClientWithHostNameAndCertificateFilePath(sHostName, sCertificateFilePath);
        else:
          oSSLContext = cSSLContext.foForClientWithHostName(sHostName);
        oSelf.__doSSLContextForClient_by_sHostName[sHostName] = oSSLContext;
        for oCertificateAuthority in oSelf.__aoCertificateAuthorities:
          oSSLContext.fAddCertificateAuthority(oCertificateAuthority);
      return oSelf.fxExitFunctionOutput(oSSLContext);
    except Exception as oException:
      oSelf.fxRaiseExceptionOutput(oException);
      raise;
