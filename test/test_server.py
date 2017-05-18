import http.server
import urllib.parse, urllib.request, urllib.error
import multiprocessing
import os.path
import random
import cgi

# test http server

class TestHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # For our custom redirect handlers
        if self.path.startswith('/redirect?'):
            target = urllib.parse.unquote(self.path.split('?')[-1])

            self.send_response(302)
            self.send_header('Location', target)
            self.end_headers()
        elif self.path.startswith('/redirect-refresh-broken'):
            self.send_response(200)
            # bogus refresh header is ignored
            self.send_header('Refresh', 'dumm-dumm; url=')
            self.end_headers()
            self.wfile.write('Not Redirected\n'.encode('utf8'))
        elif self.path.startswith('/redirect-refresh?'):
            target = urllib.parse.unquote(self.path.split('?')[-1])

            self.send_response(200)
            self.send_header('Refresh', '0; url='+target)
            self.end_headers()
        elif self.path.startswith('/redirect-meta?'):
            target = urllib.parse.unquote(self.path.split('?')[-1])

            self.send_response(200)
            self.end_headers();

            self.wfile.write('<meta http-equiv=REFRESH content="0;uRl={0}" />\n'
                .format(target).encode('utf-8'))
        elif self.path.startswith('/redirect-loop'):
            self.send_response(302)
            self.send_header('Location', '/redirect-loop/{0}'.format(random.randint(0,1000)))
            self.end_headers()
        elif self.path.startswith('/gimme4'):
            self.send_response(404)
            self.end_headers()
            self.wfile.write('there is no content'.encode('utf8'))
        elif self.path.startswith('/show-headers'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=UTF-8')
            self.end_headers()

            for key, val in self.headers.items():
                self.wfile.write('{0}: {1}\n'.format(key, val).encode('utf-8'))
        elif self.path.startswith('/show-params?'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=UTF-8')
            self.end_headers()

            paramstr = self.path.split('?', 2)[-1]
            params = cgi.parse_qsl(paramstr)

            for name,val in params:
                self.wfile.write('{0}={1}\n'.format(name, val).encode('UTF-8'))
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/show-post-params':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=UTF-8')
            self.end_headers()

            paramstr = self.rfile.read(int(self.headers['Content-Length'])).decode('ascii')
            params = cgi.parse_qsl(paramstr)

            for name,val in params:
                self.wfile.write('{0}={1}\n'.format(name, val).encode('UTF-8'))
        else:
            self.send_response(404)


    # custom path translator
    def translate_path(self, path):
        # abandon query parameters
        path = path.split('?',1)[0]
        path = path.split('#',1)[0]

        # unquote
        path = urllib.parse.unquote(path)

        # return file path
        path = os.path.dirname(os.path.abspath(__file__)) + '/files' + path
        return path

    # get rid of logging
    def log_message(self, format, *args):
        return

def run_server(q):
    server_address = ('127.0.0.1', 0)
    httpd = http.server.HTTPServer(server_address, TestHTTPRequestHandler)
    q.put(httpd.socket.getsockname()[1])
    httpd.serve_forever()

def start_test_server() -> str:
    q = multiprocessing.Queue()

    p = multiprocessing.Process(target=run_server, args=(q,), daemon=True)
    p.start()
    server = 'http://127.0.0.1:{port}'.format(port=q.get())

    # wait for server to come online
    while 1:
        try:
            resp = urllib.request.urlopen(server + '/')
            break
        except urllib.error.URLError:
            time.sleep(0.01)

    return server

