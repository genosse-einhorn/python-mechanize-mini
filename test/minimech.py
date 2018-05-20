#!/usr/bin/env python3

import unittest
import os
import os.path
import urllib.parse, urllib.request, urllib.error
import multiprocessing
import time
import random

import mechanize_mini as minimech

import test_server

TEST_SERVER = None
browser = minimech.Browser("MiniMech Test Suite / jonas@kuemmerlin.eu")

class BasicTest(unittest.TestCase):

    def test_simplest(self):
        test = browser.open(TEST_SERVER + '/test.html')
        self.assertEqual(test.url, TEST_SERVER + '/test.html')
        self.assertEqual(test.uri, TEST_SERVER + '/test.html')
        self.assertEqual(test.document_element.text_content, 'Bla bla bla')
        self.assertEqual(test.browser, browser)

    def test_redirect_3xx(self):
        test = browser.open(TEST_SERVER + '/redirect?test.html')
        self.assertEqual(test.document_element.text_content, 'Bla bla bla')

    def test_redirect_refresh(self):
        test = browser.open(TEST_SERVER + '/redirect-refresh?test.html')
        self.assertEqual(test.document_element.text_content, 'Bla bla bla')

    def test_redirect_broken_refresh(self):
        test = browser.open(TEST_SERVER + '/redirect-refresh-broken')
        self.assertEqual(test.document_element.text_content,
            'Not Redirected')

    def test_redirect_meta_refresh(self):
        test = browser.open(TEST_SERVER + '/redirect?/redirect-meta.html')
        self.assertEqual(test.document_element.text_content, 'Bla bla bla')

    def test_too_many_redirects(self):
        with self.assertRaises(minimech.TooManyRedirectsException):
            browser.open(TEST_SERVER + '/redirect-loop')

    def test_error_return(self):
        with self.assertRaises(minimech.HTTPException) as cm:
            browser.open(TEST_SERVER + '/gimme4')

        self.assertEqual(cm.exception.code, 404)
        self.assertEqual(cm.exception.document.document_element.text, 'there is no content')

    def test_additional_headers(self):
        test = browser.open(TEST_SERVER + '/show-headers', additional_headers={'X-Foo': 'bar'})
        self.assertIn('X-Foo: bar', test.document_element.text.split('\n'))

    def test_return_headers(self):
        test = browser.open(TEST_SERVER + '/return-x-headers?bla=foo&BAR=baZ')
        self.assertEqual(test.headers['X-Bla'], 'foo')
        self.assertEqual(test.headers['x-bar'], 'baZ')

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
        self.assertIn('Referer: ' + test.url, test2.document_element.text.split('\n'))

        # redirects with HTTP 300x should keep referer intact
        # (not specified by W3C, but this is what every browser does)
        test3 = test.open('../redirect?/show-headers')
        self.assertIn('Referer: ' + test.url, str(test3.document_element.text or '').split('\n'))

        # redirects with Refresh will change referer
        # (also not specified by W3C and slightly inconsitent between browsers)
        test4 = test.open('/redirect-refresh?show-headers')
        self.assertIn('Referer: ' + TEST_SERVER + '/redirect-refresh?show-headers',
                      test4.document_element.text.split('\n'))

        # same thing with <meta> refresh
        test5 = test.open('/redirect-meta?show-headers')
        self.assertIn('Referer: ' + TEST_SERVER + '/redirect-meta?show-headers',
                      test5.document_element.text.split('\n'))

class HyperlinkTest(unittest.TestCase):
    def test_follow_link(self):
        test = browser.open(TEST_SERVER + '/hyperlinks.html')

        page = test.query_selector('a:contains(Second One)').follow()
        page2 = test.query_selector('a').click()

        self.assertEqual(page.uri, TEST_SERVER + '/test.html')
        self.assertEqual(page2.uri, TEST_SERVER + '/test.html')

    def test_synthesized_link(self):
        test = browser.open(TEST_SERVER + '/hyperlinks.html')

        link = test.create_element('a', {'href': 'test.html'})
        page = link.follow()

        self.assertEqual(page.uri, TEST_SERVER + '/test.html')

if __name__ == '__main__':
    TEST_SERVER = test_server.start_test_server()

    unittest.main()
