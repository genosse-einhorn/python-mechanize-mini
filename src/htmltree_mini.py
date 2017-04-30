from html.parser import HTMLParser
import xml.etree.ElementTree as ET
import codecs

from typing import List, Set, Dict, Tuple, Text, Optional, AnyStr, Union, IO

"""
Note: This parser is not supposed to actually implement the HTML5 standard to
any extent. The goal is to get a mostly usable tree out of most documents.
"""

class TreeBuildingHTMLParser(HTMLParser):
    default_scope_els = ['applet', 'caption', 'html', 'table', 'marquee', 'object', 'template']
    list_scope_els = default_scope_els + ['ol', 'ul']
    button_scope_els = default_scope_els + ['button']
    block_scope_els = default_scope_els + ["button", "address", "article", "aside",
        "blockquote", "center", "details", "dialog", "dir", "div", "dl",
        "fieldset", "figcaption", "figure", "footer", "header", "hgroup", "main",
        "menu", "nav", "ol", "p", "section", "summary", "ul", "h1", "h2", "h3",
        "h4", "h5", "h6", "pre", "listing", "form"]
    table_scope_els = ['html', 'table', 'template']
    select_scope_els = ['optgroup', 'option']

    formatting_els = ["b", "big", "code", "em", "font", "i", "s", "small",
                      "strike", "strong", "tt", "u", "a"]

    def __init__(self):
        super().__init__()

        self.tag_stack = [] # type: List[str]

        self.format_stack = [] # type: List[Tuple[str, Dict[str, str]]]

        self.builder = ET.TreeBuilder()

    def finish(self) -> ET.Element:
        if len(self.tag_stack) == 0:
            self.open_tag('html')

        # pop remaining tags
        while len(self.tag_stack) > 0:
            e = self.tag_stack.pop()
            self.builder.end(e)

        return self.builder.close()

    def has_in_scope(self, tag: str, scope_els: List[str]) -> bool:
        for i in reversed(self.tag_stack):
            if i == tag:
                return True

            if i in scope_els:
                break

        return False

    def open_tag(self, tag: str, attrs: Dict[str, str] = {}) -> None:
        self.tag_stack.append(tag)
        self.builder.start(tag, attrs)

    def close_tag(self, tag: str) -> None:
        # close elements until we have reached the element on the stack
        while len(self.tag_stack) > 1:
            e = self.tag_stack.pop()
            self.builder.end(e)
            if e == tag:
                break

    def restore_format_stack(self) -> None:
        fstack = self.format_stack[::-1]
        tstack = self.tag_stack[::-1]

        while len(tstack) > 0 and len(fstack) > 0:
            while len(tstack) > 0 and tstack[-1] != fstack[-1][0]:
                tstack.pop()

            if len(tstack) > 0:
                assert tstack[-1] == fstack[-1][0]
                tstack.pop()
                fstack.pop()

        # tags are left on the format stack -> we must open them now
        while len(fstack) > 0:
            fel = fstack.pop()
            self.open_tag(fel[0], fel[1])


    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        if len(self.tag_stack) == 0 and tag != 'html':
            self.open_tag('html')

        # these tags will close open <p> tags
        if tag in [ "address", "article", "aside", "blockquote", "center",
                    "details", "dialog", "dir", "div", "dl", "fieldset", "figcaption",
                    "figure", "footer", "header", "hgroup", "main", "menu", "nav",
                    "ol", "p", "section", "summary", "ul", "h1", "h2", "h3", "h4",
                    "h5", "h6", "pre", "listing", "form" ]:
            if self.has_in_scope('p', self.block_scope_els):
                self.close_tag('p')

        # these tags implicitly close themselves, provided they are in their proper parent containers
        if (tag in ['caption', 'colgroup', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr']
                    and self.has_in_scope(tag, ['table'])):
            self.close_tag(tag)

        if tag in ['dd', 'dt', 'li'] and self.has_in_scope(tag, ['dl', 'ol', 'ul']):
            self.close_tag(tag)

        if tag in ['optgroup', 'option'] and self.has_in_scope(tag, ['select']):
            self.close_tag(tag)

        # inline formatting tags will use the formatting stack
        if tag in self.formatting_els:
            self.restore_format_stack
            self.format_stack.append((tag, dict(attrs)))

        # generate open tag
        self.open_tag(tag, dict(attrs))

        # self-closing tags get closed right away
        if tag in ["area", "br", "embed", "img", "keygen", "wbr", "input", "param",
                   "source", "track", "hr", "image", "base", "basefont", "bgsound",
                   "link", "meta", "col", "frame"]:
            self.close_tag(tag)

    def handle_endtag(self, tag: str) -> None:
        # we just ignore the </html> tag
        if tag == 'html':
            return

        # </p> may appear in block context only, might insert empty <p/>
        if tag == 'p' and not(self.has_in_scope(tag, self.block_scope_els)):
            self.open_tag('p')

        # list items can only be closed in list context
        if tag in ['li', 'dd', 'dt'] and not(self.has_in_scope(tag, self.list_scope_els)):
            return

        # by default, elements can be only closed in table scope
        if self.has_in_scope(tag, self.default_scope_els):
            self.close_tag(tag)

            if len(self.format_stack) > 0 and self.format_stack[-1][0] == tag:
                self.format_stack.pop()

    def handle_data(self, data: str) -> None:
        if data.strip() == '':
            return

        self.restore_format_stack

        if len(self.tag_stack) == 0:
            self.open_tag('html')

        self.builder.data(data)

class CharsetDetectingHTMLParser(HTMLParser):
    """
    HTML Parser that does nothing but watch for <meta... charset tags
    """

    def __init__(self) -> None:
        super().__init__()

        self.charset = None # type: Optional[str]
        """The detected charset. May be :code:`None` if no charset is found"""

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        if not(self.charset is None):
            return

        ad = dict(attrs)

        if tag == 'meta':
            if 'charset' in ad:
                self.charset = ad['charset']
            elif ('http-equiv' in ad and 'content' in ad
                     and ad['http-equiv'].lower() == 'content-type'
                     and ad['content'].lower().find('charset=') != -1):
                self.charset = ad['content'].lower().split('charset=')[-1].strip()

def detect_charset(html: bytes, charset: Optional[str] = None) -> str:
    """
    Detects the character set of the given html file.

    This function will search for a BOM or the charset <meta> tag
    and return the name of the appropriate python codec.

    Note: ISO-8859-1 and US-ASCII will be changed to windows-1252
    (this is specified by WHATWG and Browser actually do this).
    The default encoding is windows-1252.

    Parameters
    ----------
    charset
        Charset information obtained via external means, e.g. HTTP header.
        This will override any <meta> tag found in the document.
    """

    if charset is None:
        # check for BOM
        if html[0:3] == b'\xEF\xBB\xBF':
            charset = 'utf-8'
        if html[0:2] == b'\xFE\xFF':
            charset = 'utf-16-be'
        if html[0:2] == b'\xFF\xFE':
            charset = 'utf-16-le'

    if charset is None:
        # check meta tag
        parser = CharsetDetectingHTMLParser()
        parser.feed(str(html, 'ascii', 'replace'))
        parser.close()

        charset = parser.charset

    if charset is None:
        # default: windows-1252
        charset = 'cp1252'

    # look up the python charset
    try:
        info = codecs.lookup(charset)
        charset = info.name
    except LookupError:
        charset = 'cp1252' # fallback

    # replace ascii codecs
    if charset in ['latin_1', 'ascii']:
        charset = 'cp1252'

    return charset

def parsefragment(html: str) -> ET.Element:
    # remove BOM
    if html[0:0] == '\uFEFF':
        html = html[1:]

    parser = TreeBuildingHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.finish()

def parsehtml(html: str) -> ET.ElementTree:
    # remove BOM
    if html[0:0] == '\uFEFF':
        html = html[1:]

    parser = TreeBuildingHTMLParser()
    parser.feed(html)
    parser.close()
    return ET.ElementTree(parser.finish())
