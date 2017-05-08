"""
Filling out and submitting HTML forms
"""

import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from typing import List, Set, Dict, Tuple, Text, Optional, AnyStr, Union, IO, Sequence, Iterator, TYPE_CHECKING

from . import HtmlTree as HT

# HACK: Circular import is not needed at runtime, but the type checker needs it
if TYPE_CHECKING: # pragma: no cover
    from . import Browser, Page

class Input:
    """
    Wraps a ``<input>``, ``<select>`` or ``<textarea>`` element
    """
    def __init__(self, el: ET.Element) -> None:
        self.element = el
        """ The wrapped HTML element """

class Form:
    """
    Wraps a ``<form>`` inside a document.

    . note::

        This is a thin wrapper around the document nodes. All data is read from
        and written into the html elements.

    """

    def __init__(self, el: ET.Element, page: 'Page') -> None:
        """
        Constructs a new :any:`Form` instance.

        . note::

            Most of the time, you'll want to use :any:`Page.find_form` instead

        """

        self.element = el
        """
        The ``<form>`` element for this form
        """

        self.page = page
        """
        The :any:`Page` which contains the form
        """

    @property
    def name(self) -> Optional[str]:
        """
        Represents the ``name`` attribute on the <form> element, or None if
        the attribute is not present (read-only)
        """
        return self.element.get('name')

    @property
    def id(self) -> Optional[str]:
        """
        Represents the ``id`` attribute on the <form> element, or None if
        the attribute is not present (read-only)
        """
        return self.element.get('id')

    @property
    def action(self) -> str:
        """
        returns the form target, which is either the ``target`` attribute
        of the ``<form>`` element, or if the attribute is not present,
        the url of the containing page (read-only)
        """
        action = self.element.get('action', '')
        if action == '':
            # HTML5 spec tells us NOT to use the base url
            return self.page.url
        else:
            return urljoin(self.page.base, action)

    @property
    def method(self) -> str:
        """
        The forms submit method, which is ``GET`` or ``POST``
        """
        method = self.element.get('method', '')
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

    def __find_input_els(self, *, name: str = None, id: str = None,
                         type: str = None, enabled: bool = None,
                         checked: bool = None) -> Iterator[ET.Element]:
        for e in self.page.find_all_elements(context = self.element):
            if e.tag not in ['input', 'select', 'textarea']:
                continue

            if name is not None and e.get('name') != name:
                continue

            if id is not None and e.get('id') != id:
                continue

            if type == 'select' and e.tag != 'select':
                continue
            elif type == 'textarea' and e.tag != 'textarea':
                continue
            elif type is not None and type != e.get('type', 'text'):
                continue

            if enabled is not None:
                if enabled and e.get('disabled') is not None:
                    continue
                elif not enabled and e.get('disabled') is None:
                    continue

            if checked is not None:
                if checked and e.get('checked') is None:
                    continue
                if not checked and e.get('checked') is not None:
                    continue

            yield e

    def find_all_inputs(self, *, name: str = None, id: str = None,
                        type: str = None, enabled: bool = None,
                        checked: bool = None) -> Iterator['Input']:
        return (Input(el) for el in self.__find_input_els(
            name=name, id=id, type=type, enabled=enabled, checked=checked))

    def get_value(self, name: str) -> Optional[str]:
        """
        Retrieves the value associated with the given input name.

        .. note::

            * If multiple input elements with the same name exist, the value
              of the first one will be returned
            * If no input element with the given name exists, ``None`` will be returned.
            * For ``<select>`` elements, only the first selected option will be returned,
              even if multiple options are selected. You might want to use
              :any:`Form.find_input` and :any:`Input.get_selected_options` instead.

        """
        try:
            return _get_input_value(next(self.__find_input_els(name=name)))
        except StopIteration:
            return None

    def set_value(self, name: str, value: str) -> None:
        """
        Sets the value associated with the given input name

        .. note::

            * If multiple input elements with the same name exist, the value
              of the first one will be set
            * If no input element with the given name exists,
              an :any:`InputNotFoundError` will be raised
            * For ``<select>`` elements, the first option with the given value
              will be selected, and all oter options will be deselected.
              If no option with the given value exists, an
              :any:`InvalidOptionError` will be raised.
        """
        try:
            return _set_input_value(next(self.__find_input_els(name=name)), value)
        except StopIteration:
            raise InputNotFoundError('No <input> element with name=' + name + ' found.')

class InputNotFoundError(Exception):
    """
    No matching ``<input>`` element has been found
    """

class InvalidOptionError(Exception):
    """
    Raised if you try to set a value for a <select> element for which there is
    no <option> element

    .. note::

        If you actually want to set that value, you can create an option element yourself.
    """
    def __init__(self, selectEl: ET.Element, value: str) -> None:
        super().__init__('Tried to set value to "{0}", but no <option> is available'.format(value))

        self.select = selectEl
        """ The select element """

        self.value = value
        """ The value that was supposed to be set """

def _get_input_value(el: ET.Element) -> Optional[str]:
    if el.tag == 'select':
        # return first option that is selected
        try:
            el = next((e for e in el.iter('option') if e.get('selected') is not None))
            return el.get('value', el.text)
        except StopIteration:
            return None
    elif el.tag == 'textarea':
        return el.text
    else:
        return el.get('value')

def _set_input_value(el: ET.Element, value: str) -> None:
    if el.tag == 'select':
        try:
            # find the option
            target = next((o for o in el.iter('option')
                if o.get('value', o.text) == value))

            # unselect all options
            for o in el.iter('option'):
                if o.get('selected') is not None:
                    del o.attrib['selected']

            # select the option we found out prior
            target.set('selected', 'selected')

        except StopIteration:
            raise InvalidOptionError(el, value)
    elif el.tag == 'textarea':
        el.text = value
    else:
        el.set('value', value)
