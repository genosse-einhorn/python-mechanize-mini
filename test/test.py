#!/usr/bin/env python3

import unittest
import os
import os.path
import http.server
import urllib.parse, urllib.request, urllib.error
import multiprocessing
import time
import random

import mechanize_mini as minimech

# test http server

class TestHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # For our custom redirect handlers
        if self.path.startswith('/redirect?'):
            target = urllib.parse.unquote(self.path.split('?')[-1])

            self.send_response(302)
            self.send_header('Location', target)
            self.end_headers()
        elif self.path.startswith('/redirect-refresh?'):
            target = urllib.parse.unquote(self.path.split('?')[-1])

            self.send_response(200)
            self.send_header('Refresh', '0; '+target)
            self.end_headers()
        elif self.path.startswith('/redirect-loop'):
            self.send_response(302)
            self.send_header('Location', '/redirect-loop/{0}'.format(random.randint(0,1000)))
            self.end_headers()
        else:
            super().do_GET()

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


PORT = 23527

def run_server():
    server_address = ('', PORT)
    httpd = http.server.HTTPServer(server_address, TestHTTPRequestHandler)
    httpd.serve_forever()

def run_test_server():
    p = multiprocessing.Process(target=run_server, daemon=True)
    p.start()


TEST_SERVER = 'http://localhost:{port}'.format(port=PORT)
browser = minimech.Browser("MiniMech Test Suite / jonas@kuemmerlin.eu")

class BasicTest(unittest.TestCase):

    def test_simplest(self):
        test = browser.open(TEST_SERVER + '/test.html')
        self.assertEqual(test.document.getroot().text_content().strip(), 'Bla bla bla')

    def test_redirect_3xx(self):
        test = browser.open(TEST_SERVER + '/redirect?test.html')
        self.assertEqual(test.document.getroot().text_content().strip(), 'Bla bla bla')

    def test_redirect_refresh(self):
        test = browser.open(TEST_SERVER + '/redirect-refresh?test.html')
        self.assertEqual(test.document.getroot().text_content().strip(), 'Bla bla bla')

    def test_redirect_meta_refresh(self):
        test = browser.open(TEST_SERVER + '/redirect?/redirect-meta.html')
        self.assertEqual(test.document.getroot().text_content().strip(), 'Bla bla bla')

    def test_too_many_redirects(self):
        with self.assertRaises(minimech.TooManyRedirectsException):
            browser.open(TEST_SERVER + '/redirect-loop')


if __name__ == '__main__':
    run_test_server()

    # wait for server to come online
    while 1:
        try:
            resp = urllib.request.urlopen(TEST_SERVER + '/')
            break
        except urllib.error.URLError:
            time.sleep(0.01)

    unittest.main()
