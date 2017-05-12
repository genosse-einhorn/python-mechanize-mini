#!/usr/bin/env python3

import unittest
import xml.etree.ElementTree as ET

import mechanize_mini as minimech
import mechanize_mini.HtmlTree as HT
from mechanize_mini.HtmlTree import HTML
from mechanize_mini.forms import Form, Input, UnsupportedFormError, InvalidOptionError, InputNotFoundError

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

        self.assertEqual(form.get_field('foo'), 'bar')
        self.assertEqual(form.get_field('checker'), None)
        self.assertEqual(form.get_field('longtext'), 'Loltext')
        self.assertEqual(form.get_field('nonexistent'), None)


    def test_input_setvalue(self):
        page = browser.open(TEST_SERVER + '/form.html')
        form = Form(list(page.document.iter('form'))[1], page)

        foo = next(x for x in page.find_all_elements(context=form.element) if x.get('name') == 'foo')
        form.set_field('foo', 'baz')
        self.assertEqual(foo.get('value'), 'baz')

        # <select>

        # set option with text
        form.set_field('checker', 'Text is Value')
        self.assertEqual(form.get_field('checker'), 'Text is Value')
        self.assertEqual(page.find_element(tag='option', text='Text is Value').get('selected'), 'selected')

        # set option with custom value
        form.set_field('checker', 'theval')
        self.assertEqual(form.get_field('checker'), 'theval')
        self.assertEqual(page.find_element(id='val1').get('selected'), 'selected')

        # set nonexistent option
        with self.assertRaises(minimech.forms.InvalidOptionError) as cm:
            form.set_field('checker', 'bogus')
        self.assertEqual(cm.exception.select.tag, 'select')
        self.assertEqual(cm.exception.value, 'bogus')

        # nonexistent elements
        with self.assertRaises(minimech.forms.InputNotFoundError):
            form.set_field('nonexistent', 'bla')

        # textarea
        txa = page.find_element(tag='textarea', context=form.element)
        form.set_field('longtext', 'blabla')
        self.assertEqual(txa.text, 'blabla')

class InputTest(unittest.TestCase):
    def test_construct(self):
        el = HTML('<input>')
        i = Input(el)
        self.assertEqual(i.element, el)

        el = HTML('<textarea>')
        i = Input(el)
        self.assertEqual(i.element, el)

        el = HTML('<select>')
        i = Input(el)
        self.assertEqual(i.element, el)

        with self.assertRaises(UnsupportedFormError):
            el = HTML('<p>')
            i = Input(el)


    def test_id(self):
        el = ET.Element('input', {})
        i = Input(el)

        self.assertEqual(i.id, None)

        i.id = 'someid'
        self.assertEqual(el.get('id'), 'someid')
        self.assertEqual(i.id, 'someid')

        el = ET.Element('input', {'id': 'bla'})
        i = Input(el)
        self.assertEqual(i.id, 'bla')

    def test_name(self):
        el = ET.Element('input', {})
        i = Input(el)

        self.assertEqual(i.name, None)

        i.name = 'someid'
        self.assertEqual(el.get('name'), 'someid')
        self.assertEqual(i.name, 'someid')

        el = ET.Element('input', {'name': 'bla'})
        i = Input(el)
        self.assertEqual(i.name, 'bla')

    def test_type(self):
        i = Input(ET.Element('select', {}))
        self.assertEqual(i.type, 'select')

        i = Input(ET.Element('textarea', {}))
        self.assertEqual(i.type, 'textarea')

        i = Input(ET.Element('input', {}))
        self.assertEqual(i.type, 'text')

        i = Input(HTML("<input type=radio>"))
        self.assertEqual(i.type, 'radio')

    def test_enabled(self):
        i = Input(HTML("<input type='text' name='bla'>"))
        self.assertEqual(i.enabled, True)

        i.enabled = False
        self.assertEqual(i.element.get('disabled'), 'disabled')

        i = Input(HTML("<input type='text' name='bla' disabled>"))
        self.assertEqual(i.enabled, False)

        i.enabled = True
        self.assertEqual(i.element.get('disabled'), None)

    def test_getvalue(self):
        i = Input(HTML("<input type='hidden' name=bla value=blub>"))
        self.assertEqual(i.value, 'blub')

        i = Input(HTML("<input>"))
        self.assertEqual(i.value, '') # NOT None!

        i = Input(HTML("<textarea>hohoho</textarea>"))
        self.assertEqual(i.value, 'hohoho')

        i = Input(HTML("<select><option selected value=a>b<option>c</select>"))
        self.assertEqual(i.value, 'a')

        i = Input(HTML("<select><option>a<option selected>c</select>"))
        self.assertEqual(i.value, 'c')

        i = Input(HTML("<select><option>a<option>b</select>"))
        self.assertEqual(i.value, None)

        with self.assertRaises(UnsupportedFormError):
            i = Input(HTML("<select><option selected>a<option selected>b</select>"))
            i.value

        # default value for checkboxes and radio buttons is "on"
        i = Input(HTML("<input type=checkbox>"))
        self.assertEqual(i.value, 'on')

        i = Input(HTML("<input type=checbox value=foo>"))
        self.assertEqual(i.value, 'foo')

        i = Input(HTML("<input type=radio>"))
        self.assertEqual(i.value, 'on')

        i = Input(HTML("<input type=radio value=bar>"))
        self.assertEqual(i.value, 'bar')

    def test_setvalue(self):
        i = Input(HTML("<input name=foo value=var>"))
        i.value = 'baz'
        self.assertEqual(i.element.get('value'), 'baz')

        i = Input(HTML('<textarea>blub</textarea>'))
        i.value = 'hello'
        self.assertEqual(i.element.text, 'hello')

        # select is more complicated
        select = HTML("<select>")
        option_a = HTML("<option value=a>b</option>")
        option_c = HTML("<option>c</option>")
        select.append(option_a); select.append(option_c)

        i = Input(select)
        i.value = 'a'

        self.assertEqual(option_a.get('selected'), 'selected')
        self.assertEqual(option_c.get('selected'), None)

        i.value = 'c'
        self.assertEqual(option_c.get('selected'), 'selected')
        self.assertEqual(option_a.get('selected'), None)

        with self.assertRaises(InvalidOptionError) as cm:
            i.value = 'bogus'

        self.assertEqual(cm.exception.select, select)
        self.assertEqual(cm.exception.value, 'bogus')

    def test_checked(self):
        i = Input(HTML('<input type=checkbox>'))
        self.assertEqual(i.checked, False)

        i = Input(HTML('<input type=text checked>'))
        self.assertEqual(i.checked, False)

        i = Input(HTML('<input type=radio checked>'))
        self.assertEqual(i.checked, True)

        i = Input(HTML('<input type=checkbox>'))
        i.checked = False
        self.assertEqual(i.element.get('checked'), None)

        i.checked = True
        self.assertEqual(i.element.get('checked'), 'checked')

        i = Input(HTML('<input type=radio checked>'))
        i.checked = False
        self.assertEqual(i.element.get('checked'), None)

        with self.assertRaises(UnsupportedFormError):
            i = Input(HTML('<input type=text checked>'))
            i.checked = False



if __name__ == '__main__':
    TEST_SERVER = test_server.start_test_server()

    unittest.main()
