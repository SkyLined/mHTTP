from mDebugOutput import fDebugOutput;
import mHTTP;

def fTestURL():
  mHTTP.cURL.foFromString("http://0.1.2.3:12345/path?query#hash");
  mHTTP.cURL.foFromString("https://[0:1:2:3:4:5:6:7]:12345/path?query#hash");
  mHTTP.cURL.foFromString("http://host/path?query#hash");
  mHTTP.cURL.foFromString("http://a.b-c.1.host.domain/path?query#hash");
