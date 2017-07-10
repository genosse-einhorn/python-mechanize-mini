"""
A parser to parse a HTML document into an :any:`xml.etree.ElementTree`

The parser is roughly inspired by the WHATWG HTML5 spec, but following it to the
letter is an explicit non-goal. This helps to keep the code size down, but it
may manifest itself on some pages by creating a slightly different document tree
than a browser, especially when grossly misnested elements are involved.

The parser output closely resembles the structure of the HTML input.
If the document does not contain a <head> or <body>, then you won't get these
elements in tree (and the content will be a child of <html> directly).

"""

import xml.etree.ElementPath as ElementPath
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
import codecs
import re

from typing import List, Set, Dict, Tuple, Text, Optional, AnyStr, Union, IO, \
        Sequence, Iterator, Iterable, TypeVar, KeysView, ItemsView, cast

THtmlElement = TypeVar('THtmlElement', bound='HtmlElement')
T = TypeVar('T')
class HtmlElement(Sequence['HtmlElement']):
    """
    An HTML Element

    This is designed to be duck-compatible with :any:`xml.etree.ElementTree.Element`,
    but is extended with new additional methods
    """

    def __init__(self, tag: str, attrib: Dict[str,str] = {}, **extra) -> None:
        """
        Create a new Element

        TODO: Document Exceptions for subclasses
        """

        self.tag = tag # type: str
        """The element tag name (:any:`str`)"""

        self.attrib = attrib.copy() # type: Dict[str,str]
        """The element's attributes (dictionary str->str)"""

        self.text = '' # type: str
        """
        Element text before the first subelement.
        This is always a :any:`str`
        """

        self.tail = '' # type: str
        """
        Text after this element's end tag up until the next sibling tag.
        This is always a :any:`str`
        """


        self.attrib.update(extra)
        self._children = [] # type: List[HtmlElement]

    def makeelement(self: THtmlElement, tag: str, attrib:Dict[str,str]) -> THtmlElement:
        # Deprecated, just here for compatibility with etree.
        return self.__class__(tag, attrib)

    def copy(self: THtmlElement) -> THtmlElement:
        """
        Make a shallow copy of current element.
        """
        elem = self.__class__(self.tag, self.attrib)
        elem.text = self.text
        elem.tail = self.tail
        elem[:] = self
        return elem

    def append(self, subelement: 'HtmlElement') -> None:
        """
        Add a new child element
        """
        self._children.append(subelement)

    def extend(self, elements: Iterable['HtmlElement']) -> None:
        """
        Add multiple elements
        """
        for element in elements:
            self.append(element)

    def insert(self, index: int, subelement: 'HtmlElement') -> None:
        """Insert a given child at the given position."""
        self._children.insert(index, subelement)

    def remove(self, subelement: 'HtmlElement') -> None:
        """Remove the given child element"""
        self._children.remove(subelement)

    def getchildren(self) -> Sequence['HtmlElement']:
        # deprecated, just here for etree compat
        return self._children

    def find(self, path:str='.//', namespaces:Dict[str,str]=None, *,
             id:str=None, class_name:str=None, text:str=None, n:int=0) -> Optional['HtmlElement']:
        """
        Find first element matching the given conditions.

        See: findall
        """
        els = self.iterfind(path, namespaces, id=id, class_name=class_name, text=text)
        retval = next(els, None)
        for i in range(1, n+1):
            try:
                retval = next(els)
            except StopIteration as e:
                return None

        return retval


    def findall(self, path:str='.//', namespaces:Dict[str,str]=None, *,
             id:str=None, class_name:str=None, text:str=None) -> List['HtmlElement']:
        return list(self.iterfind(path, namespaces, id=id, class_name=class_name, text=text))

    def iterfind(self, path:str='.//', namespaces:Dict[str,str]=None, *,
                 id:str=None, class_name:str=None, text:str=None) -> Iterator['HtmlElement']:
        # FIXME: fighting against the type checker
        for eltmp in ElementPath.iterfind(self, path, namespaces): # type: ignore
            el = cast(HtmlElement, eltmp)

            if id is not None:
                if el.get('id') != id:
                    continue

            if class_name is not None:
                if class_name not in (el.get('class') or '').split():
                    continue

            if text is not None:
                if el.text_content != text:
                    continue

            yield el

    def findtext(self, path, default=None, namespaces=None):
        return ElementPath.findtext(self, path, default, namespaces)

    def clear(self) -> None:
        self.attrib.clear()
        self._children = []
        self.text = ''
        self.tail = ''

    def get(self, key: str, default:T=None) -> Union[str,T,None]:
        """
        Get an attribute value.
        """
        return self.attrib.get(key, default)

    def set(self, key: str, value: str) -> None:
        """
        Set an attribute
        """
        self.attrib[key] = value

    def keys(self) -> KeysView[str]:
        """
        List of attribute names
        """
        return self.attrib.keys()

    def items(self) -> ItemsView[str,str]:
        """
        Attributes as (key, value) sequence
        """
        return self.attrib.items()

    def iter(self, tag:str=None) -> Iterator['HtmlElement']:
        if tag == "*":
            tag = None

        if tag is None or self.tag == tag:
            yield self

        for e in self._children:
            yield from e.iter(tag)

    def getiterator(self, tag:str=None) -> List['HtmlElement']:
        # deprectated, just for etree compat
        return list(self.iter(tag))

    def itertext(self) -> Iterator[str]:
        if self.text:
            yield self.text

        for e in self:
            yield from e.itertext()
            if e.tail:
                yield e.tail

    @property
    def text_content(self) -> str:
        """
        Return the textual content of the element,
        with all html tags removed and whitespace-normalized.

        Example
        -------

        >>> import mechanize_mini.HtmlTree as HT
        >>> element = HT.HTML('<p>foo <i>bar    </i>\\nbaz</p>')
        >>> element.text_content
        'foo bar baz'
        """

        # let python walk the tree and get the text for us
        c = ET.tostring(self, method='text', encoding='unicode') # type: ignore

        # now whitespace-normalize.
        # FIXME: is ascii enough or should we dig into unicode whitespace here?
        return ' '.join(x for x in re.split('[ \t\r\n\f]+', c) if x != '')

    def __len__(self) -> int:
        return len(self._children)

    def __bool__(self) -> bool:
        # TODO: Python docs say something about deprecation, keep an eye on that
        return len(self._children) != 0

    def __getitem__(self, index):
        return self._children[index]

    def __setitem__(self, index: int, element: 'HtmlElement') -> None:
        self._children[index] = element

    def __delitem__(self, index: int) -> None:
        del self._children[index]


class _TreeBuildingHTMLParser(HTMLParser):
    default_scope_els = ['applet', 'caption', 'table', 'marquee', 'object', 'template']
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

        self.element_stack = [HtmlElement('html')]

        self.format_stack = [] # type: List[Tuple[str, Dict[str, str]]]

    def finish(self) -> HtmlElement:
        # remove whitespace-only text nodes before <head>
        if (len(self.element_stack[0]) > 0
                and self.element_stack[0][0].tag in ['head', 'body']
                and str(self.element_stack[0].text or '').strip() == ''):
            self.element_stack[0].text = ''

        # remove whitespace-only text after </body>
        if (len(self.element_stack[0]) > 0
                and self.element_stack[0][-1].tag in ['head', 'body']
                and str(self.element_stack[-1].tail or '').strip() == ''):
            self.element_stack[0][-1].tail = ''

        return self.element_stack[0]

    def has_in_scope(self, tag: str, scope_els: List[str]) -> bool:
        for i in reversed(self.element_stack):
            if i.tag == tag:
                return True

            if i.tag in scope_els:
                break

        return False

    def open_tag(self, tag: str, attrs: Dict[str, str] = {}) -> None:
        el = HtmlElement(tag, attrs)
        self.element_stack[-1].append(el)
        self.element_stack.append(el)

    def close_tag(self, tag: str) -> None:
        # close elements until we have reached the element on the stack

        # NOTE: currently, this is not called unless we have already made sure that
        # we actually can pop this element from the stack, which means the loop
        # condition cannot practically fail, it's just defensive programming at this point
        while len(self.element_stack) > 1: # pragma: no branch
            e = self.element_stack.pop()
            if e.tag == tag:
                break

    def restore_format_stack(self) -> None:
        fstack = self.format_stack[::-1]
        tstack = self.element_stack[::-1]

        while len(tstack) > 0 and len(fstack) > 0:
            while len(tstack) > 0 and tstack[-1].tag != fstack[-1][0]:
                tstack.pop()

            if len(tstack) > 0:
                assert tstack[-1].tag == fstack[-1][0]
                tstack.pop()
                fstack.pop()

        # tags are left on the format stack -> we must open them now
        while len(fstack) > 0:
            fel = fstack.pop()
            self.open_tag(fel[0], fel[1])


    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        # <html> is ignored, but its attributes will be merged with the implicit <html> tag
        if tag == 'html':
            for a, v in attrs:
                self.element_stack[0].set(a, v)

            return

        # fixup None attribute values
        for i in range(0, len(attrs)):
            if attrs[i][1] is None:
                attrs[i] = (attrs[i][0], attrs[i][0])

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
            self.restore_format_stack()
            self.format_stack.append((tag, dict(attrs)))

        # generate open tag
        self.open_tag(tag, dict(attrs))

        # self-closing tags get closed right away
        if tag in ["area", "br", "embed", "img", "keygen", "wbr", "input", "param",
                   "source", "track", "hr", "image", "base", "basefont", "bgsound",
                   "link", "meta", "col", "frame", "menuitem"]:
            self.close_tag(tag)

    # NOTE: this is NOT the "adoption agency algorithm" as specified by WHATWG, but has similar results
    def close_formatting_tag(self, tag: str, attrs: Dict[str, str]) -> None:
        # we always have <html> and at least one formatting element on the stack
        assert len(self.element_stack) >= 2

        if self.element_stack[-1].tag == tag:
            # we have found the original formatting tag, just pop it
            self.element_stack.pop()
        elif self.element_stack[-1].tag in self.formatting_els:
            # we have found a different formatting element, and we want to
            # keep the nesting order the same.
            # so we pop it, adjust the parent elements and then open it again.

            # pop
            el = self.element_stack.pop()

            # recurse
            self.close_formatting_tag(tag, attrs)

            # open the just popped formatting element again
            self.open_tag(str(el.tag), dict(el.items()))
        else:
            # we have a non-formatting element, e.g. a <div>
            # for this one, we actually remove it from the tree completely,
            # move all its children to a new formatting child and
            # append it again onto the fixed parent

            # temporarily remove top item from stack
            el = self.element_stack.pop()
            self.element_stack[-1].remove(el)

            # recurse
            self.close_formatting_tag(tag, attrs)

            # implant formatting tag(s) into element
            formatel = HtmlElement(tag, attrs)
            formatel.text = el.text
            formatel.extend(list(el))
            for child in list(el):
                el.remove(child)
            el.text = ''
            el.append(formatel)

            # push el on stack again
            self.element_stack[-1].append(el)
            self.element_stack.append(el)

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

        # formatting elements don't play by the normal rules, any misnesting must be
        # resolved in such a way that it renders the same as if a stateful renderer
        # just passed over the stream of tags.
        if tag in self.formatting_els:
            # ignore if we don't even have this on the format stack
            if not (tag in (x[0] for x in self.format_stack)):
                return

            # also, check if we actually have the element open right now.
            # if we don't that means our element has been closed because of misnesting
            if (tag in (e.tag for e in self.element_stack)):
                # some "harmless" cases of misnesting formatting elements can be solved by
                # just popping formatting elements from the stack
                while self.element_stack[-1].tag in self.formatting_els and self.element_stack[-1].tag != tag:
                    self.element_stack.pop()

                # if we found our element, stop right here
                if self.element_stack[-1].tag == tag:
                    self.element_stack.pop()
                else:
                    # this is the hard case: the misnested formatting crosses block-level
                    # elements, so we have to move items around
                    # Also, coverage.py misdetects this as a branch point
                    self.close_formatting_tag(tag, next(x[1] for x in reversed(self.format_stack) if x[0] == tag)) # pragma: no branch

            # remove from formatting stack
            index = len(self.format_stack) - 1 - [x[0] for x in self.format_stack][::-1].index(tag)
            del self.format_stack[index]
        else:
            # non-formatting elements
            # avoid prematurely closing tables
            if self.has_in_scope(tag, self.default_scope_els):
                self.close_tag(tag)

    def handle_data(self, data: str) -> None:
        self.restore_format_stack()

        el = self.element_stack[-1]
        if len(el):
            el[-1].tail = str(el[-1].tail or '') + data
        else:
            el.text = str(el.text or '') + data

class _CharsetDetectingHTMLParser(HTMLParser):
    """
    HTML Parser that does nothing but watch for ``<meta charset=... />`` tags
    """

    def __init__(self) -> None:
        super().__init__()

        self.charset = None # type: Optional[str]
        """The detected charset. May be :code:`None` if no charset is found"""

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        if self.charset is not None:
            return

        ad = dict(attrs)

        if tag == 'meta':
            if 'charset' in ad:
                self.charset = ad['charset']
            elif ('http-equiv' in ad and 'content' in ad
                     and ad['http-equiv'].lower() == 'content-type'
                     and ad['content'].lower().find('charset=') != -1):
                self.charset = ad['content'].lower().split('charset=')[-1].strip()


        # verify that we actually found a possible encoding.
        # if the encoding is invalid, look  for the next meta tag
        if self.charset is not None:
            try:
                codec = codecs.lookup(self.charset)
                # if the meta tag says UTF-16, silently treat it as UTF-8
                # because if we're at this point in the code, we can be
                # sure that we have an ASCII-compatible encoding.
                if codec.name.startswith('utf-16'):
                    self.charset = 'utf-8'

            except LookupError:
                self.charset = None


def detect_charset(html: bytes, charset: str = None) -> str:
    """
    Detects the character set of the given html file.

    This function will search for a BOM or the charset <meta> tag
    and return the name of the appropriate python codec.

    :param charset:
        Charset information obtained via external means, e.g. HTTP header.
        This will override any <meta> tag found in the document.

    .. note::
        * ISO-8859-1 and US-ASCII will always be changed to windows-1252
          (this is specified by WHATWG and browsers actually do this).
        * Encodings which the :any:`codecs` module does not know about are
          silently ignored.
        * The default encoding is :code:`windows-1252`.

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
        parser = _CharsetDetectingHTMLParser()
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
    if charset in ['iso8859-1', 'ascii']:
        charset = 'cp1252'

    return charset

def parsefragmentstr(html: str) -> HtmlElement:
    """
    Parse a HTML fragment into an element tree

    If the given fragment parses to just one element, this element
    is returned. If it parses to multiple sibling elements, a wrapping
    ``<html>`` element will be returned.
    """

    et = parsehtmlstr(html)
    if (len(et) == 1
                and et.text.strip() == ''
                and et[0].tail.strip() == ''):
        et[0].tail = ''
        return et[0]
    else:
        # if the fragment consisted of more than one element, this is the best
        # we can do besides throwing an error
        return et

def parsehtmlstr(html: str) -> HtmlElement:
    """
    Parse a complete HTML document into an element tree

    The root element will always be <html>, even if that was not actually
    present in the original page
    """

    # remove BOM
    if html[0:1] == '\uFEFF':
        html = html[1:]

    parser = _TreeBuildingHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.finish()

def parsefile(filename: str) -> HtmlElement:
    """
    Parse a HTML file into an element tree
    """
    with open(filename, 'rb') as f:
        return parsehtmlbytes(f.read())

def parsehtmlbytes(html: bytes, charset:str = None) -> HtmlElement:
    """
    Parse a HTML document into an element tree

    This function will also detect the encoding of the given document.

    :param str charset:
        Charset information obtained via external means, e.g. HTTP header.
        This will override any <meta> tag found in the document.
    """

    charset = detect_charset(html, charset)

    return parsehtmlstr(str(html, charset, 'replace'))

class ElementNotFoundError(Exception):
    """ No element has been found """

class TooManyElementsFoundError(Exception):
    """ One element was requested, but multiple were found """

def HTML(text: str) -> HtmlElement:
    """
    Parses a HTML fragment from a string constant. This function can be used to embed "HTML literals" in Python code
    """
    return parsefragmentstr(text)


TElement = TypeVar('TElement')
def _get_exactly_one(els: Iterator[TElement], n: int = None) -> TElement:
    # write complicated code here to not traverse the iterator more than necessary
    try:
        first = next(els)
    except StopIteration as e:
        raise ElementNotFoundError("Expected (at least) one element, got none") from e

    if n is None:
        try:
            next(els)
            raise TooManyElementsFoundError("Expected exactly one element, found a second one")
        except StopIteration:
            return first
    else:
        retval = first
        for i in range(1, n+1):
            try:
                retval = next(els)
            except StopIteration as e:
                raise ElementNotFoundError(
                    "Tried to retrieve element {n}, but found only {i}".format(n=n, i=i)) from e

        return retval
