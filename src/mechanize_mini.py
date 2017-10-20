import http.cookiejar
import urllib.request
import urllib.error
from urllib.parse import urljoin, urldefrag, urlencode
import re
import codecs
import warnings
import xml.etree.ElementTree as ET
import xml.etree.ElementPath as ElementPath
from html.parser import HTMLParser
from functools import partial

from typing import List, Set, Dict, Tuple, Text, Optional, AnyStr, Union, Iterator, \
    IO, Sequence, Iterable, TypeVar, KeysView, ItemsView, cast, Callable

THtmlElement = TypeVar('THtmlElement', bound='HtmlElement')
T = TypeVar('T')
class HtmlElement(Sequence['HtmlElement']):
    """
    An HTML Element

    This is designed to be duck-compatible with :any:`xml.etree.ElementTree.Element`,
    but is extended with new additional methods
    """

    def __new__(cls, *args, **kwargs) -> 'HtmlElement':
        tag = args[0].lower()

        if (tag == 'option') and not issubclass(cls, HtmlOptionElement):
            return HtmlOptionElement(*args, **kwargs)

        if (tag == 'input') and not issubclass(cls, HtmlInputElement):
            return HtmlInputElement(*args, **kwargs)

        if (tag == 'textarea') and not issubclass(cls, HtmlTextareaElement):
            return HtmlTextareaElement(*args, **kwargs)

        if (tag == 'select') and not issubclass(cls, HtmlSelectElement):
            return HtmlSelectElement(*args, **kwargs)

        if (tag in ['form']) and not issubclass(cls, HtmlFormElement):
            return HtmlFormElement(*args, **kwargs)

        if (tag in ['a']) and not issubclass(cls, HtmlAnchorElement):
            return HtmlAnchorElement(*args, **kwargs)

        return super().__new__(cls)

    def __init__(self, tag: str, attrib: Dict[str,str] = {}, **extra) -> None:
        """
        Create a new Element.

        Note
        ----

        The :code:`HtmlElement` class overrides :code:`__new__` to create the appropriate
        element subclass, e.g. when you do :code:`HtmlElement('a')`, you will get a :any:`HtmlAnchorElement`
        """

        self.tag = tag # type: str
        """The element tag name (:any:`str`)"""

        self.attrib = attrib.copy() # type: Dict[str,str]
        """The element's attributes (dictionary str->str)"""

        self.text = '' # type: str
        """
        Element text before the first subelement.
        This is always a :any:`str`.
        """

        self.tail = '' # type: str
        """
        Text after this element's end tag up until the next sibling tag.
        This is always a :any:`str`.
        """

        self.attrib.update(extra)
        self._children = [] # type: List[HtmlElement]

    def makeelement(self: THtmlElement, tag: str, attrib:Dict[str,str]) -> THtmlElement:
        """ Etree API compatibility. Do not use. """
        warnings.warn("HtmlElement#makeelement is deprecated and only there for etree compatibility",
                      DeprecationWarning, stacklevel=2)
        return self.__class__(tag, attrib)

    def copy(self: THtmlElement) -> THtmlElement:
        """
        Make a shallow copy of current element.

        This is not very useful and only implemented for etree compatibility.
        """
        elem = self.__class__(self.tag, self.attrib)
        elem.text = self.text
        elem.tail = self.tail
        elem[:] = self
        return elem

    def append(self, subelement: 'HtmlElement') -> None:
        """
        Add a new child element

        >>> from mechanize_mini import HTML
        >>> el = HTML('<ul><li>a<li>b</ul>')
        >>> el.append(HTML('<li>c'))
        >>> el.outer_html
        '<ul><li>a</li><li>b</li><li>c</li></ul>'

        """
        self._children.append(subelement)

    def extend(self, elements: Iterable['HtmlElement']) -> None:
        """
        Add multiple elements

        >>> from mechanize_mini import HTML
        >>> el = HTML('<ul><li>a<li>b</ul>')
        >>> el.extend([HTML('<li>c'), HTML('<li>d')])
        >>> el.outer_html
        '<ul><li>a</li><li>b</li><li>c</li><li>d</li></ul>'
        """
        for element in elements:
            self.append(element)

    def insert(self, index: int, subelement: 'HtmlElement') -> None:
        """
        Insert a given child at the given position.

        >>> from mechanize_mini import HTML
        >>> el = HTML('<ul><li>a<li>b</ul>')
        >>> el.insert(1, HTML('<li>c'))
        >>> el.outer_html
        '<ul><li>a</li><li>c</li><li>b</li></ul>'
        """
        self._children.insert(index, subelement)

    def remove(self, subelement: 'HtmlElement') -> None:
        """
        Remove the given child element

        >>> from mechanize_mini import HTML
        >>> el = HTML('<ul><li>a<li>b<li>c</ul>')
        >>> el.remove(el[0])
        >>> el.outer_html
        '<ul><li>b</li><li>c</li></ul>'
        """
        self._children.remove(subelement)

    def getchildren(self) -> Sequence['HtmlElement']:
        warnings.warn("HtmlElement#getchildren() is deprecated and only here for etree compatibility."
                      "Use list(el) instead.",
                      DeprecationWarning, stacklevel=2)
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
        """
        Retrieves all descendant elements which satisfy all given conditions:

        Parameters
        ----------
        path
            XPath-esque element path. See TODO for the supported functionality.
        namespaces
            Accepted for compatibility with etree. The html parser does not use namespaces.
        id
            The element id, specified using the :code:`id` attribute in HTML.
        class_name
            The class name, specified in the :code:`class` attribute in HTML.
            TODO: Accept multiple classes
        text
            The text contained in the element, as returned by :any:`HtmlElement.text_content`

        Example
        -------
        >>> from mechanize_mini import HTML
        >>> doc = HTML('<ul><li class="a b">With <em>emphasis</em><li id="2">another one<li>third')
        >>> doc.findall('li') # doctest: +ELLIPSIS
        [<HtmlElement 'li' at 0x...>, <HtmlElement 'li' at 0x...>, <HtmlElement 'li' at 0x...>]
        >>> doc.findall('ul')
        []
        >>> [el.text_content for el in doc.findall('li', class_name='a')]
        ['With emphasis']
        >>> doc.find(id='2').text_content
        'another one'
        >>> doc.find(text='third').outer_html
        '<li>third</li>'
        """
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
        """
        Removes text, children and attributes from the element.

        Not very useful. Create a new element instead.
        """
        self.attrib.clear()
        self._children = []
        self.text = ''
        self.tail = ''

    def get(self, key: str, default:T=None) -> Union[str,T,None]:
        """
        Get an attribute value.

        Example
        -------
        >>> from mechanize_mini import HTML
        >>> el = HTML('<a href=http://example.com>Test</a>')
        >>> el.get('href')
        'http://example.com'
        >>> el.get('data-foo') is None
        True
        >>> el.get('data-foo', 'bar')
        'bar'
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
        """
        Returns an iterator over the current element and all its descendants
        which have the given tag (or any tag, if :code:`tag` is :any:`None`.

        Primarily implemented for etree compatibility, not necessarily useful in itself.
        """
        if tag == "*":
            tag = None

        if tag is None or self.tag == tag:
            yield self

        for e in self._children:
            yield from e.iter(tag)

    def getiterator(self, tag:str=None) -> List['HtmlElement']:
        """ Etree compatibility only. Do not use. """
        warnings.warn("HtmlElement#getiterator() is deprecated. Use list(el.iter()) instead.",
                      DeprecationWarning, stacklevel=2)
        return list(self.iter(tag))

    def itertext(self) -> Iterator[str]:
        """
        Returns an iterator over all texts contained in the element.

        Example
        -------

        >>> from mechanize_mini import HTML
        >>> el = HTML('Hey <b>Ho what\\'s</b> up?')
        >>> list(el.itertext())
        ['Hey ', "Ho what's", ' up?']

        """
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

        >>> from mechanize_mini import HTML
        >>> element = HTML('<p>foo <i>bar    </i>\\nbaz</p>')
        >>> element.text_content
        'foo bar baz'
        """

        # let python walk the tree and get the text for us
        c = ET.tostring(self, method='text', encoding='unicode') # type: ignore

        # now whitespace-normalize.
        # FIXME: is ascii enough or should we dig into unicode whitespace here?
        return ' '.join(x for x in re.split('[ \t\r\n\f]+', c) if x != '')

    @property
    def outer_html(self) -> str:
        """
        Serialize the element to valid HTML code

        Example
        -------

        >>> from mechanize_mini import HTML
        >>> el = HTML('<ul id=foo><li>hey<li>ho')
        >>> el.outer_html
        '<ul id="foo"><li>hey</li><li>ho</li></ul>'
        """

        # FIXME: mypy doesn't like duck typing here
        return ET.tostring(self, method='html', encoding='unicode') # type: ignore

    @property
    def id(self) -> Optional[str]:
        """
        Represents the ``id`` attribute on the element, or None if
        the attribute is not present
        """
        return self.get('id')

    @id.setter
    def id(self, id: str) -> None:
        self.set('id', id)

    @property
    def class_list(self) -> Set[str]:
        """
        The set of CSS classes applied to the element. Wraps the ``class``
        attribute as an immutable set.

        Example
        -------
        >>> from mechanize_mini import HTML
        >>> el = HTML('<p class="a c    b">');
        >>> el.class_list == {'a', 'b', 'c'}
        True
        >>> el.class_list = el.class_list | {'d'}
        >>> el.get('class')
        'a b c d'
        >>> el.class_list = el.class_list - set('c')
        >>> el.get('class')
        'a b d'
        >>> 'b' in el.class_list
        True
        >>> 'c' in el.class_list
        False
        """
        return set((self.get('class') or '').split())

    @class_list.setter
    def class_list(self, l: Iterable[str]) -> None:
        self.set('class', ' '.join(sorted(l)))

    def query_selector_all(self, sel: str) -> Iterator['HtmlElement']:
        """
        Returns all descendants matching the given CSS selector.
        The return value is an iterator that can be used in a for loop,
        if you want a list you'll need to call :any:`list` on it yourself.

        Note
        ----

        The following selectors are supported:

        * tag name selector (``div``)
        * class selector (``.my-class-name``)
        * id selector (``#my-id``)
        * universal selector (``*``)
        * descendant combination selector (``div p``)
        * child combination selector (``div > p``)
        * jQuery text selector (``span:contains(foo)``)
        """
        selector = _build_css_selector(lambda el: el, sel)
        yield from selector(self)

    def query_selector(self, sel: str) -> Optional['HtmlElement']:
        """
        Returns the first descendant matching the given CSS selector,
        or :any:`None` if no matching descendant has been found.

        See :any:`HtmlElement.query_selector_all` for the supported selectors.
        """
        return next(self.query_selector_all(sel), None)

    def __len__(self) -> int:
        return len(self._children)

    def __bool__(self) -> bool:
        warnings.warn("HtmlElement#__bool__() might not do what you think."
                      "Check for len(el) or el is None instead.",
                      DeprecationWarning, stacklevel=2)
        return len(self._children) != 0

    def __getitem__(self, index):
        return self._children[index]

    def __setitem__(self, index: int, element: 'HtmlElement') -> None:
        self._children[index] = element

    def __delitem__(self, index: int) -> None:
        del self._children[index]

    def __repr__(self) -> str:
        return '<{} {!r} at {:#x}>'.format(self.__class__.__name__, self.tag, id(self))

### CSS Selectors
_TMatcher = Callable[[HtmlElement], bool]
_TSelector = Callable[[HtmlElement], Iterable[HtmlElement]]

def _chain_selector(a: _TSelector, b: _TSelector) -> _TSelector:
    def wrap(el: HtmlElement) -> Iterator[HtmlElement]:
        for e in a(el):
            yield from b(e)
    return wrap

def _descendant_selector(match: _TMatcher) -> _TSelector:
    return _chain_selector(lambda el: el, _descendant_or_self_selector(match))

def _descendant_or_self_selector(match: _TMatcher) -> _TSelector:
    def sel(el: HtmlElement) -> Iterator[HtmlElement]:
        if match(el):
            yield el

        for child in el:
            yield from sel(child)
    return sel

def _immediate_child_selector(match: _TMatcher) -> _TSelector:
    def sel(el: HtmlElement) -> Iterator[HtmlElement]:
        for child in el:
            if match(child):
                yield child

    return sel

def _uniqueify_selector(inp: _TSelector) -> _TSelector:
    def sel(el: HtmlElement) -> Iterator[HtmlElement]:
        seen = set() # type: Set[int]

        for f in inp(el):
            if id(f) not in seen:
                seen |= {id(f)}
                yield f

    return sel

class InvalidSelectorError(Exception):
    """ The specified CSS selector is invalid """

def _matcher_and(a: Optional[_TMatcher], b: _TMatcher) -> _TMatcher:
    if a is not None: return lambda el: cast(_TMatcher, a)(el) and b(el)
    else: return b

def _matcher_tagname(tag: str) -> _TMatcher:
    return lambda el: el.tag == tag
def _matcher_class(classname: str) -> _TMatcher:
    return lambda el: classname in el.class_list
def _matcher_id(id: str) -> _TMatcher:
    return lambda el: el.id == id
def _matcher_contains(text: str) -> _TMatcher:
    return lambda el: text in el.text_content

def _build_css_selector(start: _TSelector, s: str) -> _TSelector:
    i = 0
    selgen = _descendant_or_self_selector
    sel = start
    matcher = None # type: Optional[_TMatcher]
    while i < len(s):
        match = re.match('''\*''', s[i:])
        if match: # universal selector
            matcher = _matcher_and(matcher, lambda el: True)
            i += len(match.group(0)); continue
        match = re.match('''[\w_-]+''', s[i:])
        if match: # tag selector
            matcher = _matcher_and(matcher, _matcher_tagname(match.group(0)))
            i += len(match.group(0)); continue
        match = re.match('''\.([\w_-]+)''', s[i:])
        if match: # class selector
            matcher = _matcher_and(matcher, _matcher_class(match.group(1)))
            i += len(match.group(0)); continue
        match = re.match('''#([\w_-]+)''', s[i:])
        if match: # id selector
            matcher = _matcher_and(matcher, _matcher_id(match.group(1)))
            i += len(match.group(0)); continue
        match = re.match(''':contains\(("([^"]+)"|([^")]+))\)''', s[i:])
        if match: # jQuery :contains selector
            matcher = _matcher_and(matcher, _matcher_contains(str(match.group(2) or match.group(3))))
            i += len(match.group(0)); continue
        match = re.match('''\s*\>\s*''', s[i:])
        if match and matcher: # immediate child
            sel = _chain_selector(sel, selgen(matcher))
            selgen = _immediate_child_selector
            matcher = None
            i += len(match.group(0)); continue
        match = re.match('''\s+''', s[i:])
        if match and matcher: # descendant
            sel = _chain_selector(sel, selgen(matcher))
            selgen = _descendant_selector
            matcher = None
            i += len(match.group(0)); continue;

        raise InvalidSelectorError("Unexpected selector at position {0}".format(i))

    if matcher is not None:
        sel = _chain_selector(sel, selgen(matcher))

    if sel is not start:
        return _uniqueify_selector(sel)
    else: # empty selector - return nothing
        return lambda el: []

class InputNotFoundError(Exception):
    """
    No matching ``<input>`` element has been found
    """

class UnsupportedFormError(Exception):
    """
    The <form> does weird things which the called method cannot handle, e.g.:

    * multiple input elements with the same name which are not radio buttons
    * multiple select options are selected where only one is expected
    * multiple radio buttons are selected
    """

class HtmlOptionElement(HtmlElement):
    """
    An ``<option>`` element
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @property
    def value(self) -> str:
        """
        The ``value`` associated with that option (read-only str)

        >>> from mechanize_mini import HTML
        >>> el = HTML('<option value=foo>bar</option>')
        >>> el.value
        'foo'
        >>> el = HTML('<option>bar</option>')
        >>> el.value
        'bar'

        """
        return self.get('value') or str(self.text)

    @property
    def selected(self) -> bool:
        """
        Whether the option is selected (bool, read-write)

        >>> from mechanize_mini import HTML
        >>> el = HTML('<option selected>bar</option>')
        >>> el.selected
        True
        >>> el = HTML('<option>bar</option>')
        >>> el.selected
        False
        >>> el.selected = True
        >>> el.outer_html
        '<option selected="selected">bar</option>'

        """
        return self.get('selected') is not None

    @selected.setter
    def selected(self, selected: bool) -> None:
        if selected:
            self.set('selected', 'selected')
        else:
            if self.get('selected') is not None:
                del self.attrib['selected']

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return '<{} value={!r} at {:#x}>'.format(self.__class__.__name__, self.value, id(self))

class HtmlOptionCollection(Sequence[HtmlOptionElement]):
    """
    Represents a list of ``<option>`` tags. You get this as :any:`HtmlSelectElement.options`.

    This is a sequence type (like a list), but you can also access options by their values.

    Example
    -------
    >>> from mechanize_mini import HTML
    >>> select = HTML('<select><option value=foo>bar1<option>bar</select>')
    >>> select.options[0] # doctest: +ELLIPSIS
    <HtmlOptionElement value='foo' at 0x...>
    >>> select.options[1] # doctest: +ELLIPSIS
    <HtmlOptionElement value='bar' at 0x...>
    >>> select.options['foo'] # doctest: +ELLIPSIS
    <HtmlOptionElement value='foo' at 0x...>
    >>> select.options['bar'] == select.options[1]
    True
    """
    def __init__(self, option_els: Iterable[HtmlElement]) -> None:
        self.__backing_list = [cast(HtmlOptionElement, el) for el in option_els]

    # FIXME: key is Union[str,int] -> HtmlOptionElement, but mypy doesn't like that
    def __getitem__(self, key):
        """
        Retrieve an option from the option list.

        In addition to slices and integers, you can also pass strings as key,
        then the option will be found by its value.
        """
        if isinstance(key, str):
            # find option by value
            for o in self.__backing_list:
                if o.value == key:
                    return o

            raise IndexError("No option with value '{0}' found".format(key))
        else:
            return self.__backing_list[key]

    def __len__(self) -> int:
        return len(self.__backing_list)

    def get_selected(self) -> Sequence[str]:
        """
        Returns a list of selected option values

        >>> from mechanize_mini import HTML
        >>> el = HTML('<select><option selected>a<option>b<option selected>c')
        >>> el.options.get_selected()
        ['a', 'c']
        """
        return [o.value for o in self if o.selected]

    def set_selected(self, values: Iterable[str]) -> None:
        """
        Selects all options with the given values (and unselects everything else)

        >>> from mechanize_mini import HTML
        >>> el = HTML('<select><option selected>a<option>b<option selected>c')
        >>> el.options.set_selected(['a', 'b'])
        >>> [o.selected for o in el.options]
        [True, True, False]
        """
        avail_values = {o.value for o in self}
        selected_values = set(values)

        illegal_values = selected_values - avail_values
        if len(illegal_values) > 0:
            raise UnsupportedFormError('the following options are not valid for this <select> element: ' + str(illegal_values))

        for o in self:
            o.selected = o.value in selected_values


class HtmlInputElement(HtmlElement):
    """
    Wraps an ``<input>`` element.

    Additionally, ``<select>`` and ``<textarea>`` elements are inherited from this class.
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @property
    def name(self) -> Optional[str]:
        """ The ``name`` attribute of the HTML element (if present, None otherwise) """
        return self.get('name')

    @name.setter
    def name(self, name: str) -> None:
        self.set('name', name)

    @property
    def type(self) -> str:
        """
        The type of the input element (read-only)

        This can be ``'select'``, ``'textarea'`` or any of the valid ``type=`` attributes
        for the html ``<input>`` element.
        """
        return (self.get('type') or 'text').lower().strip()

    @property
    def value(self) -> str:
        """
        The value associated with the HTML element

        * For a ``<select>`` element, this allows
          you to read the currently selected option or select exactly one of
          the available options.
        * For a ``<textarea>`` element, this is the element's content
        * For all other elements, this is the ``value`` attribute.

        Notes
        -----

        * For ``<select multiple>`` inputs, you might want to use :any:`HtmlSelectElement.options` instead.
        * If you want to select one of multiple radio buttons, look at :any:`HtmlFormElement.set_field`.
        * For checkboxes and radio buttons, you usually want to check them (:any:`HtmlInputElement.checked`)
          and not mess with their values.
        """
        if self.type in ['radio', 'checkbox']:
            return self.get('value') or 'on'
        else:
            return self.get('value') or ''

    @value.setter
    def value(self, val: str) -> None:
        self.set('value', val)

    @property
    def enabled(self) -> bool:
        """
        Whether the element is not disabled

        Wraps the ``disabled`` attribute of the HTML element.
        """
        return self.get('disabled') == None

    @enabled.setter
    def enabled(self, is_enabled: bool) -> None:
        if is_enabled:
            if self.get('disabled') is not None:
                del self.attrib['disabled']
        else:
            self.set('disabled', 'disabled')

    @property
    def checked(self) -> bool:
        """
        Whether a checkbox or radio button is checked.
        Wraps the ``checked`` attribute of the HTML element.

        This property is only applicable to checkboxes and radio buttons. For other
        inputs, this is always false and trying to set it will raise an :any:`UnsupportedFormError`
        """
        if self.type in ['checkbox', 'radio']:
            return self.get('checked') is not None
        else:
            return False

    @checked.setter
    def checked(self, is_checked: bool) -> None:
        if self.type not in ['checkbox', 'radio']:
            raise UnsupportedFormError('Only checkboxes and radio buttons can be checked')

        if is_checked:
            self.set('checked', 'checked')
        else:
            if self.get('checked') is not None:
                del self.attrib['checked']

class HtmlTextareaElement(HtmlInputElement):
    """
    Wraps a ``<textarea>`` element
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @property
    def type(self) -> str:
        """
        The type of the input element (read-only)

        For <textarea> elements, this is always ``'textarea'``
        """
        return 'textarea'

    @property
    def value(self) -> str:
        return self.text

    @value.setter
    def value(self, val: str) -> None:
        self.text = val

class HtmlSelectElement(HtmlInputElement):
    """
    Wraps a ``<select>`` element
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @property
    def type(self) -> str:
        """
        The type of the input element (read-only)

        For <select> elements, this is always ``'select'``
        """
        return 'select'

    @property
    def value(self) -> str:
        # return first option that is selected
        selected = [e for e in self.options if e.selected]

        if len(selected) == 1:
            return selected[0].get('value') or selected[0].text
        elif len(selected) == 0:
            # chrome returns the first option, unless there's no option then returns an empty string
            if len(self.options) > 0:
                return self.options[0].value
            else:
                return '' # yes, that's whats chrome returns
        else:
            raise UnsupportedFormError("More than one <option> is selected")

    @value.setter
    def value(self, val: str) -> None:
        self.options.set_selected([str(val)])

    @property
    def options(self) -> HtmlOptionCollection:
        """
        The ``<option>`` elements contained in this ``<select>`` element (as a :any:`HtmlOptionCollection`)
        """
        return HtmlOptionCollection(self.iterfind('.//option'))

class HtmlInputCollection(Sequence[HtmlInputElement]):
    """
    A list of form input elements. You get this from :any:`HtmlFormElement.elements`.

    This is a sequence type (like a list), but you can also access elements by their name

    Example
    -------
    >>> from mechanize_mini import HTML
    >>> el = HTML('''
    ...     <form>
    ...         <input name=foo value=bar>
    ...         <textarea name=baz>hohoho</textarea>
    ...     </form>
    ... ''')
    >>> # accessing by index
    >>> el.elements[0].name
    'foo'
    >>> el.elements[1].value
    'hohoho'
    >>> # access by name
    >>> el.elements['foo'].value
    'bar'
    >>> # insert new element
    >>> el.append(HTML('<input name=a>'))
    >>> el.elements[2].name
    'a'
    >>> el.elements['a'] == el.elements[2]
    True
    """
    def __init__(self, option_els: Iterable[HtmlElement]) -> None:
        self.__backing_list = [cast(HtmlInputElement, el) for el in option_els]

    # FIXME: key is Union[str,int] -> HtmlInputElement, but mypy doesn't like that
    def __getitem__(self, key):
        """
        Retrieve an option from the option list.

        In addition to slices and integers, you can also pass strings as key,
        then the option will be found by its value.
        """
        if isinstance(key, str):
            # find option by value
            for o in self.__backing_list:
                if o.name == key:
                    return o

            raise IndexError("No element with name '{0}' found".format(key))
        else:
            return self.__backing_list[key]

    def __len__(self) -> int:
        return len(self.__backing_list)


class HtmlFormElement(HtmlElement):
    """
    A ``<form>`` element inside a document.
    """

    def __init__(self, *args, **kwargs) -> None:
        """
        Constructs a new :any:`HtmlFormElement` instance.

        .. note::

            You'll want to use :any:`Page.forms` instead

        """

        super().__init__(*args, **kwargs)

        self.page = None # type: Optional[Page]
        """
        The :any:`Page` which contains the form.
        Might be :any:`None`, if the element was constructed outside of a
        browser request.
        """

    @property
    def name(self) -> Optional[str]:
        """
        Represents the ``name`` attribute on the <form> element, or None if
        the attribute is not present (read-only)
        """
        return self.get('name')

    @property
    def action(self) -> str:
        """
        Returns the form target, which is either the ``target`` attribute
        of the ``<form>`` element, or if the attribute is not present,
        the url of the containing page (read-only).

        If no target could be determined, then the return value is an empty string.
        """
        action = self.get('action') or ''

        if self.page is not None:
            if action == '':
                # HTML5 spec tells us NOT to use the base url
                action = self.page.url
            else:
                action = urljoin(self.page.base, action)

        return action

    @property
    def method(self) -> str:
        """
        The forms submit method, which is ``GET`` or ``POST``.

        The ``method`` attribute of the ``<form>`` element specifies this,
        the default if this attribute is missing or malformed is ``GET``.
        """
        method = self.get('method') or ''
        if method.upper() == 'POST':
            return 'POST'
        else:
            return 'GET'

    @property
    def enctype(self) -> str:
        """
        The MIME type for submitted form data.

        Currently, this is hardcoded to ``application/x-www-form-urlencoded``
        because it is the only supported format.

        In the future, this will look at the ``<form>``'s ``enctype`` attribute,
        but it will only return supported mime types and return the default
        value for unsupported mime types.
        """
        return 'application/x-www-form-urlencoded'

    @property
    def accept_charset(self) -> str:
        """
        The encoding used to submit the form data

        Can be specified with the ``accept-charset`` attribute, default is the page charset
        """
        a = str(self.get('accept-charset') or '')
        if a != '':
            try:
                return codecs.lookup(a).name
            except LookupError:
                pass

        if self.page is not None:
            return self.page.charset

        return 'utf-8' # best guess

    @property
    def elements(self) -> HtmlInputCollection:
        """
        The elements contained in the form as :any:`HtmlInputCollection`.
        """
        return HtmlInputCollection(x for x in self.iter() if isinstance(x, HtmlInputElement))

    def get_field(self, name: str) -> Optional[str]:
        """
        Retrieves the value associated with the given field name.

        * If all input elements with the given name are radio buttons, the value
          of the only checked one is returned (or ``None`` if no radio button is checked).
        * If the input with the given name is a ``<select>`` element, the value
          of the only selected option is returned (or ``None`` if no option is selected).
        * For all other elements, the ``value`` attribute is returned..
        * If no input element with the given name exists, ``None`` is returned.

        Raises
        ------
        UnsupportedFormError
            If there is more than one input element with the same name (and they
            are not all radio buttons), or if more than one option in a
            ``<select>`` element is selected, or more than one radio button is checked
        InputNotFoundError
            If no input element with the given name exists

        Notes
        -----

        * For ``<select multiple>`` inputs, you might want to use
          :any:`HtmlFormElement.elements` and :any:`HtmlSelectElement.options` instead.
        * If your form is particularly crazy, you will have to get your hands dirty
          and retrieve the element attributes yourself.

        """
        inputs = list(e for e in self.elements if e.name==name)
        if len(inputs) > 1:
            # check if they are all radio buttons
            if any(True for x in inputs if x.type != 'radio'):
                raise UnsupportedFormError(("Found multiple elements for name '{0}', "+
                                           "and they are not all radio buttons").format(name))

            # they are radio buttons, find the checked one
            checked = [x for x in inputs if x.checked]
            if len(checked) == 1:
                return checked[0].value
            elif len(checked) == 0:
                return None
            else:
                raise UnsupportedFormError("Multiple radio buttons with name '{0}' are selected".format(name))
        elif len(inputs) == 1:
            return inputs[0].value
        else:
            raise InputNotFoundError("No input with name `{0}' exists.".format(name))

    def set_field(self, name: str, value: str) -> None:
        """
        Sets the value associated with the given input name

        * If all input elements with the given name are radio buttons,
          the one with the given value is marked as checked and all other ones
          will be unchecked.
        * If the input with the given name is a ``<select>`` element, the option
          with the given value will be selected, and all other options will be unselected
        * For all other elements, the ``value`` attribute is changed.

        Raises
        ------

        UnsupportedFormError
            * There is more than one input element with the same name (and they
              are not all radio buttons)
            * There is no radio button with the given value
            * There is no option with the given value in a ``<select>`` element.
            * The input element is a checkbox (if you really want to change the
              value attribute of a checkbox, use :any:`HtmlInputElement.value`).

        InputNotFoundError
            if no input element with the given name exists


        Notes
        -----

        * For ``<select multiple>`` inputs, you might want to use
          :any:`HtmlFormElement.elements` and :any:`HtmlSelectElement.options` instead.
        * If your form is particularly crazy, you will have to get your hands dirty
          and set element attributes yourself.

        """
        inputs = list(e for e in self.elements if e.name == name)
        if len(inputs) > 1:
            # check if they are all radio buttons
            if any(True for x in inputs if x.type != 'radio'):
                raise UnsupportedFormError(("Found multiple elements for name '{0}', "+
                                           "and they are not all radio buttons").format(name))

            # they are radio buttons, find the correct one to check
            withval = [x for x in inputs if x.get('value') == value]
            if len(withval) >= 1:
                for i in inputs:
                    if i.get('checked') is not None:
                        del i.attrib['checked']

                withval[0].set('checked', 'checked')
            else:
                raise UnsupportedFormError("No radio button with value '{0}' exists".format(value))
        elif len(inputs) == 1:
            inputs[0].value = value
        else:
            raise InputNotFoundError('No <input> element with name=' + name + ' found.')

    def get_formdata(self) -> Iterator[Tuple[str,str]]:
        """
        Calculates form data in key-value pairs.

        This is the data that will be sent when the form is submitted.
        """
        for i in self.elements:
            if not i.enabled:
                continue

            if not i.name:
                continue

            type = i.type
            if type in ['radio', 'checkbox']:
                if i.checked:
                    yield (i.name or '', i.value or 'on')
            elif isinstance(i, HtmlSelectElement):
                for o in i.options:
                    if o.selected:
                        yield (i.name or '', o.value or '')
            else:
                yield (i.name or '', i.value or '')

    def get_formdata_query(self) -> str:
        """
        Get the query string (for submitting via GET)
        """
        # TODO: throw if multipart/form-data
        charset = self.accept_charset
        return urlencode([(name.encode(charset), val.encode(charset)) for name,val in self.get_formdata()])

    def get_formdata_bytes(self) -> bytes:
        """
        The POST data as stream
        """
        # TODO: multipart/form-data
        return self.get_formdata_query().encode('ascii')

    def submit(self) -> 'Page':
        assert self.page is not None # no chance of working otherwise

        if self.method == 'POST':
            return self.page.open(self.action, data=self.get_formdata_bytes(),
                                  additional_headers={'Content-Type': self.enctype})
        else:
            return self.page.open(urljoin(self.action, '?'+self.get_formdata_query()))


class HtmlAnchorElement(HtmlElement):
    """
    An <a> element
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.page = None # type: Page
        """
        The :any:`Page` this hyperlink belongs to (if any)
        """

    @property
    def href(self) -> str:
        """
        the link target as given by the 'href' attribute, or possibly
        an empty string if the href attribute is missing (read-only)
        """
        return self.get('href') or ''

    def follow(self) -> 'Page':
        """
        Open the link and return the retrieved target page
        """

        assert self.page is not None

        return self.page.open(self.href)

    def click(self) -> 'Page':
        """Alias for :any:`HtmlAnchorElement.follow`"""
        return self.follow()


class _TreeBuildingHTMLParser(HTMLParser):
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

def HTML(text: str) -> HtmlElement:
    """
    Parses a HTML fragment from a string constant. This function can be used to embed "HTML literals" in Python code
    """
    return parsefragmentstr(text)

class _NoHttpRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return None

class HTTPException(Exception):
    """
    Raised when the requested page responds with HTTP code != 200
    """
    def __init__(self, code: int, page: 'Page') -> None:
        super().__init__("HTTP/" + str(code))

        self.code = code # type: int
        """ The HTTP status code """

        self.page = page # type: Page
        """ The (parsed) response page """

class TooManyRedirectsException(HTTPException):
    """
    Raised when the maximum number of redirects for this request have been exceeded
    """

class Browser:
    """
    Represents a virtual web browser.

    The Browser class is not very useful in itself, it only houses the cookie storage
    and default settings for individual requests.

    .. note:: MiniMech strives to be as stateless as possible.
        In contrast to e.g. :code:`WWW::Mechanize`, MiniMech will give you a
        new :any:`Page` object for every page you open and every link you follow.

        There is no such thing as a current page or a browser history.

    """

    def __init__(self, ua: str) -> None:
        """
        Constructs a new :any:`Browser` instance

        Parameters
        ----------
        ua : str
            Value of the :code:`User-Agent` header. This parameter is mandatory.
            If you want to be honest and upright, you'd include the name of your
            bot, e.g. ``'MiniMech Documentation Example / rgcjonas@gmail.com'``,
            but you can also impersonate a real-world browser.

        """


        self.default_headers = {'User-Agent': ua} # type: Dict[str, str]
        """
        List of headers sent with every request.

        By default, this contains the ``User-Agent`` header only.
        """


        self.cookiejar = http.cookiejar.CookieJar() # type: http.cookiejar.CookieJar
        """
        Cookie jar to use for all requests.

        By default, this is a newly constructed :any:`http.cookiejar.CookieJar`,
        but you may replace it with your own compatible object.
        """

    def open(self, url: str, *, additional_headers: Dict[str, str] = {},
             maximum_redirects: int = 10, data: bytes = None) -> 'Page':
        """
        Navigates to :code:`url` and returns a new :any:`Page` object.

        Parameters
        ----------
        url:
            The URL to open. This must be an absolute URL.

        additional_headers:
            Additional HTTP headers to append to this request

        maximum_redirects:
            Maximum number of redirects to follow for this request.

            In addition to standard HTTP/3xx redirects, MiniMech can follow serveral
            braindead redirect techniques that have been seen in the wild, e.g.
            HTTP/200 with `<meta http-equiv="Refresh" ...`

            Note: If your browser redirects something and MiniMech does not, then this
            is a bug and you should report it.

            If the allowed number of redirects is exceeded, a :any:`TooManyRedirectsException` will be thrown.
        data:
            POST data. If this is not ``None``, a POST request will be performed with the given
            data as content. If data is ``None`` (the default), a regular GET request is performed

        Notes
        -----

        *   Anything but a final HTTP/200 response will raise an exception.
        *   This function supports HTML responses only, and will try to parse anything it gets back as HTML.

        """

        opener = urllib.request.build_opener(_NoHttpRedirectHandler, urllib.request.HTTPCookieProcessor(self.cookiejar))

        request = urllib.request.Request(url, data=data)
        for header, val in self.default_headers.items():
            request.add_header(header, val)

        for header, val in additional_headers.items():
            request.add_header(header, val)

        try:
            response = opener.open(request) # type: Union[urllib.request.HTTPResponse, urllib.error.HTTPError, urllib.request.addinfourl]
        except urllib.error.HTTPError as r:
            response = r

        page = Page(self, response)
        redirect_to = None # type: Union[None, str]
        if (page.status in [301, 302, 303, 307]) and ('Location' in page.headers):
            # standard redirects
            redirect_to = page.headers['Location'].strip()

        if (page.status == 200) and (('Refresh' in page.headers)):
            # really brainded Refresh redirect
            match = re.fullmatch('\s*\d+\s*;\s*[uU][rR][lL]\s*=(.+)', page.headers['Refresh'])
            if match:
                redirect_to = match.group(1).strip()

                # referer change
                additional_headers = {**additional_headers, 'Referer': urldefrag(page.url).url}

        if ((page.status == 200) and not (page.document is None)):
            # look for meta tag
            for i in page.document.iter('meta'):
                h = str(i.get('http-equiv') or '')
                c = str(i.get('content') or '')
                match = re.fullmatch('\s*\d+\s*;\s*[uU][rR][lL]\s*=(.+)', c)
                if h.lower() == 'refresh' and match:
                    # still shitty meta redirect
                    redirect_to = match.group(1).strip()

                    # referer change
                    additional_headers = {**additional_headers, 'Referer': urldefrag(page.url).url}

        if redirect_to:
            if maximum_redirects > 0:
                return page.open(redirect_to, additional_headers=additional_headers, maximum_redirects=maximum_redirects-1)
            else:
                raise TooManyRedirectsException(page.status, page)
        elif page.status == 200:
            return page
        else:
            raise HTTPException(page.status, page)

class Page:
    """
    Represents a retrieved HTML page.

    .. note:: You don't want to construct a :any:`Page` instance yourself.

        Get it from  :any:`Browser.open` or :any:`Page.open`.

    Arguments
    ---------
    browser : Browser
        The :any:`Browser` instance

    response :
        A response object as retrieved from :any:`urllib.request.urlopen`

    """

    def __init__(self, browser: Browser, response) -> None:
        self.browser = browser
        """ The :any:`Browser` used to open this page  """

        self.status = response.getcode() # type: int
        """
        The HTTP status code received for this page (integer, read-only)
        """

        self.headers = response.info() # type: Dict[str, str]
        """
        The HTTP headers received with this page

        Note: This is a special kind of dictionary which is not case-sensitive
        """

        self.url = response.geturl() # type: str
        """ The URL to this page (str, read-only)"""

        self.response_bytes = response.read()
        """ The raw http response content, as a bytes-like object. """

        self.charset = detect_charset(self.response_bytes, response.headers.get_content_charset())
        """
        The encoding used to decode the page (str).

        The encoding is determined by looking at the HTTP Content-Type header,
        byte order marks in the document and <meta> tags, and applying various
        rules as specified by WHATWG (e.g. treating ASCII as windows-1252).
        """

        self.document = parsehtmlstr(str(self.response_bytes, self.charset, 'replace')) # type: HtmlElement
        """
        The parsed document (:any:`HtmlElement`)
        """

        # fixup form page backreferences
        for f in self.forms:
            f.page = self

        # fixup hyperlink references
        for a in self.iterfind('.//a'):
            cast(HtmlAnchorElement, a).page = self

    @property
    def baseuri(self) -> str:
        """
        The base URI which relative URLs are resolved against.

        This is always an absolute URL, even if it
        was specified as a relative URL in the <base> tag.

        .. note::

            This read-only property is calculated from the ``<base>`` tag(s) present
            in the document. If you change the ``<base>`` tag in the :any:`Page.document`,
            you will change this property, too.
        """

        base = self.url

        # NOTE: at the moment, the html parser cannot fail and will
        # always return something. This is just defensive programming here
        if not (self.document is None): # pragma: no branch
            bases = self.document.findall('.//base[@href]')
            if len(bases) > 0:
                base = urljoin(self.url, (bases[0].get('href') or '').strip())

        return urldefrag(base).url

    @property
    def base(self) -> str:
        """ Alias for :any:`baseuri` """
        return self.baseuri

    @property
    def uri(self) -> str:
        """ Alias for :any:`Page.url` (read-only str)"""
        return self.url

    def query_selector(self, sel: str) -> Optional[HtmlElement]:
        """
        First element matching the selector, or :any:`None`.

        See: :any:`HtmlElement.query_selector`
        """
        return next(self.query_selector_all(sel), None)

    def query_selector_all(self, sel: str) -> Iterator[HtmlElement]:
        """
        Iterator over all elements matching the given CSS selector.

        See: :any:`HtmlElement.query_selector_all`
        """
        selector = _build_css_selector(lambda el: [el], sel)
        yield from selector(self.document)

    def find(self, path:str='.//', namespaces:Dict[str,str]=None, **kwargs) -> Optional[HtmlElement]:
        return self.document.find(path, namespaces, **kwargs)

    def findall(self, path:str='.//', namespaces:Dict[str,str]=None, **kwargs) -> List[HtmlElement]:
        return self.document.findall(path, namespaces, **kwargs)

    def iterfind(self, path:str='.//', namespaces:Dict[str,str]=None, **kwargs) -> Iterator[HtmlElement]:
        return self.document.iterfind(path, namespaces, **kwargs)

    @property
    def forms(self) -> 'HtmlFormsCollection':
        return HtmlFormsCollection(self.document.iterfind('.//form'))

    def open(self, url: str, **kwargs) -> 'Page':
        """
        Opens another page as if it was linked from the current page.

        Relative URLs are resolved properly, and a :code:`Referer` [sic] header
        is added (unless overriden in an ``additional_headers`` argument).
        All keyword arguments are forwarded to :any:`Browser.open`.
        """

        headers = { 'Referer': urldefrag(self.url).url }
        if ('additional_headers' in kwargs):
            for header, val in kwargs['additional_headers'].items():
                headers[header] = val

        kwargs['additional_headers'] = headers

        return self.browser.open(urljoin(self.baseuri, url), **kwargs)

class HtmlFormsCollection(Sequence[HtmlFormElement]):
    """
    A list of <form> elements

    This is a sequence type (like a list), but you can also access elements by their name

    TODO: Example
    """
    def __init__(self, els: Iterable[HtmlElement]) -> None:
        self.__backing_list = [cast(HtmlFormElement, el) for el in els]

    # FIXME: key is Union[str,int] -> HtmlFormElement, but mypy doesn't like that
    def __getitem__(self, key):
        """
        Retrieve an option from the option list.

        In addition to slices and integers, you can also pass strings as key,
        then the option will be found by its value.
        """
        if isinstance(key, str):
            # find option by value
            for o in self.__backing_list:
                if o.name == key:
                    return o

            raise IndexError("No element with name '{0}' found".format(key))
        else:
            return self.__backing_list[key]

    def __len__(self) -> int:
        return len(self.__backing_list)
