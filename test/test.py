#!/usr/bin/env python3

import unittest
import os
import os.path
import http.server
import urllib.parse, urllib.request, urllib.error
import multiprocessing
import time
import random
import xml.etree.ElementTree as ET

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
        self.assertEqual(test.url, TEST_SERVER + '/test.html')
        self.assertEqual(test.uri, TEST_SERVER + '/test.html')
        self.assertEqual(ET.tostring(test.document.getroot(), method='text', encoding='unicode').strip(), 'Bla bla bla')

    def test_redirect_3xx(self):
        test = browser.open(TEST_SERVER + '/redirect?test.html')
        self.assertEqual(ET.tostring(test.document.getroot(), method='text', encoding='unicode').strip(), 'Bla bla bla')

    def test_redirect_refresh(self):
        test = browser.open(TEST_SERVER + '/redirect-refresh?test.html')
        self.assertEqual(ET.tostring(test.document.getroot(), method='text', encoding='unicode').strip(), 'Bla bla bla')

    def test_redirect_meta_refresh(self):
        test = browser.open(TEST_SERVER + '/redirect?/redirect-meta.html')
        self.assertEqual(ET.tostring(test.document.getroot(), method='text', encoding='unicode').strip(), 'Bla bla bla')

    def test_too_many_redirects(self):
        with self.assertRaises(minimech.TooManyRedirectsException):
            browser.open(TEST_SERVER + '/redirect-loop')

    def test_error_return(self):
        with self.assertRaises(minimech.HTTPException) as cm:
            browser.open(TEST_SERVER + '/gimme4')

        self.assertEqual(cm.exception.code, 404)
        self.assertEqual(cm.exception.page.document.getroot().text, 'there is no content')

    def test_additional_headers(self):
        test = browser.open(TEST_SERVER + '/show-headers', additional_headers={'X-Foo': 'bar'})
        self.assertIn('X-Foo: bar', test.document.getroot().text.split('\n'))

class BaseUriTest(unittest.TestCase):
    def test_implicit(self):
        # in the simplest case where no <base> tag is present
        test = browser.open(TEST_SERVER + '/test.html')
        self.assertEqual(test.baseuri, test.base)
        self.assertEqual(test.baseuri, TEST_SERVER + '/test.html')

    def test_fragment(self):
        # base uri never contains fragments
        test = browser.open(TEST_SERVER + '/test.html#blabla')
        self.assertEqual(test.baseuri, TEST_SERVER + '/test.html')

    def test_absolute_base(self):
        test = browser.open(TEST_SERVER + '/base/absolute.html')
        self.assertEqual(test.baseuri, test.base)
        self.assertEqual(test.baseuri, 'http://example.com/')

    def test_relative_base(self):
        test = browser.open(TEST_SERVER + '/base/relative.html')
        self.assertEqual(test.baseuri, test.base)
        self.assertEqual(test.baseuri, TEST_SERVER + '/otherdir/')

class PageOpenTest(unittest.TestCase):
    def test_absolute(self):
        test = browser.open(TEST_SERVER + '/test.html')
        test2 = test.open(TEST_SERVER + '/empty.html')
        self.assertEqual(test2.url, TEST_SERVER + '/empty.html')

    def test_implicit(self):
        test = browser.open(TEST_SERVER + '/test.html')
        test2 = test.open('empty.html')
        self.assertEqual(test2.url, TEST_SERVER + '/empty.html')

    def test_fragment(self):
        # base uri never contains fragments
        test = browser.open(TEST_SERVER + '/empty.html')
        test = test.open('test.html#blabla')
        self.assertEqual(test.uri, TEST_SERVER + '/test.html#blabla')

    def test_relative_base(self):
        test = browser.open(TEST_SERVER + '/base/relative.html')
        test = test.open('../empty.html')
        self.assertEqual(test.url, TEST_SERVER + '/empty.html')

    def test_referer(self):
        test = browser.open(TEST_SERVER + '/base/relative.html')
        test2 = test.open('../show-headers')
        self.assertIn('Referer: ' + test.url, test2.document.getroot().text.split('\n'))

        # redirects with HTTP 300x should keep referer intact
        # (not specified by W3C, but this is what every browser does)
        test3 = test.open('../redirect?/show-headers')
        self.assertIn('Referer: ' + test.url, str(test3.document.getroot().text or '').split('\n'))

        # redirects with Refresh will change referer
        # (also not specified by W3C and slightly inconsitent between browsers)
        test4 = test.open('/redirect-refresh?show-headers')
        self.assertIn('Referer: ' + TEST_SERVER + '/redirect-refresh?empty.html',
                      test4.document.getroot().text.split('\n'))

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
