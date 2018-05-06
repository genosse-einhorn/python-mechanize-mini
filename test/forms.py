#!/usr/bin/env python3

import unittest

import mechanize_mini as minimech
from mechanize_mini import HTML, HtmlFormElement, HtmlInputElement, UnsupportedFormError, InputNotFoundError

import test_server

TEST_SERVER = None

browser = minimech.Browser('MiniMech test suite / jonas@kuemmerlin.eu')
class FormAccessorTest(unittest.TestCase):
    def test_defaults(self):
        page = browser.open(TEST_SERVER + '/form.html')
        form = page.forms[0]

        # neither name and id are set on the form
        self.assertEqual(form.name, None)
        self.assertEqual(form.id, None)

        # the rest are defaults
        self.assertEqual(form.method, 'GET')
        self.assertEqual(form.action, page.url)
        self.assertEqual(form.enctype, 'application/x-www-form-urlencoded')

        # form.action has a special default if the form's page is unset
        form.page = None
        self.assertEqual(form.action, '')

    def test_nondefaults(self):
        page = browser.open(TEST_SERVER + '/form.html')
        form = page.forms[1]

        self.assertEqual(form.name, 'withaction')
        self.assertEqual(form.id, 'actionwith')
        self.assertEqual(form.method, 'POST')
        self.assertEqual(form.action, TEST_SERVER + '/show-post-params')

    def test_input_getvalue(self):
        page = browser.open(TEST_SERVER + '/form.html')
        form = page.forms[1]

        self.assertEqual(form.get_field('foo'), 'bar')
        self.assertEqual(form.get_field('checker'), 'theval')
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
        for i in (x for x in form.iter('input') if x.name == 'gaga'):
            if i.value == 'a':
                i.checked = True

        self.assertEqual(form.get_field('gaga'), 'a')

        # throws if multiple radio buttons are selected
        for i in (x for x in form.iter('input') if x.name == 'gaga'):
            if i.value == 'b':
                i.checked = True

        with self.assertRaises(UnsupportedFormError):
            form.get_field('gaga')


    def test_input_setvalue(self):
        page = browser.open(TEST_SERVER + '/form.html')
        form = page.forms[1]

        foo = form.elements['foo']
        form.set_field('foo', 'baz')
        self.assertEqual(foo.get('value'), 'baz')

        # <select>

        # set option with text
        form.set_field('checker', 'Text is Value')
        self.assertEqual(form.get_field('checker'), 'Text is Value')
        self.assertEqual(page.query_selector('option:contains(Text is Value)').get('selected'), 'selected')

        # set option with custom value
        form.set_field('checker', 'theval')
        self.assertEqual(form.get_field('checker'), 'theval')
        self.assertEqual(page.query_selector('#val1').get('selected'), 'selected')

        # set nonexistent option
        with self.assertRaises(UnsupportedFormError):
            form.set_field('checker', 'bogus')

        # nonexistent elements
        with self.assertRaises(InputNotFoundError):
            form.set_field('nonexistent', 'bla')

        # textarea
        txa = form.query_selector('textarea')
        form.set_field('longtext', 'blabla')
        self.assertEqual(txa.text, 'blabla')

        # crashes for multiple inputs with same name
        with self.assertRaises(UnsupportedFormError):
            form.set_field('twice', 'rice')

        with self.assertRaises(UnsupportedFormError):
            form.set_field('conflict', 'armed')

        # can select a radio button
        form.set_field('gaga', 'a')
        for i in (x for x in form.iter('input') if x.name == 'gaga'):
            self.assertEqual(i.value == 'a', i.checked)

        # make sure old one has been properly unselected
        form.set_field('gaga', 'b')
        for i in (x for x in form.iter('input') if x.name == 'gaga'):
            self.assertEqual(i.value == 'b', i.checked)

        # can't select non-existing radio button
        with self.assertRaises(UnsupportedFormError):
            form.set_field('gaga', 'd')

    def test_input_list(self):
        page = browser.open(TEST_SERVER + '/form.html')
        form = page.forms[1]

        # name accessor
        self.assertEqual(form.elements['foo'],
            next(x for x in form.iter('input') if x.get('name') == 'foo'))

        with self.assertRaises(IndexError):
            form.elements['i-do-not-exist']

        # int accessor
        self.assertEqual(form.elements[0], form.query_selector('input'))

        # length
        self.assertEqual(len(form.elements), len([x for x in form.query_selector_all('*') if x.tag in ['input', 'select', 'textarea']]))

class InputTest(unittest.TestCase):
    def test_construct(self):
        el = HTML('<input>')
        self.assertIsInstance(el, HtmlInputElement)

        # TODO: split in textarea and select classes
        el = HTML('<textarea>')
        self.assertIsInstance(el, HtmlInputElement)

        el = HTML('<select>')
        self.assertIsInstance(el, HtmlInputElement)

        el = HTML('<p>')
        self.assertNotIsInstance(el, HtmlInputElement)


    def test_id(self):
        i = minimech.HtmlElement('input')

        self.assertEqual(i.id, None)

        i.id = 'someid'
        self.assertEqual(i.get('id'), 'someid')
        self.assertEqual(i.id, 'someid')

        i = minimech.HtmlElement('input', {'id': 'bla'})
        self.assertEqual(i.id, 'bla')

    def test_name(self):
        i = minimech.HtmlElement('input', {})

        self.assertEqual(i.name, None)

        i.name = 'someid'
        self.assertEqual(i.get('name'), 'someid')
        self.assertEqual(i.name, 'someid')

        i = minimech.HtmlElement('input', {'name': 'bla'})
        self.assertEqual(i.name, 'bla')

    def test_type(self):
        i = minimech.HtmlElement('select', {})
        self.assertEqual(i.type, 'select')

        i = minimech.HtmlElement('textarea', {})
        self.assertEqual(i.type, 'textarea')

        i = minimech.HtmlElement('input', {})
        self.assertEqual(i.type, 'text')

        i = HTML("<input type=radio>")
        self.assertEqual(i.type, 'radio')

    def test_enabled(self):
        i = HTML("<input type='text' name='bla'>")
        self.assertEqual(i.enabled, True)

        i.enabled = False
        self.assertEqual(i.get('disabled'), 'disabled')

        i = HTML("<input type='text' name='bla' disabled>")
        self.assertEqual(i.enabled, False)

        i.enabled = True
        self.assertEqual(i.get('disabled'), None)

        # make sure it doesn't break when setting it twice
        # (we also need this for coverage masturbation)
        i.enabled = True
        i.enabled = True
        i.enabled = False
        i.enabled = False

    def test_getvalue(self):
        i = HTML("<input type='hidden' name=bla value=blub>")
        self.assertEqual(i.value, 'blub')

        i = HTML("<input>")
        self.assertEqual(i.value, '') # NOT None!

        i = HTML("<textarea>hohoho</textarea>")
        self.assertEqual(i.value, 'hohoho')

        i = HTML("<select><option selected value=a>b<option>c</select>")
        self.assertEqual(i.value, 'a')

        i = HTML("<select><option>a<option selected>c</select>")
        self.assertEqual(i.value, 'c')

        # by default: first option selected
        i = HTML("<select><option>a<option>b</select>")
        self.assertEqual(i.value, 'a')

        # unless there are no options: then empty string
        i = HTML("<select></select>")
        self.assertEqual(i.value, '')

        with self.assertRaises(UnsupportedFormError):
            i = HTML("<select><option selected>a<option selected>b</select>")
            i.value

        # default value for checkboxes and radio buttons is "on"
        i = HTML("<input type=checkbox>")
        self.assertEqual(i.value, 'on')

        i = HTML("<input type=checbox value=foo>")
        self.assertEqual(i.value, 'foo')

        i = HTML("<input type=radio>")
        self.assertEqual(i.value, 'on')

        i = HTML("<input type=radio value=bar>")
        self.assertEqual(i.value, 'bar')

    def test_setvalue(self):
        i = HTML("<input name=foo value=var>")
        i.value = 'baz'
        self.assertEqual(i.get('value'), 'baz')

        i = HTML('<textarea>blub</textarea>')
        i.value = 'hello'
        self.assertEqual(i.text, 'hello')

        # select is more complicated
        select = HTML("<select>")
        option_a = HTML("<option value=a>b</option>")
        option_c = HTML("<option>c</option>")
        select.append(option_a); select.append(option_c)

        select.value = 'a'

        self.assertEqual(option_a.get('selected'), 'selected')
        self.assertEqual(option_c.get('selected'), None)

        select.value = 'c'
        self.assertEqual(option_c.get('selected'), 'selected')
        self.assertEqual(option_a.get('selected'), None)

        with self.assertRaises(UnsupportedFormError):
            select.value = 'bogus'

    def test_checked(self):
        i = HTML('<input type=checkbox>')
        self.assertEqual(i.checked, False)

        i = HTML('<input type=text checked>')
        self.assertEqual(i.checked, False)

        i = HTML('<input type=radio checked>')
        self.assertEqual(i.checked, True)

        i = HTML('<input type=checkbox>')
        i.checked = False
        self.assertEqual(i.get('checked'), None)

        i.checked = True
        self.assertEqual(i.get('checked'), 'checked')

        i = HTML('<input type=radio checked>')
        i.checked = False
        self.assertEqual(i.get('checked'), None)

        with self.assertRaises(UnsupportedFormError):
            i = HTML('<input type=text checked>')
            i.checked = False

    def test_multiselect(self):
        i = HTML('<select><option>a<option value=b selected>c</select>')
        self.assertEqual([(o.value, o.text) for o in i.options], [('a', 'a'),('b', 'c')])
        self.assertEqual(i.options.get_selected(), ['b'])

        # works with sets
        i.options.set_selected({'b','a'})
        self.assertEqual(list(i.query_selector_all('option'))[0].get('selected'), 'selected')
        self.assertEqual(list(i.query_selector_all('option'))[1].get('selected'), 'selected')
        self.assertEqual(i.options.get_selected(), ['a','b'])

        # also works with lists
        i.options.set_selected(['a'])
        self.assertEqual(list(i.query_selector_all('option'))[0].get('selected'), 'selected')
        self.assertEqual(list(i.query_selector_all('option'))[1].get('selected'), None)
        self.assertEqual(i.options.get_selected(), ['a'])

        # can individually select options
        i.options['b'].selected = True
        self.assertEqual(list(i.query_selector_all('option'))[1].get('selected'), 'selected')

        # and unselect them
        i.options['b'].selected = False
        self.assertEqual(list(i.query_selector_all('option'))[1].get('selected'), None)
        # and unselect them again for code coverage masturbation
        i.options['b'].selected = False
        self.assertEqual(list(i.query_selector_all('option'))[1].get('selected'), None)
        self.assertEqual(i.options['b'].selected, False)

        # bogus option accessors throw
        with self.assertRaises(IndexError):
            i.options['bogus'].selected = True

        # can also clear select status
        i.options.set_selected(iter([]))
        self.assertEqual(list(i.query_selector_all('option'))[0].get('selected'), None)
        self.assertEqual(list(i.query_selector_all('option'))[1].get('selected'), None)
        self.assertEqual(i.options.get_selected(), [])

        # oh and btw we can also retrieve the number of options
        self.assertEqual(len(i.options), 2)

        # and - rogue feature which doesn't type check - you can assign an option to value
        i.value = i.options[0]
        self.assertEqual(list(i.query_selector_all('option'))[0].get('selected'), 'selected')
        self.assertEqual(list(i.query_selector_all('option'))[1].get('selected'), None)
        self.assertEqual(i.options.get_selected(), ['a'])

        # raises for invalid options
        with self.assertRaises(UnsupportedFormError):
            i.options.set_selected(['bogus'])

        # raises for non-select elements
        i = HTML('<input>')
        with self.assertRaises(AttributeError):
            i.options

class FindFormTest(unittest.TestCase):
    def test_find_by_name_id(self):
        page = browser.open(TEST_SERVER + '/form.html')
        formname = page.forms['withaction']
        formid = page.query_selector('#actionwith')
        formsecond = page.forms[1]

        self.assertEqual(formname, formid)
        self.assertEqual(formid, formsecond)

        with self.assertRaises(IndexError):
            page.forms['alkfmwalkfmawlfawf']

        self.assertEqual(len(page.forms), len(list(page.query_selector_all('form'))))

class SubmitTest(unittest.TestCase):
    def test_formdata(self):
        form = HTML("""
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
            """)
        self.assertEqual(list(form.get_formdata()), [
                ('name', 'Mustermann'),
                ('b', 'on'),
                ('bogustype', 'lala'),
                ('b', 'a'),
                ('b', 'c')
            ])

    def test_get(self):
        page = browser.open(TEST_SERVER + '/empty.html')
        form = HTML("""
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
            """)
        form.page = page
        result = form.submit()
        self.assertEqual(result.document.text,
            'name=Müßtérmañ\nb=on\nbogustype=lala\nb=a\nb=c\n')

    def test_bogus_encoding(self):
        page = browser.open(TEST_SERVER + '/form.html') # has utf-8 encoding
        form = HTML("""
            <form action=show-post-params method=post accept-charset=latin-bogus>
                <input type=text name=name value='Müßtérmañ'>
            </form>
            """)
        form.page = page
        result = form.submit()
        self.assertEqual(result.document.text, 'name=Müßtérmañ\n')

    def test_encoding_without_page(self):
        form = HTML("""
            <form action=show-post-params method=post accept-charset=latin-bogus>
                <input type=text name=name value='Müßtérmañ'>
            </form>
            """)
        self.assertEqual(form.accept_charset, 'utf-8')

    def test_post(self):
        page = browser.open(TEST_SERVER + '/form.html')
        form = HTML("""
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
            """)
        form.page = page
        result = form.submit()
        self.assertEqual(result.document.text,
            'name=Müßtérmañ\nb=on\nbogustype=lala\nb=a\nb=c\n')

if __name__ == '__main__':
    TEST_SERVER = test_server.start_test_server()

    unittest.main()
