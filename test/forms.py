#!/usr/bin/env python3

import unittest

import mechanize_mini as minimech
from mechanize_mini.forms import Form

import test_server

TEST_SERVER = None

browser = minimech.Browser('MiniMech test suite / jonas@kuemmerlin.eu')
class FormAccessorTest(unittest.TestCase):
    def test_defaults(self):
        page = browser.open(TEST_SERVER + '/form.html')
        form = Form(next(page.document.iter('form')), page)

        # neither name and id are set on the form
        self.assertEqual(form.name, None)
        self.assertEqual(form.id, None)

        # the rest are defaults
        self.assertEqual(form.method, 'GET')
        self.assertEqual(form.action, page.url)
        self.assertEqual(form.enctype, 'application/x-www-form-urlencoded')

    def test_nondefaults(self):
        page = browser.open(TEST_SERVER + '/form.html')
        form = Form(list(page.document.iter('form'))[1], page)

        self.assertEqual(form.name, 'withaction')
        self.assertEqual(form.id, 'actionwith')
        self.assertEqual(form.method, 'POST')
        self.assertEqual(form.action, TEST_SERVER + '/show-post-params')

    def test_input_getvalue(self):
        page = browser.open(TEST_SERVER + '/form.html')
        form = Form(list(page.document.iter('form'))[1], page)

        self.assertEqual(form.get_value('foo'), 'bar')
        self.assertEqual(form.get_value('checker'), None)
        self.assertEqual(form.get_value('longtext'), 'Loltext')
        self.assertEqual(form.get_value('nonexistent'), None)


    def test_input_setvalue(self):
        page = browser.open(TEST_SERVER + '/form.html')
        form = Form(list(page.document.iter('form'))[1], page)

        foo = next(x for x in page.find_all_elements(context=form.element) if x.get('name') == 'foo')
        form.set_value('foo', 'baz')
        self.assertEqual(foo.get('value'), 'baz')

        # <select>

        # set option with text
        form.set_value('checker', 'Text is Value')
        self.assertEqual(form.get_value('checker'), 'Text is Value')
        self.assertEqual(page.find_element(tag='option', text='Text is Value').get('selected'), 'selected')

        # set option with custom value
        form.set_value('checker', 'theval')
        self.assertEqual(form.get_value('checker'), 'theval')
        self.assertEqual(page.find_element(id='val1').get('selected'), 'selected')

        # set nonexistent option
        with self.assertRaises(minimech.forms.InvalidOptionError) as cm:
            form.set_value('checker', 'bogus')
        self.assertEqual(cm.exception.select.tag, 'select')
        self.assertEqual(cm.exception.value, 'bogus')

        # nonexistent elements
        with self.assertRaises(minimech.forms.InputNotFoundError):
            form.set_value('nonexistent', 'bla')

        # textarea
        txa = page.find_element(tag='textarea', context=form.element)
        form.set_value('longtext', 'blabla')
        self.assertEqual(txa.text, 'blabla')

if __name__ == '__main__':
    TEST_SERVER = test_server.start_test_server()

    unittest.main()
