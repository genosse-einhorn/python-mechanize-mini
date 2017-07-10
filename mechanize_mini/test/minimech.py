#!/usr/bin/env python3

import unittest
import os
import os.path
import urllib.parse, urllib.request, urllib.error
import multiprocessing
import time
import random
import xml.etree.ElementTree as ET

import mechanize_mini as minimech
import mechanize_mini.HtmlTree as HT

import test_server

TEST_SERVER = None
browser = minimech.Browser("MiniMech Test Suite / jonas@kuemmerlin.eu")

class BasicTest(unittest.TestCase):

    def test_simplest(self):
        test = browser.open(TEST_SERVER + '/test.html')
        self.assertEqual(test.url, TEST_SERVER + '/test.html')
        self.assertEqual(test.uri, TEST_SERVER + '/test.html')
        self.assertEqual(ET.tostring(test.document, method='text', encoding='unicode').strip(), 'Bla bla bla')

    def test_redirect_3xx(self):
        test = browser.open(TEST_SERVER + '/redirect?test.html')
        self.assertEqual(ET.tostring(test.document, method='text', encoding='unicode').strip(), 'Bla bla bla')

    def test_redirect_refresh(self):
        test = browser.open(TEST_SERVER + '/redirect-refresh?test.html')
        self.assertEqual(ET.tostring(test.document, method='text', encoding='unicode').strip(), 'Bla bla bla')

    def test_redirect_broken_refresh(self):
        test = browser.open(TEST_SERVER + '/redirect-refresh-broken')
        self.assertEqual(ET.tostring(test.document, method='text', encoding='unicode').strip(),
            'Not Redirected')

    def test_redirect_meta_refresh(self):
        test = browser.open(TEST_SERVER + '/redirect?/redirect-meta.html')
        self.assertEqual(ET.tostring(test.document, method='text', encoding='unicode').strip(), 'Bla bla bla')

    def test_too_many_redirects(self):
        with self.assertRaises(minimech.TooManyRedirectsException):
            browser.open(TEST_SERVER + '/redirect-loop')

    def test_error_return(self):
        with self.assertRaises(minimech.HTTPException) as cm:
            browser.open(TEST_SERVER + '/gimme4')

        self.assertEqual(cm.exception.code, 404)
        self.assertEqual(cm.exception.page.document.text, 'there is no content')

    def test_additional_headers(self):
        test = browser.open(TEST_SERVER + '/show-headers', additional_headers={'X-Foo': 'bar'})
        self.assertIn('X-Foo: bar', test.document.text.split('\n'))

    def test_return_headers(self):
        test = browser.open(TEST_SERVER + '/return-x-headers?bla=foo&BAR=baZ')
        self.assertEqual(test.headers['X-Bla'], 'foo')
        self.assertEqual(test.headers['x-bar'], 'baZ')

class FindStuffTest(unittest.TestCase):
    def test_find_by_tag_name(self):
        test = browser.open(TEST_SERVER + '/form.html')

        self.assertEqual(test.find('.//form').tag, 'form')

    def test_find_by_class(self):
        test = browser.open(TEST_SERVER + '/elements.html')

        # not existing
        self.assertEqual(test.find(class_name='nada'), None)

        # not so many
        self.assertEqual(test.find(class_name='important', n=10), None)

        # but the third one is ok
        self.assertNotEqual(test.find(class_name='important', n=2), None)

        # but there should be two of these
        self.assertEqual(len(test.findall('.//p', class_name='important')), 2)

    def test_find_by_id(self):
        test = browser.open(TEST_SERVER + '/elements.html')

        self.assertEqual(test.find(id='importantest').get('id'), 'importantest')

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
        self.assertIn('Referer: ' + test.url, test2.document.text.split('\n'))

        # redirects with HTTP 300x should keep referer intact
        # (not specified by W3C, but this is what every browser does)
        test3 = test.open('../redirect?/show-headers')
        self.assertIn('Referer: ' + test.url, str(test3.document.text or '').split('\n'))

        # redirects with Refresh will change referer
        # (also not specified by W3C and slightly inconsitent between browsers)
        test4 = test.open('/redirect-refresh?show-headers')
        self.assertIn('Referer: ' + TEST_SERVER + '/redirect-refresh?show-headers',
                      test4.document.text.split('\n'))

        # same thing with <meta> refresh
        test5 = test.open('/redirect-meta?show-headers')
        self.assertIn('Referer: ' + TEST_SERVER + '/redirect-meta?show-headers',
                      test5.document.text.split('\n'))

class HyperlinkTest(unittest.TestCase):
    def test_find_link(self):
        test = browser.open(TEST_SERVER + '/hyperlinks.html')

        first = test.find('.//a')
        link1 = test.find_link(n=0)
        self.assertEqual(first, link1)

        link1 = test.find_link(url='/test.html')
        self.assertEqual(first, link1)

        link1 = test.find_link(text='First Link')
        self.assertEqual(first, link1)

        # find_link ignores anchors without href
        second = test.find('.//a', n=2)
        link2 = test.find_link(n=1)
        self.assertEqual(second, link2)

        link2 = test.find_link(text='Second One')
        self.assertEqual(second, link2)

    def test_follow_link(self):
        test = browser.open(TEST_SERVER + '/hyperlinks.html')

        page = test.follow_link(text='Second One')

        self.assertEqual(page.uri, TEST_SERVER + '/test.html')

if __name__ == '__main__':
    TEST_SERVER = test_server.start_test_server()

    unittest.main()
