import sys
import os
import pkgutil
import Queue
import StringIO

try:
    from PyQt4 import QtCore, QtGui, QtWebKit, QtNetwork
except ImportError:
    from PySide import QtCore, QtGui, QtWebKit, QtNetwork


class Message():

    def __init__(self,
                 status=None, status_text=None, # response
                 method=None, url=None, # request
                 headers={}, body=None):
        self.status = status
        self.status_text = status_text

        self.method = method
        self.url = url

        self.headers = headers
        self.body = body


class Request():

    def __init__(self, message, fake_reply):
        self.message = message
        self.fake_reply = fake_reply
        self._streaming = False

    def respond(self, message=None):
        """Respond to this request with a Message.

        Set the message body to None to write the response body later
        by calling this method with a string as the message.

        When message is None, a partial response is finally closed.
        """
        if isinstance(message, Message):
            if message.body is None:
                self._streaming = True
            self.fake_reply.fake_response.emit(message)
        elif message is None:
            assert self._streaming, "not a streaming response"
            self.fake_reply.fake_response_close.emit()
        else:
            assert self._streaming, "not a streaming response"
            self.fake_reply.fake_response_write.emit(str(message))


class WebSocket():

    # create and pass this to NetworkHandler in the WebSocketBackend class

    def __init__(self, url, backend, id):
        self.url = url
        self._backend = backend
        self._id = id

    def connected(self):
        """Confirm a connection."""
        self._backend.onopen.emit(self._id)

    def send(self, data):
        """Send data over an opened connection."""
        self._backend.send_to_client(self._id, data)

    def close(self):
        """Close the connection."""
        self._backend.server_close(self._id)


class NetworkHandler():
    """A Class dealing with requests from the embedded webkit.

    Subclass it to implement your own request/websocket handlers.
    """

    # HTTP

    def request(self, request):
        """Incoming Request.

        Use request.respond(id, **data) to respond.
        """
        pass

    # WebSocket

    def connect(self, websocket):
        """Incoming WebSocket conncetion.

        Call .connected() on the provided websocket object to confirm the connection
        Call .close() to close or abort the connection.
        """
        pass

    def receive(self, websocket, data):
        """Incoming WebSocket data.

        Call .send() on the provided websocket object to send data back.
        """
        pass

    def close(self, websocket):
        """Client has closed the websocket connection."""
        pass


class AnyValue(QtCore.QObject):

    def __init__(self, value):
        self.value = value


class AsyncNetworkHandler(QtCore.QObject):
    _request   = QtCore.pyqtSignal(object)
    _connect   = QtCore.pyqtSignal(object)
    _receive   = QtCore.pyqtSignal(object, str)
    _close     = QtCore.pyqtSignal(object)

    def __init__(self, network_handler):
        super(AsyncNetworkHandler, self).__init__()
        self._nh = network_handler
        self._connect.connect(self.connect)
        self._receive.connect(self.receive)
        self._close.connect(self.close)

    # HTTP

    @QtCore.pyqtSlot(object)
    def request(self, request):
        self._nh.request(request)

    # object

    @QtCore.pyqtSlot(object)
    def connect(self, websocket):
        self._nh.connect(websocket)

    @QtCore.pyqtSlot(object, str)
    def receive(self, websocket, data):
        self._nh.receive(websocket, data)

    @QtCore.pyqtSlot(object)
    def close(self, websocket):
        self._nh.close(websocket)

class LocalDispatchNetworkAccessManager(QtNetwork.QNetworkAccessManager):
    """
    Custom NetworkAccessManager to intercept requests and dispatch them locally.
    """

    def set_network_handler(self, network_handler):
        # overwriting the ctor with new arguments is not allowed -> use a setter instead
        self.network_handler = network_handler

    def createRequest(self, operation, request, data):
        reply = None

        method = "GET" # TODO: decode operation
        url = request.url().toString()
        headers = dict((str(h),str(request.rawHeader(h))) for h in request.rawHeaderList())

        msg   = Message(method=method, url=url, headers=headers, body=data)
        reply = FakeReply(self, request, operation)
        self.network_handler.request(Request(msg, reply)) # will .set_response the FakeReply to reply
        QtCore.QTimer.singleShot(0, lambda:self.finished.emit(reply))
        return reply


class FakeReply(QtNetwork.QNetworkReply):
    """
    QNetworkReply implementation that returns a given response.
    """

    fake_response       = QtCore.pyqtSignal(object)
    fake_response_write = QtCore.pyqtSignal(object)
    fake_response_close = QtCore.pyqtSignal()

    def __init__(self, parent, request, operation):
        QtNetwork.QNetworkReply.__init__(self, parent)

        self.fake_response.connect(self._fake_response)
        self.fake_response_write.connect(self._fake_response_write)
        self.fake_response_close.connect(self._fake_response_close)

        self._streaming = False
        self._content = None
        self._offset = 0

        self.setRequest(request)
        self.setUrl(request.url())
        self.setOperation(operation)
        self.open(self.ReadOnly | self.Unbuffered)

    @QtCore.pyqtSlot(object)
    def _fake_response(self, response):
        assert isinstance(response, Message)

        # status
        self.setAttribute(QtNetwork.QNetworkRequest.HttpStatusCodeAttribute, response.status)
        self.setAttribute(QtNetwork.QNetworkRequest.HttpReasonPhraseAttribute, response.status_text)

        # headers
        for k,v in response.headers.items():
            self.setRawHeader(QtCore.QString(k), QtCore.QString(v))

        if response.body is not None:
            self._content = response.body
            self._offset = 0

            # respond immediately
            if not 'Content-Length' in response.headers:
                self.setHeader(QtNetwork.QNetworkRequest.ContentLengthHeader, QtCore.QVariant(len(self._content)))

            QtCore.QTimer.singleShot(0, lambda : self.readyRead.emit())
            QtCore.QTimer.singleShot(0, lambda : self.finished.emit())
        else:
            # streaming response, call fake_response_write and fake_response_close
            self._streaming = True
            self._content = StringIO.StringIO()

    @QtCore.pyqtSlot(object)
    def _fake_response_write(self, response):
        assert isinstance(response, basestring)
        assert self._streaming, "not a streaming response"
        self._content.write(response)
        self.readyRead.emit()

    @QtCore.pyqtSlot()
    def _fake_response_close(self):
        assert self._streaming, "not a streaming response"
        self.finished.emit()

    def abort(self):
        pass

    def bytesAvailable(self):
        if isinstance(self._content, StringIO.StringIO):
            c = self._content.getvalue()
        else:
            c = self._content

        avail = long(len(c) - self._offset + super(FakeReply, self).bytesAvailable())
        return avail

    def isSequential(self):
        return True

    def readData(self, max_size):
        if isinstance(self._content, StringIO.StringIO):
            c = self._content.getvalue()
        else:
            c = self._content

        if self._offset < len(c):
            size = min(max_size, len(c)-self._offset)
            data = c[self._offset:self._offset+size]
            self._offset += size
            return data
        else:
            return None


class WebSocketBackend(QtCore.QObject):

    # javascript websocket events fo the given connection_id
    onmessage = QtCore.pyqtSignal(int, str)
    onopen    = QtCore.pyqtSignal(int)
    onclose   = QtCore.pyqtSignal(int)

    def __init__(self, network_handler):
        super(WebSocketBackend, self).__init__()
        self._connections = {}
        self._network_handler = AsyncNetworkHandler(network_handler)

    @QtCore.pyqtSlot(str, result=int)
    def connect(self, url):
        """Create a websocket connection."""
        id = max(self._connections.keys() or [0]) + 1
        ws = WebSocket(url, self, id)
        self._connections[id] = ws
        QtCore.QTimer.singleShot(0, lambda: self._network_handler._connect.emit(ws))# ??????
        return id

    @QtCore.pyqtSlot(int)
    def client_close(self, id):
        """Close the given websocket connection, initiated from the client."""
        self._network_handler._close.emit(self._connections[id])
        del self._connections[id]

    def server_close(self, id):
        """Close the given websocket connection, initiated from the server."""
        del self._connections[id]
        self.onclose.emit(id)

    @QtCore.pyqtSlot(int, str)
    def send_to_server(self, id, data):
        """Send data on the given websocket connection to the network_handler."""
        self._network_handler._receive.emit(self._connections[id], data)

    def send_to_client(self, id, data):
        """Send data from the backend to the given websocket in the browser."""
        assert self._connections[id]
        self.onmessage.emit(id, data)


class WebkitWindow(QtGui.QMainWindow):

    @classmethod
    def run(self, handler, url="http://localhost"):
        """Open a window displaying a single webkit instance.

        handler must be an object implementing the NetworkHandler
        interface (or deriving from it).

        Navigate the webkit to url after opening it.
        """
        app = QtGui.QApplication(sys.argv)
        win = self(handler, url)
        win.show()
        sys.exit(app.exec_())

    def __init__(self, network_handler, url=None):
        self.url = url or "http://localhost"
        self.network_handler = network_handler
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
        nam.set_network_handler(self.network_handler)
        webpage.setNetworkAccessManager(nam)

        # websocket requests do not go through the custom NAM
        # -> catch them in the javascript directly
        self.websocket_backend = WebSocketBackend(self.network_handler)
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
    websocket_js = pkgutil.get_data('webkitwindow', 'websocket.js')

    def setup_local_websockets_on_frame(self, qwebframe):
        def _load_js(f=qwebframe, js=self.websocket_js, websocket_backend=self.websocket_backend):
            # without passing arguments as default keyword arguments, I get strange errors:
            #     "NameError: free variable 'self' referenced before assignment in enclosing scope"
            # which looks like sombody is trying to null all local
            # arguments at the end of my function
            f.addToJavaScriptWindowObject("_wsExt", websocket_backend)
            f.evaluateJavaScript(js)

        # TODO: 'dispose' the websocket object when the frame is gone (e.g. after reload)
        qwebframe.javaScriptWindowObjectCleared.connect(_load_js)

    def setup_local_websockets(self, qwebpage):
        qwebpage.frameCreated.connect(lambda frame: self.setup_local_websockets_on_frame(frame))
