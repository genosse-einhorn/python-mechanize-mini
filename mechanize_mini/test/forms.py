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

        with self.assertRaises(InputNotFoundError):
            form.get_field('nonexistent')

        # crashes for multiple inputs with same name
        with self.assertRaises(UnsupportedFormError):
            form.get_field('twice')

        with self.assertRaises(UnsupportedFormError):
            form.get_field('conflict')

        # returns null if no radio button is selected
        self.assertEqual(form.get_field('gaga'), None)

        # returns the selected radio button if there is one
        for i in form.find_all_inputs(name='gaga'):
            if i.value == 'a':
                i.checked = True

        self.assertEqual(form.get_field('gaga'), 'a')

        # throws if multiple radio buttons are selected
        for i in form.find_all_inputs(name='gaga'):
            if i.value == 'b':
                i.checked = True

        with self.assertRaises(UnsupportedFormError):
            form.get_field('gaga')


    def test_input_setvalue(self):
        page = browser.open(TEST_SERVER + '/form.html')
        form = Form(list(page.document.iter('form'))[1], page)

        foo = next(x for x in form.element.iterfind() if x.get('name') == 'foo')
        form.set_field('foo', 'baz')
        self.assertEqual(foo.get('value'), 'baz')

        # <select>

        # set option with text
        form.set_field('checker', 'Text is Value')
        self.assertEqual(form.get_field('checker'), 'Text is Value')
        self.assertEqual(page.find('.//option', text='Text is Value').get('selected'), 'selected')

        # set option with custom value
        form.set_field('checker', 'theval')
        self.assertEqual(form.get_field('checker'), 'theval')
        self.assertEqual(page.find(id='val1').get('selected'), 'selected')

        # set nonexistent option
        with self.assertRaises(minimech.forms.InvalidOptionError) as cm:
            form.set_field('checker', 'bogus')
        self.assertEqual(cm.exception.select.tag, 'select')
        self.assertEqual(cm.exception.value, 'bogus')

        # nonexistent elements
        with self.assertRaises(minimech.forms.InputNotFoundError):
            form.set_field('nonexistent', 'bla')

        # textarea
        txa = form.find_input(type='textarea')
        form.set_field('longtext', 'blabla')
        self.assertEqual(txa.element.text, 'blabla')

        # crashes for multiple inputs with same name
        with self.assertRaises(UnsupportedFormError):
            form.set_field('twice', 'rice')

        with self.assertRaises(UnsupportedFormError):
            form.set_field('conflict', 'armed')

        # can select a radio button
        form.set_field('gaga', 'a')
        for i in form.find_all_inputs(name='gaga'):
            self.assertEqual(i.value == 'a', i.checked)

        # make sure old one has been properly unselected
        form.set_field('gaga', 'b')
        for i in form.find_all_inputs(name='gaga'):
            self.assertEqual(i.value == 'b', i.checked)

        # can't select non-existing radio button
        with self.assertRaises(UnsupportedFormError):
            form.set_field('gaga', 'd')


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

        # make sure it doesn't break when setting it twice
        # (we also need this for coverage masturbation)
        i.enabled = True
        i.enabled = True
        i.enabled = False
        i.enabled = False

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

    def test_multiselect(self):
        i = Input(HTML('<select><option>a<option value=b selected>c</select>'))
        self.assertEqual([(o.value, o.text) for o in i.options], [('a', 'a'),('b', 'c')])
        self.assertEqual(i.options.get_selected(), ['b'])

        # works with sets
        i.options.set_selected({'b','a'})
        self.assertEqual(i.element.find('.//option', n=0).get('selected'), 'selected')
        self.assertEqual(i.element.find('.//option', n=1).get('selected'), 'selected')
        self.assertEqual(i.options.get_selected(), ['a','b'])

        # also works with lists
        i.options.set_selected(['a'])
        self.assertEqual(i.element.find('.//option', n=0).get('selected'), 'selected')
        self.assertEqual(i.element.find('.//option', n=1).get('selected'), None)
        self.assertEqual(i.options.get_selected(), ['a'])

        # can individually select options
        i.options['b'].selected = True
        self.assertEqual(i.element.find('.//option', n=1).get('selected'), 'selected')

        # and unselect them
        i.options['b'].selected = False
        self.assertEqual(i.element.find('.//option', n=1).get('selected'), None)
        # and unselect them again for code coverage masturbation
        i.options['b'].selected = False
        self.assertEqual(i.element.find('.//option', n=1).get('selected'), None)
        self.assertEqual(i.options['b'].selected, False)

        # bogus option accessors throw
        with self.assertRaises(IndexError):
            i.options['bogus'].selected = True

        # can also clear select status
        i.options.set_selected(iter([]))
        self.assertEqual(i.element.find('.//option', n=0).get('selected'), None)
        self.assertEqual(i.element.find('.//option', n=1).get('selected'), None)
        self.assertEqual(i.options.get_selected(), [])

        # oh and btw we can also retrieve the number of options
        self.assertEqual(len(i.options), 2)

        # and - rogue feature which doesn't type check - you can assign an option to value
        i.value = i.options[0]
        self.assertEqual(i.element.find('.//option', n=0).get('selected'), 'selected')
        self.assertEqual(i.element.find('.//option', n=1).get('selected'), None)
        self.assertEqual(i.options.get_selected(), ['a'])

        # raises for invalid options
        with self.assertRaises(UnsupportedFormError):
            i.options.set_selected(['bogus'])

        # raises for non-select elements
        i = Input(HTML('<input>'))
        with self.assertRaises(UnsupportedFormError):
            i.options

class FindFormTest(unittest.TestCase):
    def test_find_by_name_id(self):
        page = browser.open(TEST_SERVER + '/form.html')
        formname = page.find_form(name='withaction')
        formid = page.find_form(id='actionwith')
        formboth = page.find_form(name='withaction',id='actionwith')
        formsecond = page.find_form(n=1)

        self.assertEqual(formname.element, formid.element)
        self.assertEqual(formid.element, formboth.element)
        self.assertEqual(formboth.element, formsecond.element)

class FindInputTest(unittest.TestCase):
    def test_find_by_type(self):
        form = Form(HTML("""
            <form>
                <input name='notype' value='bla'>
                <select id='checkme'></select>
                <input name='bogustype' type=BOGUS value=lala>
                <textarea>trololo</textarea>
            </form>
            """), None)

        self.assertEqual(form.find_input(type='text').name, 'notype')
        self.assertEqual(form.find_input(type='select').id, 'checkme')
        self.assertEqual(form.find_input(type='bogus').name, 'bogustype')
        self.assertEqual(form.find_input(type='textarea').value, 'trololo')

    def test_find_enabled(self):
        form = Form(HTML("""
            <form>
                <input name='notype' value='bla' disabled>
                <input name='bogustype' type=bogus value=lala>
            </form>
            """), None)

        with self.assertRaises(HT.ElementNotFoundError):
            form.find_input(name='notype', enabled=True)
        with self.assertRaises(HT.ElementNotFoundError):
            form.find_input(name='bogustype', enabled=False)

        self.assertEqual(form.find_input(enabled=False).name, 'notype')
        self.assertEqual(form.find_input(enabled=True).type, 'bogus')

    def test_find_checked(self):
        form = Form(HTML("""
            <form>
                <input type=CHeckBOX name=a>
                <input type=RaDIO name=b checked>
            </form>
            """), None)

        with self.assertRaises(HT.ElementNotFoundError):
            form.find_input(name='a', checked=True)
        with self.assertRaises(HT.ElementNotFoundError):
            form.find_input(name='b', checked=False)

        self.assertEqual(form.find_input(checked=False).name, 'a')
        self.assertEqual(form.find_input(checked=True).type, 'radio')

class SubmitTest(unittest.TestCase):
    def test_formdata(self):
        form = Form(HTML("""
            <form>
                <input type=hidden value=lala>
                <input type=text name=name value='Mustermann'>
                <input type=CHeckBOX name=a>
                <input type=RaDIO name=b checked>
                <input name='notype' value='bla' disabled>
                <input name='bogustype' type=bogus value=lala>

                <select name=b>
                    <option selected>a</option>
                    <option value=b>alfwaklfawklm</option>
                    <option value=c selected>afmalfm</option>
                </select>
            </form>
            """), None)
        self.assertEqual(list(form.get_formdata()), [
                ('name', 'Mustermann'),
                ('b', 'on'),
                ('bogustype', 'lala'),
                ('b', 'a'),
                ('b', 'c')
            ])

    def test_get(self):
        page = browser.open(TEST_SERVER + '/empty.html')
        form = Form(HTML("""
            <form action=/show-params accept-charset=UTF-8>
                <input type=hidden value=lala>
                <input type=text name=name value='Müßtérmañ'>
                <input type=CHeckBOX name=a>
                <input type=RaDIO name=b checked>
                <input name='notype' value='bla' disabled>
                <input name='bogustype' type=bogus value=lala>

                <select name=b>
                    <option selected>a</option>
                    <option value=b>alfwaklfawklm</option>
                    <option value=c selected>afmalfm</option>
                </select>
            </form>
            """), page)
        result = form.submit()
        self.assertEqual(result.document.text,
            'name=Müßtérmañ\nb=on\nbogustype=lala\nb=a\nb=c\n')

    def test_bogus_encoding(self):
        page = browser.open(TEST_SERVER + '/form.html') # has utf-8 encoding
        form = Form(HTML("""
            <form action=show-post-params method=post accept-charset=latin-bogus>
                <input type=text name=name value='Müßtérmañ'>
            </form>
            """), page)
        result = form.submit()
        self.assertEqual(result.document.text, 'name=Müßtérmañ\n')

    def test_post(self):
        page = browser.open(TEST_SERVER + '/form.html')
        form = Form(HTML("""
            <form action=show-post-params method=post>
                <input type=hidden value=lala>
                <input type=text name=name value='Müßtérmañ'>
                <input type=CHeckBOX name=a>
                <input type=RaDIO name=b checked>
                <input name='notype' value='bla' disabled>
                <input name='bogustype' type=bogus value=lala>

                <select name=b>
                    <option selected>a</option>
                    <option value=b>alfwaklfawklm</option>
                    <option value=c selected>afmalfm</option>
                </select>
            </form>
            """), page)
        result = form.submit()
        self.assertEqual(result.document.text,
            'name=Müßtérmañ\nb=on\nbogustype=lala\nb=a\nb=c\n')

if __name__ == '__main__':
    TEST_SERVER = test_server.start_test_server()

    unittest.main()
