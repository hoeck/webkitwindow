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
    function webSocketTest() {
        ws = new WebSocket("ws://echo.websocket.org");
        ws.onopen = function() { document.write("websocket opened"); ws.send("echo"); };
        ws.onmessage = function(m) { document.write("websocket message" + m.data) };
    };

    document.onreadystatechange = function() {
        console.log("readyState", document.readyState);
        if (document.readyState == "complete") {
            var el = document.createElement("DIV")
            el.innerHTML = "foo is " + window.foo;
            console.log("el", el);
            document.body.appendChild(el);

            t.foobar.connect(function(args) { console.log("fooabr-triggered", args); });
            t.trigger();
        }
    }
    </script>

    <a href="foo">click%s</a>
    %s
    </body></html>""" % (datetime.datetime.now(), ','.join(map(str, range(2)))))

        return response
    else:
        return None

def example_websocket_dispatch():
    pass

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
        # my version of qtwebkit seems to expect to always the get the
        # full content length, not the length of the remaining
        # content!
        # maybe im misunderstanding the docs or isSequential is not working.
        return len(self.content)

        # normal implementation of this method would be:
        # return len(self.content) - self.offset

    def isSequential(self):
        return True

    def readData(self, max_size):
        if self.offset < len(self.content):
            end = min(self.offset + max_size, len(self.content))
            data = self.content[self.offset:end]
            self.offset = end
            return data


class TestJs(QtCore.QObject):

    sig = QtCore.pyqtSignal(str, name="foobar")

    @QtCore.pyqtSlot(str, result=str)
    def tm(self, *args):
        print "xxx", args
        return "BAR"

    @QtCore.pyqtSlot()
    def trigger(self):
        self.sig.emit('triggered')

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

        self.setup_local_websockets(webpage)
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

    ### Capturing Websocket Connections

    # For WebSockets, QtWebKit does not use the
    # QNetworkAccessManager. Thus we 'intercept' WebSocket connection
    # attempts by adding our own implementation of the WebSocket
    # interface to the javascript window context of each new frame.

    websocket_js = """
    window.WebSocket = function(url) {
        var self = this;

        self.onopen = undefined;
        self.onmessage = undefined;

        // TODO
    }
    window.foo = new Date(); // test
    """

    def setup_local_websockets_on_frame(self, qwebframe):
        def _load_js(f=qwebframe, js=self.websocket_js):
            # without passing arguments as default keyword arguments, I get strange errors:
            #     "NameError: free variable 'self' referenced before assignment in enclosing scope"
            # which looks like sombody is trying to null all local
            # arguments at the end of my function
            f.addToJavaScriptWindowObject("t", TestJs())
            f.evaluateJavaScript(js)

        qwebframe.javaScriptWindowObjectCleared.connect(_load_js)

    def setup_local_websockets(self, qwebpage):
        qwebpage.frameCreated.connect(lambda frame: self.setup_local_websockets_on_frame(frame))

if __name__ == '__main__':
    # start up qt
    app = QtGui.QApplication(sys.argv)
    win = WebkitWindow("http://foo", example_dispatch_fn)
    win.show()
    sys.exit(app.exec_())
