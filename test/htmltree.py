#!/usr/bin/env python3

import unittest
import codecs
import xml.etree.ElementTree as ET
import htmltree_mini as HT

class XmlEquivTest(unittest.TestCase):
    def assertHtmlEqualsXml(self, html, xml):
        htree = HT.parsehtml(html)
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


class TestCharsetDetection(unittest.TestCase):
    def assertCodecEqual(self, a, b):
        self.assertEqual(codecs.lookup(a).name, codecs.lookup(b).name)

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

    def test_override(self):
        self.assertCodecEqual(HT.detect_charset(b'bla', 'utf-8'), 'utf-8')
        self.assertCodecEqual(HT.detect_charset(b'bla', 'ASCII'), 'cp1252')

if __name__ == '__main__':
    unittest.main()
