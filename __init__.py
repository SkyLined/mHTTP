import os, sys;

# Augment the search path: look in main folder, parent folder or "modules" child folder, in that order.
sMainFolderPath = os.path.dirname(os.path.abspath(__file__));
sParentFolderPath = os.path.normpath(os.path.join(sMainFolderPath, ".."));
sModulesFolderPath = os.path.join(sMainFolderPath, "modules");
asOriginalSysPath = sys.path[:];
sys.path = [sMainFolderPath, sParentFolderPath, sModulesFolderPath] + sys.path;

# Load external dependecies to make sure they are available and shown an error
# if any one fails to load. This error explains where the missing component
# can be downloaded to fix the error.
for (sModuleName, sDownloadURL) in [
  ("mDebugOutput", "https://github.com/SkyLined/mDebugOutput/"),
  ("mMultiThreading", "https://github.com/SkyLined/mMultiThreading/"),
]:
  try:
    __import__(sModuleName, globals(), locals(), [], -1);
  except ImportError as oError:
    if oError.message == "No module named %s" % sModuleName:
      print "*" * 80;
      print "oConsole depends on %s which you can download at:" % sModuleName;
      print "    %s" % sDownloadURL;
      print "After downloading, please save the code in this folder:";
      print "    %s" % os.path.join(sModulesFolderPath, sModuleName);
      print " - or -";
      print "    %s" % os.path.join(sParentFolderPath, sModuleName);
      print "Once you have completed these steps, please try again.";
      print "*" * 80;
    raise;

# Restore the search path
sys.path = asOriginalSysPath;

from .cBufferedSocket import cBufferedSocket;
from .cCertificateAuthority import cCertificateAuthority;
from .cCertificateStore import cCertificateStore;
from .cHTTPClient import cHTTPClient;
from .cHTTPClientProxyServer import cHTTPClientProxyServer;
from .cHTTPClientUsingProxyServer import cHTTPClientUsingProxyServer;
from .cHTTPConnection import cHTTPConnection;
from .cHTTPRequest import cHTTPRequest;
from .cHTTPResponse import cHTTPResponse;
from .cHTTPServer import cHTTPServer;
from .cURL import cURL;
from .fdsURLDecodedNameValuePairsFromString import fdsURLDecodedNameValuePairsFromString;
from .fsURLEncodedStringFromNameValuePairs import fsURLEncodedStringFromNameValuePairs;from .fsGetMediaTypeForExtension import fsGetMediaTypeForExtension;