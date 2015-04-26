Webkitwindow
============

An easy to use Python wrapper around QtWebkit, BSD Licenced.

Why?
----

Couldn't find an existing solution that would suit my needs:

- must support websockets
- do not use the network for HTTP and WebSocket requests but call Python methods directly
- the API must not assume knowledge of PyQt or leak PyQt internals
- do not assume any particular backend programming style (channels, thread, asyncio, ...)
- minimal dependencies (just PyQt)
- thread safe

Setup
-----

Install PyQt4 (e.g. `apt-get install python-qt4`) or PySide (e.g. `apt-get install python-pyside`).
Clone this repository, then `python setup.py install`.

Example
-------

    from webkitwindow import WebkitWindow, Message

    class ExampleHandler():

        def startup(self, window):
            self.window = window

        def request(self, req):
            if req.url_path == '/close':
                self.window.close()
            else:
                html = ('<h1>Hello Webkit</h1>'
                        '<form action="close" method="post">'
                        '<input type="submit" value="Close">'
                        '</form>')
                req.found(html, 'text/html')

    def main():
        WebkitWindow.run(ExampleHandler())

    if __name__ == '__main__':
        main()

Licence
-------

BSD, though using webkitwindow may result in having to accept GPL as PyQt4 is GPL licensed