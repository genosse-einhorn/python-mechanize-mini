import http.cookiejar
import urllib.request
import urllib.error
from urllib.parse import urljoin, urldefrag
import re
import xml.etree.ElementTree as ET
from . import HtmlTree as HT
from . import forms

from typing import List, Set, Dict, Tuple, Text, Optional, AnyStr, Union, Iterator, IO

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

        if ((page.status == 200) and not (page.document.getroot() is None)):
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

        self.charset = HT.detect_charset(self.response_bytes, response.headers.get_content_charset())
        """
        The encoding used to decode the page (str).

        The encoding is determined by looking at the HTTP Content-Type header,
        byte order marks in the document and <meta> tags, and applying various
        rules as specified by WHATWG (e.g. treating ASCII as windows-1252).
        """

        self.document = HT.parsehtmlstr(str(self.response_bytes, self.charset, 'replace')) # type: ET.ElementTree
        """
        The parsed document (:py:obj:`ET.ElementTree`)
        """

    @property
    def baseuri(self) -> str:
        """
        The base URI which relative URLs are resolved against.

        This is always an absolute URL, even if it
        was specified as a relative URL in the <base> tag.

        .. note::

            This read-only property is calculated from the ``<base>`` tag(s) present
            in the document. If you change the ``<base>`` tag in the :any:`document`,
            you will change this property, too.
        """

        base = self.url

        # NOTE: at the moment, the html parser cannot fail and will
        # always return something. This is just defensive programming here
        if not (self.document.getroot() is None): # pragma: no branch
            bases = self.document.findall('.//base[@href]')
            if len(bases) > 0:
                base = urljoin(self.url, bases[0].get('href').strip())

        return urldefrag(base).url

    @property
    def base(self) -> str:
        """ Alias for :any:`baseuri` """
        return self.baseuri

    @property
    def uri(self) -> str:
        """ Alias for :any:`url` (read-only str)"""
        return self.url

    def find_all_elements(self, *, context: ET.Element = None, tag: str = None,
            id: str = None, class_name: str = None, text: str = None) -> Iterator[ET.Element]:
        """
        Finds HTML elements in the given page. The keyowrd arguments specify
        search criteria which are evaluated in conjunction.

        **context** (:py:obj:`ET.Element`)
            Find only elements which are descendants of the given element
        **tag** (:py:obj:`str`)
            Find only elements with the given tag
        **id** (:py:obj:`str`)
            Find only elements with the given ``id`` attribute
        **class_name** (:py:obj:`str`)
            Find only elements where the ``class`` attribute contains the given class
        **text** (:py:obj:`str`)
            Find only elements where the whitespace-normalized text content
            (as returned by :any:`mechanize_mini.HtmlTree.text_content`)
            equals the given text.
        """

        if context is None:
            context = self.document.getroot()

        return HT.find_all_elements(context, tag=tag, id=id, class_name=class_name, text=text)

    def find_element(self, *, n: int = None, **kwargs) -> ET.Element:
        return HT._get_exactly_one(self.find_all_elements(**kwargs), n)

    def find_all_forms(self, *, context: ET.Element = None, id: str = None, name: str = None) -> Iterator[forms.Form]:
        """
        Finds <form> elements in the given page and returns :any:`forms.Form` instances

        The keyword arguments specify search criteria:

        **context** (:py:obj:`ET.Element`)
            Find only forms which are descendants of the given element
        **id** (:py:obj:`str`)
            Find only forms with the given ``id`` attribute (there should be only one)
        **name** (:py:obj:`str`)
            Find only forms with the given ``name`` attribute (usually, there is only one)
        """

        for i in self.find_all_elements(context=context, id=id, tag='form'):
            if name is not None:
                if i.get('name') != name:
                    continue

            yield forms.Form(i, self)

    def find_form(self, *, n:int = None, **kwargs) -> forms.Form:
        return HT._get_exactly_one(self.find_all_forms(**kwargs), n)

    # TODO: investigate usefulness of link type
    def find_all_links(self, *, context: ET.Element = None, id: str = None, class_name: str = None,
                       url: str = None, text: str = None) -> Iterator[ET.Element]:
        """
        Finds all matching hyperlinks (``<a href=...>``) in the document.

        Search critera are specified as keyword arguments:

        context (:py:obj:`ET.Element`)
            Return only hyperlinks which are descendants of the given element
        id (:py:obj:`str`)
            Return only hyperlinks with the given ``id`` attribute
        class_name (:py:obj:`str`)
            Return only hyperlinks with the given css class
        url (:py:obj:`str`)
            Return only hyperlinks where the ``href`` attribute equals the given string
        text (:py:obj:`str` or compiled regex pattern)
            Return only hyperlinks where the normalized link text (as returned
            by :any:`mechanize_mini.HtmlTree.text_content`) equals the given string
        """
        for i in self.find_all_elements(tag='a', context=context, id=id, class_name=class_name):
            if i.get('href') is None:
                continue

            if url is not None and i.get('href') != url:
                    continue

            if text is not None and HT.text_content(i) != text:
                continue

            yield i

    def find_link(self, *, n: int = None, **kwargs) -> ET.Element:
        """
        Like :any:`find_all_links`, but returns the n-th link found.

        Will raise an exception if n is None and more than one matching link has been found.
        """
        return HT._get_exactly_one(self.find_all_links(**kwargs), n)

    def follow_link(self, **kwargs) -> 'Page':
        """
        Like :any:`find_link`, but immediately opens the link.

        Returns the new page.
        """
        return self.open(self.find_link(**kwargs).get('href'))


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

