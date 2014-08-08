"""nosetests for webkitwindow."""

import time
import threading
import nose.tools as ntools

import webkitwindow

def close_when_done(handler, win):
    if getattr(handler, 'done', False):
        win.close()
    else:
        handler.run_later(lambda: close_when_done(handler, win), timeout=1000)

def test_startup():
    """Ensure that the webkitwindow runs and can be closed."""

    class Handler(webkitwindow.NetworkHandler):

        def startup(self, win):
            ntools.assert_is_instance(win, webkitwindow.WebkitWindow)
            win.close()

    webkitwindow.WebkitWindow.run(Handler(), exit=False)

def test_load_html():
    """Ensure the webkitwindow requests html."""

    test_url = "http://foo.bar/index.html?query=1"

    class Handler(webkitwindow.NetworkHandler):

        def startup(self, win):
            close_when_done(self, win)

        def request(self, request):
            try:
                ntools.assert_is_instance(request, webkitwindow.Request)
                ntools.assert_equal(request.method, 'GET')
                ntools.assert_equal(request.url, test_url)

                msg = webkitwindow.Message(
                    headers={'Content-Type': 'text/html'},
                    body="<html><head></head><body><h1>test</h1></body></html>"
                )
                request.respond(200, msg)
            finally:
                self.done = True

    webkitwindow.WebkitWindow.run(Handler(), url=test_url, exit=False)

def test_load_request_methods():
    """Test the different request methods."""

    script = """
post = function() {
  var http = new XMLHttpRequest(),
      url = "test_post",
      data = "postdata",
      el;
  http.open("POST", url, true);
  http.setRequestHeader("Content-type", "text/plain");
  http.setRequestHeader("Content-length", data.length);
  http.setRequestHeader("Connection", "close");
  http.onreadystatechange = function() {
    if (http.readyState == 4) {
      el = document.createElement('h2');
      el.textContent = "post test response:" + http.responseText;
      document.body.appendChild(el);
    }
  };
  http.send(data);
};

document.onreadystatechange = function() {
  if (document.readyState != "complete") {
    return;
  }

  post();
};
    """

    html = """
<html>
  <head>
    <script type="text/javascript" src="script.js"></script>
  </head>
  <body>
    <h1>request method test</h1>
  </body>
</html>
    """

    class Handler(webkitwindow.NetworkHandler):

        def startup(self, win):
            self.win = win
            self.win.run_later(lambda : self.win.close(), timeout=1000)

        def request(self, request):
            try:
                if request.method == 'GET':
                    if request.url_path == '/script.js':
                        msg = webkitwindow.Message(headers={'Content-Type': 'text/javascript'},
                                                   body=script)
                    elif request.url_path == '/':
                        msg = webkitwindow.Message(headers={'Content-Type': 'text/html'},
                                                   body=html)
                    else:
                        assert False, "unexpected path: %s" % (request.url_path, )
                elif request.method == 'POST':
                    msg = webkitwindow.Message({'Content-Type': 'text/plain'},
                                               body='sucess!!!')

                request.respond(200, msg)
            finally:
                self.done = True

    webkitwindow.WebkitWindow.run(Handler(), url="http://localhost", exit=False)
