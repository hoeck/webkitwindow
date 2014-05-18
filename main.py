import webkitwindow


import datetime
def rrr():
    return dict(status="200",
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

            //t.foobar.connect(function(args) { console.log("fooabr-triggered", args); });
            //t.trigger();
            webSocketTest();
        }
    }
    </script>

    <a href="foo">click%s</a>
    %s
    </body></html>""" % (datetime.datetime.now(), ','.join(map(str, range(2)))))


import threading
import time

def xxx(req):
    print "Threaded Response"
    for x in range(50):
        time.sleep(0.2)
        print "foo %s\n" % x
        req.respond("foo %s %s\n" % ('x'*256, x))
    req.respond() # close


class ExampleHandler():

    # HTTP

    def request(self, req):
        if 0:
            # immediate
            req.respond(webkitwindow.Message(**rrr()))

        if 1:
            # streaming
            req.respond(webkitwindow.Message(status="200",
                                             status_text="found",
                                             body=None))
            t = threading.Thread(target=lambda : xxx(req))
            t.start()
            print "thread started"

    # WebSocket

    def connect(self, websocket):
        print "Websocket Connect", websocket
        websocket.connected()

    def receive(self, websocket, data):
        print "Websocket recv", websocket, data
        websocket.send('my'+data) # echo

    def close(self, websocket):
        print "Websocket closed", websocket


def main():
    webkitwindow.WebkitWindow.run(ExampleHandler(), "http://foo")

if __name__ == '__main__':
    main()
