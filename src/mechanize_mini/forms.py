"""
Filling out and submitting HTML forms
"""

import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from typing import List, Set, Dict, Tuple, Text, Optional, AnyStr, Union, IO, Sequence, Iterator, TYPE_CHECKING

from . import HtmlTree as HT

# HACK: Circular import is not needed at runtime, but the type checker requires it
if TYPE_CHECKING: # pragma: no cover
    from . import Browser, Page

class Input:
    """
    Wraps a ``<input>``, ``<select>`` or ``<textarea>`` element
    """
    def __init__(self, el: ET.Element) -> None:
        if el.tag not in ['input', 'select', 'textarea']:
            raise UnsupportedFormError("Input wrapper does not support element type `{0}'".format(el.tag))

        self.element = el
        """ The wrapped HTML element """

    @property
    def name(self) -> Optional[str]:
        """ The ``name`` attribute of the HTML element """
        return self.element.get('name')

    @name.setter
    def name(self, name: str) -> None:
        self.element.set('name', name)

    @property
    def id(self) -> Optional[str]:
        """ The ``id`` attribute of the HTML element """
        return self.element.get('id')

    @id.setter
    def id(self, id: str) -> None:
        self.element.set('id', id)

    @property
    def type(self) -> str:
        """
        The type of the input element (read-only)

        This can be ``'select'``, ``'textarea'`` or any of the valid ``type=`` attributes
        for the html ``<input>`` element.
        """
        return _get_input_type(self.element)

    @property
    def value(self) -> Optional[str]:
        """
        The value associated with the HTML element

        * If the input with the given name is a ``<select>`` element, this allows
          you to read the currently selected option or select exactly one op
          the available options.
        * For all other elements, this represents the ``value`` attribute.

        Raises
        ------

        UnsupportedFormError
            * When reading a value: More than one option is currently selected in a ``<select>`` element
            * When setting a value: There is no option with the given value in a ``<select>`` element.

        Notes
        -----

        * For ``<select multiple>`` inputs, you might want to use
          :any:`Form.find_input` and :any:`Input.set_selected_options` instead.
        * If you want to select one of multiple radio buttons, look at :any:`Form.set_field`
        * For checkboxes, you usually want to check them and not mess with their values
        """
        return _get_input_value(self.element)

    @value.setter
    def value(self, val: str) -> None:
        return _set_input_value(self.element, val)

    @property
    def enabled(self) -> bool:
        """
        Whether the element is not disabled

        Wraps the ``disabled`` attribute of the HTML element.
        """
        return self.element.get('disabled') == None

    @enabled.setter
    def enabled(self, is_enabled: bool) -> None:
        if is_enabled:
            if self.element.get('disabled') is not None:
                del self.element.attrib['disabled']
        else:
            self.element.set('disabled', 'disabled')

    @property
    def checked(self) -> bool:
        """
        Whether a checkbox or radio button is checked.
        Wraps the ``checked`` attribute of the HTML element.

        This property is only applicable to checkboxes and radio buttons.

        Raises
        ------

        UnsupportedFormError
            When you set the ``checked`` attribute on an input element which
            is neither a checkbox nor a radio button
        """
        if self.type in ['checkbox', 'radio']:
            return self.element.get('checked') is not None
        else:
            return False

    @checked.setter
    def checked(self, is_checked: bool) -> None:
        if self.type not in ['checkbox', 'radio']:
            raise UnsupportedFormError('Only checkboxes and radio buttons can be checked')

        if is_checked:
            self.element.set('checked', 'checked')
        else:
            if self.element.get('checked') is not None:
                del self.element.attrib['checked']

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
        for e in HT.find_all_elements(self.element, id=id):
            if e.tag not in ['input', 'select', 'textarea']:
                continue

            if name is not None and e.get('name') != name:
                continue

            if type is not None and _get_input_type(e) != type:
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

    def find_input(self, *, n = None, **kwargs) -> Input:
        return HT._get_exactly_one(self.find_all_inputs(**kwargs), n)

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
            * There is more than one input element with the same name (and they
              are not all radio buttons)
            * More than one option in a ``<select>`` element is selected
            * More than one radio button is checked
        InputNotFoundError
            * If no input element with the given name exists

        Notes
        -----

        * For ``<select multiple>`` inputs, you might want to use
          :any:`Form.find_input` and :any:`Input.get_selected_options` instead.
        * If your form is particularly crazy, you might have to get your hands dirty
          and get element attributes yourself.

        """
        inputs = list(self.__find_input_els(name=name))
        if len(inputs) > 1:
            # check if they are all radio buttons
            if any(True for x in inputs if _get_input_type(x) != 'radio'):
                raise UnsupportedFormError(("Found multiple elements for name '{0}', "+
                                           "and they are not all radio buttons").format(name))

            # they are radio buttons, find the checked one
            checked = [x for x in inputs if x.get('checked') != None]
            if len(checked) == 1:
                return checked[0].get('value')
            elif len(checked) == 0:
                return None
            else:
                raise UnsupportedFormError("Multiple radio buttons with name '{0}' are selected".format(name))
        elif len(inputs) == 1:
            return _get_input_value(inputs[0])
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
          :any:`Form.find_input` and :any:`Input.set_selected_options` instead.
        * If your form is particularly crazy, you might have to get your hands dirty
          and set element attributes yourself.

        """
        inputs = list(self.__find_input_els(name=name))
        if len(inputs) > 1:
            # check if they are all radio buttons
            if any(True for x in inputs if _get_input_type(x) != 'radio'):
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
            return _set_input_value(inputs[0], value)
        else:
            raise InputNotFoundError('No <input> element with name=' + name + ' found.')

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
    def __init__(self, selectEl: ET.Element, value: str) -> None:
        super().__init__('Tried to set value to "{0}", but no <option> is available'.format(value))

        self.select = selectEl
        """ The select element """

        self.value = value
        """ The value that was supposed to be set """

def _get_input_value(el: ET.Element) -> Optional[str]:
    type = _get_input_type(el)
    if type == 'select':
        # return only option that is selected
        selected = [e for e in el.iter('option') if e.get('selected') is not None]

        if len(selected) == 1:
            return selected[0].get('value', selected[0].text)
        elif len(selected) == 0:
            return None
        else:
            raise UnsupportedFormError("More than one <option> is selected")
    elif type == 'textarea':
        return el.text
    elif type in ['radio', 'checkbox']:
        return el.get('value', 'on')
    else:
        return el.get('value', '')

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

def _get_input_type(el: ET.Element) -> str:
    if el.tag == 'select':
        return 'select'
    elif el.tag == 'textarea':
        return 'textarea'
    else:
        return el.get('type', 'text').lower().strip()
