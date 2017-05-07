#!/usr/bin/env python3

import unittest
import codecs
import xml.etree.ElementTree as ET
import mechanize_mini.HtmlTree as HT

class XmlEquivTest(unittest.TestCase):
    def assertHtmlEqualsXml(self, html, xml):
        htree = HT.parsehtmlstr(html)
        xtree = ET.ElementTree(ET.fromstring(xml))

        # prune empty text nodes from xml
        for el in xtree.iter():
            if str(el.text).strip() == '':
                el.text = None
            if str(el.tail).strip() == '':
                el.tail = None

        self.assertEqual(ET.tostring(htree.getroot()),
                         ET.tostring(xtree.getroot()))

    def assertHtmlEqualsXmlFragment(self, html, xml):
        htree = ET.ElementTree(HT.parsefragmentstr(html))
        xtree = ET.ElementTree(ET.fromstring(xml))

        # prune empty text nodes from xml
        for el in xtree.iter():
            if str(el.text).strip() == '':
                el.text = None
            if str(el.tail).strip() == '':
                el.tail = None

        self.assertEqual(ET.tostring(htree.getroot()),
                         ET.tostring(xtree.getroot()))


class BasicTest(XmlEquivTest):
    def test_empty(self):
        self.assertHtmlEqualsXml('', '<html />')

    def test_vanilla(self):
        self.assertHtmlEqualsXml(
            '''
            <!DOCTYPE html>
            <html lang=en>
                <head>
                    <title>Vanilla Example</title>
                </head>
                <body>
                    Hello, World!
                </body>
            </html>
            ''',
            '''
            <html lang="en">
                <head>
                    <title>Vanilla Example</title>
                </head>
                <body>
                    Hello, World!
                </body>
            </html>
            ''')

    def test_implicit_html(self):
        self.assertHtmlEqualsXml('Hello, World!', '<html>Hello, World!</html>')
        self.assertHtmlEqualsXml('<p>Hello, <p>World!', '<html><p>Hello, </p><p>World!</p></html>')

    def test_unknown_tags(self):
        self.assertHtmlEqualsXml('<foo>bar</foo>', '<html><foo>bar</foo></html>')
        self.assertHtmlEqualsXml('blub<foo />lada', '<html>blub<foo/>lada</html>')

    def test_html_attrib_collapse(self):
        self.assertHtmlEqualsXml('<p>bla<html lang=en>blub<html foo=bar />',
                                 '<html lang="en" foo="bar"><p>blablub</p></html>')

    def test_single_special_chars(self):
        self.assertHtmlEqualsXml('a < dumbledore < blabla', '<html>a &lt; dumbledore &lt; blabla</html>')
        self.assertHtmlEqualsXml('a&dum</div>', '<html>a&amp;dum</html>')

    def test_attribute_without_val(self):
        self.assertHtmlEqualsXmlFragment('<foo bar />', '<foo bar="bar"/>')

    def test_fragment(self):
        self.assertHtmlEqualsXmlFragment('<p>bla</p>', '<p>bla</p>')

        # multiple elements -> will be returned in wrapper
        self.assertHtmlEqualsXmlFragment('<p>bla<p>blub', '<html><p>bla</p><p>blub</p></html>')

        # text before or after -> wrapper will be returned
        self.assertHtmlEqualsXmlFragment('<p>bla</p>blub', '<html><p>bla</p>blub</html>')
        self.assertHtmlEqualsXmlFragment('blub<p>bla', '<html>blub<p>bla</p></html>')

    def test_with_bom(self):
        self.assertHtmlEqualsXmlFragment('\uFEFF<p>bla</p>', '<p>bla</p>')

        # but only one bom will be removed
        self.assertHtmlEqualsXmlFragment('\uFEFF\uFEFF<p>bla</p>', '<html>\uFEFF<p>bla</p></html>')

    def test_autoclose(self):
        # list items
        self.assertHtmlEqualsXmlFragment(
            '''
            <ul>
                <li>bla
                <li>blub
                <li>abcdefg
            </ul>
            ''',
            '''
            <ul>
                <li>bla
                </li><li>blub
                </li><li>abcdefg
            </li></ul>
            ''')

        # tables
        self.assertHtmlEqualsXmlFragment(
            '''
            <table>
                <colgroup>
                    <col style="background-color: #0f0">
                    <col span="2">
                <colgroup>
                    <col>
                </colgroup>
                <tr>
                    <th>Howdy
                    <th>My friends!
                <tr>
                    <td>Tables
                    <td>Can totally
                    <td>Be abused
                    <td>We don't care about geometry no way
                    <table>
                        </td>
                    </table>
            </table>
            ''',
            '''
            <table>
                <colgroup>
                    <col style="background-color: #0f0"/>
                    <col span="2"/>
                </colgroup><colgroup>
                    <col/>
                </colgroup>
                <tr>
                    <th>Howdy
                    </th><th>My friends!
                </th></tr><tr>
                    <td>Tables
                    </td><td>Can totally
                    </td><td>Be abused
                    </td><td>We don't care about geometry no way
                    <table/>
            </td></tr></table>
            ''')

        # select items
        self.assertHtmlEqualsXmlFragment(
            '''
            <select>
                <optgroup label=Group1>
                    <option>a
                    <option>b
                <optgroup label=Group2>
                    <option>c
            </select>
            ''',
            '''
            <select>
                <optgroup label="Group1">
                    <option>a
                    </option><option>b
                </option></optgroup><optgroup label="Group2">
                    <option>c
            </option></optgroup></select>
            ''')

class ParagraphWeirdness(XmlEquivTest):
    def test_nested_paragraph(self):
        self.assertHtmlEqualsXml('<p>a<p>b</p>c</p>', '<html><p>a</p><p>b</p>c<p/></html>')

    def test_paragraph_in_header(self):
        self.assertHtmlEqualsXml('<h1><p>Bla</h1>', '<html><h1><p>Bla</p></h1></html>')

    def test_rogue_closing_tags(self):
        self.assertHtmlEqualsXml(
            '''
            <p>
                Bla
                <article>
                    Yumm</p>ie
                </article>
                Bla
            </p>
            ''',
            '''<html>
            <p>
                Bla
                </p>
                <article>
                    Yumm<p/>ie
                </article>
                Bla
            <p/>
            </html>''')
        self.assertHtmlEqualsXml(
            '''
            <div>
            <ul>
                <li>
                    <p>
                        Some Paragraph
                        </li>
                    </p>
                </li>
                </div>
            </ul>
            </div>
            ''',
            '''<html>
            <div>
            <ul>
                <li>
                    <p>
                        Some Paragraph
                        </p>
                </li>
                <p/>
            </ul>
            </div>
            </html>''')
        self.assertHtmlEqualsXml(
            '''
            <div>
            <ul>
                <li>
                    <p>
                        Some Paragraph
                        </li>
                    </p>
                </ul>
                </div>
            </ul>
            </div>
            ''',
            '''<html>
            <div>
            <ul>
                <li>
                    <p>
                        Some Paragraph
                        </p>
                </li>
                <p/>
            </ul>
            </div>
            </html>''')
        self.assertHtmlEqualsXml(
            '''
            <table>
                <td>
                    <p>
                    Bla
                        <table>
                            <td>
                                </table>
                            </td>
                        </table>
                    </p>
                    Blub
                </td>
            </table>
            ''', '''<html>
            <table>
                <td>
                    <p>
                    Bla
                        <table>
                            <td>
                                </td></table>
                    </p></td></table>
                    <p/>
                    Blub
                </html>''')

class TestFormatMisnesting(XmlEquivTest):
    def test_correct(self):
        self.assertHtmlEqualsXml('<b>a<div>b</div>c</b>', '<html><b>a<div>b</div>c</b></html>')

    def test_easy(self):
        self.assertHtmlEqualsXml('<b>a<i>b</b>c</i>', '<html><b>a<i>b</i></b><i>c</i></html>')

    def test_stray_endtags(self):
        self.assertHtmlEqualsXmlFragment('<p>bla</b>blub</p>', '<p>blablub</p>')

    def test_evil1(self):
        self.assertHtmlEqualsXml('<b>a<div>b<i>c<div>d</b>e</div>f</i>',
            '<html><b>a</b><div><b>b<i>c</i></b><i><div><b>d</b>e</div>f</i></div></html>')

    def test_evil2(self):
        self.assertHtmlEqualsXml('<div><b><i><hr>bla<div>blub</b>lala</i></div>',
            '<html><div><b><i><hr/>bla</i></b><i/><div><i><b>blub</b>lala</i></div></div></html>')

    def test_for_coverage(self):
        self.assertHtmlEqualsXmlFragment('<div><i>bla</div></i>', '<div><i>bla</i></div>')

class TestCharsetDetection(unittest.TestCase):
    def assertCodecEqual(self, a, b):
        self.assertEqual(codecs.lookup(a).name, codecs.lookup(b).name)

    def assertHtmlEqualsXml(self, html, xml, charset=None):
        htree = HT.parsehtmlbytes(html, charset)
        xtree = ET.ElementTree(ET.fromstring(xml))

        # prune empty text nodes from xml
        for el in xtree.iter():
            if str(el.text).strip() == '':
                el.text = None
            if str(el.tail).strip() == '':
                el.tail = None

        self.assertEqual(ET.tostring(htree.getroot()),
                         ET.tostring(xtree.getroot()))

    def test_default(self):
        self.assertCodecEqual(HT.detect_charset(b''), 'cp1252')

        # yes, even if utf-8 characters are inside we still default to cp1252
        self.assertCodecEqual(HT.detect_charset('blabläáßð«»'.encode('utf8')), 'cp1252')

    def test_bom(self):
        # various utf trickeries

        self.assertCodecEqual(HT.detect_charset('\uFEFFblöáðäü'.encode('utf-16-le')), 'utf-16-le')
        self.assertCodecEqual(HT.detect_charset('\uFEFFblöáðäü'.encode('utf-16-be')), 'utf-16-be')
        self.assertCodecEqual(HT.detect_charset('\uFEFFblöáðäü'.encode('utf8')), 'utf_8')

        # BOM overrides anything else
        self.assertCodecEqual(HT.detect_charset(codecs.BOM_UTF8 + b'<meta charset="ascii">'), 'utf_8')

    def test_meta(self):

        self.assertCodecEqual(HT.detect_charset(b'<meta charset="ascii">'), 'cp1252')
        self.assertCodecEqual(HT.detect_charset(b'<meta charset="utf8">'), 'utf-8')
        self.assertCodecEqual(HT.detect_charset(b'<meta charset="ascii">'), 'cp1252')
        self.assertCodecEqual(HT.detect_charset(b'<meta http-equiv=Content-Type content=text/html; charset=utf8>'), 'utf-8')
        self.assertCodecEqual(HT.detect_charset(b'<meta http-equiv="Content-Type" content="text/html; CHARSET= utf8">'), 'utf-8')

        # multiple meta tags -> only first valid one is evaluated
        self.assertCodecEqual(HT.detect_charset(b'<meta charset=ascii>blabla<meta charset="utf-8">'), 'cp1252')
        self.assertCodecEqual(HT.detect_charset(b'<meta charset=gucklug>blabla<meta charset="utf-8">'), 'utf-8')

        # meta content without charset -> cp1252
        self.assertCodecEqual(HT.detect_charset(b'<meta http-equiv="Content-Type" content="text/html">'), 'cp1252')

        # meta in ASCII test with UTF-16 -> gets turned into UTF-8
        self.assertCodecEqual(HT.detect_charset(b'<meta charset=UTF-16BE>blabla'), 'utf-8')

    def test_garbage(self):
        # garbage charset -> default win1252

        self.assertCodecEqual(HT.detect_charset(b'<meta charset="trololololoooool">'), 'cp1252')

        self.assertCodecEqual(HT.detect_charset(b'blabla', 'lutscher'), 'cp1252')

    def test_override(self):
        self.assertCodecEqual(HT.detect_charset(b'bla', 'utf-8'), 'utf-8')
        self.assertCodecEqual(HT.detect_charset(b'bla', 'ASCII'), 'cp1252')
        self.assertCodecEqual(HT.detect_charset(b'bla', 'latin-1'), 'cp1252')

    def test_html(self):
        # standard case
        self.assertHtmlEqualsXml(b'<p>bla', '<html><p>bla</p></html>')

        # unicode characters interpreted as cp1252
        self.assertHtmlEqualsXml('a\u2019b'.encode('utf-8'), '<html>aâ€™b</html>')

        # cp1252 characters misinterpreted as utf-8
        self.assertHtmlEqualsXml('aüb'.encode('cp1252'), '<html>a\uFFFDb</html>', charset='utf8')

if __name__ == '__main__':
    unittest.main()
