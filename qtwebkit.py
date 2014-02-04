import sys
import os

try:
    from PyQt4 import QtCore, QtGui, QtWebKit, QtNetwork
except ImportError:
    from PySide import QtCore, QtGui, QtWebKit, QtNetwork


def example_dispatch_fn(method, url, headers, data):
    if 'foo' in url:
        import datetime
        response = Response(status="200",
                                status_text="found",
                                body="""<html><head></head><body>

    <script type="text/javascript">
    ws = new WebSocket("ws://echo.websocket.org");
    ws.onopen = function() { document.write("websocket opened"); ws.send("echo"); };
                                ws.onmessage = function(m) { document.write("websocket message" + m.data) };
    </script>

    <a href="foo">click%s</a>
    %s
    </body></html>""" % (datetime.datetime.now(), ','.join(map(str, range(2)))))

        return response
    else:
        return None

class Response():

    def __init__(self, status="200", status_text="", headers={}, body=""):
        self.status = status
        self.status_text = status_text
        self.headers = headers
        self.body = body


class LocalDispatchNetworkAccessManager(QtNetwork.QNetworkAccessManager):
    """
    Custom NetworkAccessManager to intercept requests and dispatch them locally.
    """

    def set_request_dispatch_function(self, request_dispatch_function):
        # overwriting the ctor with new arguments is not allowed -> use a setter instead
        self.request_dispatch_function = request_dispatch_function

    def createRequest(self, operation, request, data):
        reply = None

        method = "GET" # TODO: decode operation
        url = request.url().toString()
        headers = dict((str(h),str(request.rawHeader(h))) for h in request.rawHeaderList())

        response = self.request_dispatch_function(method, url, headers, data)
        if not response:
            # real network request:
            reply = QtNetwork.QNetworkAccessManager.createRequest(self, operation, request, data)
        else:
            reply = FakeReply(self, request, operation, response)
            QtCore.QTimer.singleShot(0, lambda:self.finished.emit(reply))

        return reply


class FakeReply(QtNetwork.QNetworkReply):
    """
    QNetworkReply implementation that returns a given response.
    """
    def __init__(self, parent, request, operation, response):
        QtNetwork.QNetworkReply.__init__(self, parent)
        self.setRequest(request)
        self.setUrl(request.url())
        self.setOperation(operation)
        self.open(self.ReadOnly | self.Unbuffered)

        self.content = response.body
        self.offset = 0

        for k,v in response.headers.items():
            self.setRawHeader(QtCore.QString(k), QtCore.QString(v))

        if not 'Content-Length' in response.headers:
            self.setHeader(QtNetwork.QNetworkRequest.ContentLengthHeader, QtCore.QVariant(len(self.content)))

        # status
        self.setAttribute(QtNetwork.QNetworkRequest.HttpStatusCodeAttribute, response.status)
        self.setAttribute(request.HttpReasonPhraseAttribute, response.status_text)

        QtCore.QTimer.singleShot(0, lambda : self.readyRead.emit())
        QtCore.QTimer.singleShot(0, lambda : self.finished.emit())

    def abort(self):
        pass

    def bytesAvailable(self):
        # hack:
        # my version of qtwebkit does not read replies smaller than
        # 512 Bytes properly, unless this method always returns the
        # full size, even when everything has already been read.
        if len(self.content) <= 512:
            return len(self.content)
        else:
            return len(self.content) - self.offset

    def isSequential(self):
        return True

    def readData(self, maxSize):
        if self.offset < len(self.content):
            end = min(self.offset + maxSize, len(self.content))
            data = self.content[self.offset:end]
            self.offset = end
            return data


class WebkitWindow(QtGui.QMainWindow):

    def __init__(self, url=None, request_dispatch_function=None):
        self.url = url or "http://localhost"
        self.request_dispatch_function = request_dispatch_function or (lambda method, url, headers, data: None)
        QtGui.QMainWindow.__init__(self)
        self.setup()

    def setup(self):
        centralwidget = QtGui.QWidget()
        centralwidget.setObjectName("centralwidget")
        horizontalLayout = QtGui.QHBoxLayout(centralwidget)
        horizontalLayout.setObjectName("horizontalLayout")
        webView = QtWebKit.QWebView(centralwidget)
        webView.setObjectName("webView")
        webpage = QtWebKit.QWebPage()

        # set the custom NAM
        nam = LocalDispatchNetworkAccessManager()
        nam.set_request_dispatch_function(self.request_dispatch_function)
        webpage.setNetworkAccessManager(nam)

        webView.setPage(webpage)
        horizontalLayout.addWidget(webView)
        horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(centralwidget)

        webView.setUrl(QtCore.QUrl(self.url))

        # setup webkit
        gs = QtWebKit.QWebSettings.globalSettings()
        gs.setAttribute(QtWebKit.QWebSettings.PluginsEnabled, True)
        gs.setAttribute(QtWebKit.QWebSettings.JavascriptEnabled, True)
        gs.setAttribute(QtWebKit.QWebSettings.AutoLoadImages, True)
        gs.setAttribute(QtWebKit.QWebSettings.JavascriptCanOpenWindows, True)
        gs.setAttribute(QtWebKit.QWebSettings.DeveloperExtrasEnabled, True)
        gs.setAttribute(QtWebKit.QWebSettings.LocalContentCanAccessRemoteUrls, True)

        # setup app details
        QtGui.QApplication.setApplicationName("Panel")
        QtGui.QApplication.setOrganizationName("Panel")

if __name__ == '__main__':
    # start up qt
    app = QtGui.QApplication(sys.argv)
    win = WebkitWindow("http://foo", example_dispatch_fn)
    win.show()
    sys.exit(app.exec_())
