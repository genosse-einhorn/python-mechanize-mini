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

from urllib.parse import urljoin, urlencode
import xml.etree.ElementPath as ElementPath
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
import codecs
import re

from typing import List, Set, Dict, Tuple, Text, Optional, AnyStr, Union, IO, \
        Sequence, Iterator, Iterable, TypeVar, KeysView, ItemsView, cast, TYPE_CHECKING

# HACK: Circular import is not needed at runtime, but the type checker requires it
if TYPE_CHECKING: # pragma: no cover
    from . import Browser, Page

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

        if (tag in ['select', 'input', 'textarea']) and not issubclass(cls, HtmlInputElement):
            return HtmlInputElement(*args, **kwargs)

        if (tag in ['form']) and not issubclass(cls, HtmlFormElement):
            return HtmlFormElement(*args, **kwargs)

        return super().__new__(cls)

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

    @property
    def id(self) -> Optional[str]:
        """
        Represents the ``id`` attribute on the element, or None if
        the attribute is not present (read-only)
        """
        return self.get('id')

    @id.setter
    def id(self, id: str) -> None:
        self.set('id', id)

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

class InvalidOptionError(Exception):
    """
    Raised if you try to set a value for a <select> element for which there is
    no <option> element

    .. note::

        If you actually want to set that value, you can create an option element yourself.
    """
    def __init__(self, selectEl: HtmlElement, value: str) -> None:
        super().__init__('Tried to set value to "{0}", but no <option> is available'.format(value))

        self.select = selectEl
        """ The select element """

        self.value = value
        """ The value that was supposed to be set """


class HtmlOptionElement(HtmlElement):
    """
    An ``<option>`` element
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @property
    def value(self) -> str:
        """ The ``value`` associated with that option (read-only str) """
        return self.get('value') or str(self.text)

    @property
    def selected(self) -> bool:
        """ Whether the option is selected (bool, read-write) """
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

class HtmlOptionCollection(Sequence[HtmlOptionElement]):
    """
    Interface a list of ``<option>`` tags

    This is a sequence type (like a list), but you can also access options by their values

    TODO: Example
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
        """ Returns a list of selected option values """
        return [o.value for o in self if o.selected]

    def set_selected(self, values: Iterable[str]) -> None:
        """ Selects all options with the given values (and unselects everything else) """
        avail_values = {o.value for o in self}
        selected_values = set(values)

        illegal_values = selected_values - avail_values
        if len(illegal_values) > 0:
            raise UnsupportedFormError('the following options are not valid for this <select> element: ' + str(illegal_values))

        for o in self:
            o.selected = o.value in selected_values


class HtmlInputElement(HtmlElement):
    """
    Wraps an ``<input>``, ``<select>`` or ``<textarea>`` element
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @property
    def name(self) -> Optional[str]:
        """ The ``name`` attribute of the HTML element """
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
        if self.tag == 'select':
            return 'select'
        elif self.tag == 'textarea':
            return 'textarea'
        else:
            return (self.get('type') or 'text').lower().strip()

    @property
    def value(self) -> Optional[str]:
        """
        The value associated with the HTML element

        * If the input with the given name is a ``<select>`` element, this allows
          you to read the currently selected option or select exactly one of
          the available options.
        * For all other elements, this represents the ``value`` attribute.

        Notes
        -----

        * For ``<select multiple>`` inputs, you might want to use
          :any:`Form.find_input` and :any:`Input.options` instead.
        * If you want to select one of multiple radio buttons, look at :any:`Form.set_field`
        * For checkboxes, you usually want to check them and not mess with their values
        """
        type = self.type
        if type == 'select':
            # return first option that is selected
            selected = [e for e in self.iter('option') if e.get('selected') is not None]

            if len(selected) == 1:
                return selected[0].get('value', selected[0].text)
            elif len(selected) == 0:
                return None
            else:
                raise UnsupportedFormError("More than one <option> is selected")
        elif type == 'textarea':
            return self.text
        elif type in ['radio', 'checkbox']:
            return self.get('value', 'on')
        else:
            return self.get('value', '')

    @value.setter
    def value(self, val: str) -> None:
        if self.type == 'select':
            self.options.set_selected([str(val)])
        elif self.type == 'textarea':
            self.text = val
        else:
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

        This property is only applicable to checkboxes and radio buttons.
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

    @property
    def options(self) -> HtmlOptionCollection:
        """
        Options available for a <select> element

        Raises
        ------
        UnsupportedFormError
            If the input is not a <select> element
        """
        if self.type != 'select':
            raise UnsupportedFormError('options is only available for <select> inputs')

        return HtmlOptionCollection(self.iterfind('.//option'))

class HtmlInputCollection(Sequence[HtmlInputElement]):
    """
    A list of form input elements

    This is a sequence type (like a list), but you can also access elements by their name

    TODO: Example
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
        Constructs a new :any:`Form` instance.

        .. note::

            Most of the time, you'll want to use :py:obj:`Page.find_form` instead

        """

        super().__init__(*args, **kwargs)

        self.page = None # type: Optional[Page]
        """
        The :py:obj:`Page` which contains the form. Might be None.
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
        returns the form target, which is either the ``target`` attribute
        of the ``<form>`` element, or if the attribute is not present,
        the url of the containing page (read-only)
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
        The forms submit method, which is ``GET`` or ``POST``
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
        The elements contained in the form
        """
        return HtmlInputCollection(x for x in self.iter() if isinstance(x, HtmlInputElement))

    def get_field(self, name: str) -> Optional[str]:
        """
        Retrieves the value associated with the given field name.

        * If all input elements with the given name are radio buttons, the value
          of only checked one is returned (or ``None`` if no radio button is checked).
        * If the input with the given name is a ``<select>`` element, the value
          of the selected option is returned (or ``None`` if no option is
          selected).
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
          :any:`Form.find_input` and :any:`Input.options` instead.
        * If your form is particularly crazy, you might have to get your hands dirty
          and get element attributes yourself.

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
              value attribute of a checkbox, use :any:`Input.value`).

        InputNotFoundError
            if no input element with the given name exists

        Notes
        -----

        * For ``<select multiple>`` inputs, you might want to use
          :any:`Form.find_input` and :any:`Input.options` instead.
        * If your form is particularly crazy, you might have to get your hands dirty
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
        Calculates form data in key-value pairs

        This is the data that will be sent when the form is submitted
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
            elif type == 'select':
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
