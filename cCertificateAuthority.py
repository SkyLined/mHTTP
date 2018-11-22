import os, subprocess;
from .cSSLContext import cSSLContext;
from mMultiThreading import cLock, cWithCallbacks;

gsMainFolderPath = os.path.dirname(__file__);

class cCertificateAuthority(object):
  __sOpenSSLBinaryPath = os.path.join(gsMainFolderPath, "OpenSSL", "OpenSSL.exe");

  oCertificateFilesLock = cLock("foGenerateSSLContextForServerWithHostName.py/goCertificateFilesLock");
  def __init__(oSelf, sBaseFolderPath):
    oSelf.__sBaseFolderPath = sBaseFolderPath;
    oSelf.__sOpenSSLConfigFilesFolderPath = os.path.join(sBaseFolderPath, "Config");
    oSelf.__sGeneratedCertificatesFolderPath = os.path.join(sBaseFolderPath, "Generated");
    oSelf.__sCertificatePath = os.path.join(sBaseFolderPath, "Config", "root+intermediate.cert.pem");
  
  @property
  def sCertificatePath(oSelf):
    return oSelf.__sCertificatePath;
  
  def __fExecuteOpenSSL(oSelf, *asArguments):
    try:
      subprocess.check_output(
        args = [oSelf.__sOpenSSLBinaryPath] + list(asArguments),
        cwd = oSelf.__sBaseFolderPath,
        stderr = subprocess.STDOUT,
      );
    except subprocess.CalledProcessError as oException:
      print "%s %s" % (oSelf.__sOpenSSLBinaryPath, " ".join(asArguments));
      print oException.output;
      raise;

  def foGetSSLContextForServerWithHostName(oSelf, sHostName):
    sKeyFilePath = os.path.join(oSelf.__sGeneratedCertificatesFolderPath, "%s.key.pem" % sHostName);
    sCertificateFilePath = os.path.join(oSelf.__sGeneratedCertificatesFolderPath, "%s.cert.pem" % sHostName);
    oSelf.oCertificateFilesLock.fAcquire();
    try:
      if not os.path.isfile(sKeyFilePath) or not os.path.isfile(sCertificateFilePath):
        return None;
    finally:
      oSelf.oCertificateFilesLock.fRelease();
    return cSSLContext.foForServerWithHostNameAndKeyAndCertificateFilePath(sHostName, sKeyFilePath, sCertificateFilePath);

  def foGenerateSSLContextForServerWithHostName(oSelf, sHostName):
    sKeyFilePath = os.path.join(oSelf.__sGeneratedCertificatesFolderPath, "%s.key.pem" % sHostName);
    sCertificateFilePath = os.path.join(oSelf.__sGeneratedCertificatesFolderPath, "%s.cert.pem" % sHostName);
    oSelf.oCertificateFilesLock.fAcquire();
    try:
      if not os.path.isfile(sKeyFilePath) or not os.path.isfile(sCertificateFilePath):
        sCertificateSigningRequestFilePath = os.path.join(oSelf.__sGeneratedCertificatesFolderPath, "%s.csr.pem" % sHostName);
        oSelf.__fExecuteOpenSSL(
          "req",
          "-config", os.path.join(oSelf.__sOpenSSLConfigFilesFolderPath, "intermediate.conf"),
          "-nodes",
          "-new",
          "-newkey", "rsa:1024",
          "-keyout", sKeyFilePath,
          "-out", sCertificateSigningRequestFilePath,
          "-subj", "/C=NL/O=SkyLined/CN=%s" % sHostName,
        );
        assert os.path.isfile(sCertificateSigningRequestFilePath), \
            "wut";
        oSelf.__fExecuteOpenSSL(
          "ca",
          "-batch",
          "-config", os.path.join(oSelf.__sOpenSSLConfigFilesFolderPath, "intermediate.conf"),
          "-extensions", "server_cert",
          "-notext",
          "-in", sCertificateSigningRequestFilePath,
          "-out", sCertificateFilePath,
        );
        assert os.path.isfile(sCertificateFilePath), \
            "wut";
        os.remove(sCertificateSigningRequestFilePath);
    finally:
      oSelf.oCertificateFilesLock.fRelease();
    return cSSLContext.foForServerWithHostNameAndKeyAndCertificateFilePath(sHostName, sKeyFilePath, sCertificateFilePath);
