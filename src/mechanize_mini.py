import http.cookiejar
import urllib.request
import urllib.error
from urllib.parse import urljoin
import xml.etree.ElementTree as ET
import htmltree_mini as HT


from typing import List, Set, Dict, Tuple, Text, Optional, AnyStr, Union

class _NoHttpRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return None


class TooManyRedirectsException(Exception):
    """
    The maximum number of redirects for this request have been exceeded
    """

class HTTPException(Exception):
    """
    Raised when the requested page respons with HTTP code != 200
    """
    def __init__(self, code: int, page: 'Page') -> None:
        super().__init__("HTTP/" + str(code))

        self.code = code # type: int
        """ The HTTP status code """

        self.page = page # type: Page
        """ The (parsed) response page """

class Browser:
    """
    Represents a virtual web browser.

    The Browser class is not very useful in itself, it only houses the cookie storage
    and default settings for individual requests.

    .. note:: MiniMech strives to be as stateless as possible
        In contrast to e.g. :code:`WWW::Mechanize`, MiniMech will give you a
        new :any:`Page` object for every page you open and every link you follow.

        There is no such thing as a current page or a browser history.
    """

    def __init__(self, ua: str) -> None:
        """
        Creates a new Browser instance.

        Parameters
        ----------

        ua : str
            Value of the :code:`User-Agent` header. This parameter is mandatory.
            If you want to be honest and upright, you'd include the name of your
            bot, e.g. :code:`MiniMech Documentation Example / rgcjonas@gmail.com`,
            but you can also impersonate a real-world browser.
        """

        self.default_headers = {'User-Agent': ua} # type: Dict[str, str]
        """ List of headers sent with every request """

        self.cookiejar = http.cookiejar.CookieJar() # type: http.cookiejar.CookieJar
        """
        Cookie jar to use for all requests.

        By default, this is a newly constructed :any:`http.cookiejar.CookieJar`,
        but you may replace it with your own compatible object.
        """

    def open(self, url: str, additional_headers: Dict[str, str] = {}, maximum_redirects: int = 10) -> 'Page':
        """
        Navigates to :code:`url` and returns a new :any:`Page` object.

        Parameters
        ----------
        url
            The URL to open. This must be an absolute URL.

        additional_headers
            Additional HTTP headers to append to this request

        maximum_redirects
            Maximum number of redirects to follow for this request.

            In addition to standard HTTP/3xx redirects, MiniMech can follow serveral
            braindead redirect techniques that have been seen in the wild, e.g.
            HTTP/200 with `<meta http-equiv="Refresh" ...`

            Note: If your browser redirects something and MiniMech does not, then this
            is a bug and you should report it.

            If the allowed number of redirects is exceeded, an exception will be thrown.

        Additional Notes
        ----------------

        *   Anything but a final HTTP/200 response will raise an exception.
        *   This function supports HTML responses only, and will try to parse anything it gets back as HTML.
        """

        opener = urllib.request.build_opener(_NoHttpRedirectHandler, urllib.request.HTTPCookieProcessor(self.cookiejar))

        request = urllib.request.Request(url)
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
            redirect_to = page.headers['Refresh'].split(';')[-1].strip()

        if ((page.status == 200) and not (page.document.getroot() is None)
                and len(page.document.findall(".//meta[@http-equiv='Refresh']")) > 0):
            # still not so great redirect
            redirect_to = page.document.findall(".//meta[@http-equiv='Refresh']")[0].get('value').split(';')[-1].strip()

        if redirect_to:
            if maximum_redirects > 0:
                return page.open(redirect_to, additional_headers=additional_headers, maximum_redirects = maximum_redirects-1)
            else:
                raise TooManyRedirectsException("Too many redirects, stopped at " + url)
        elif page.status == 200:
            return page
        else:
            raise HTTPException(page.status, page)

class Page:
    """
    Represents a retrieved HTML page.
    """

    def __init__(self, browser: Browser, response) -> None:
        """
        Creates a new page instance.
        You should not call this yourself, instead, use :any:`Browser.open`.

        Parameters
        ----------
        browser
            The :any:`Browser` instance

        response
            A response object as retrieved from :any:`urllib.request.urlopen()`
        """

        self.browser = browser
        """
        The :any:`Browser` used to open this page
        """

        self.status = response.getcode() # type: int
        """ The HTTP status code received for this page """

        self.headers = dict(response.info()) # type: Dict[str, str]
        """ The HTTP headers received with this page """

        self.url = response.geturl() # type: str
        """ The URL to this page """

        self.document = HT.parsehtmlbytes(response.read(), response.headers.get_content_charset()) # type: ET.ElementTree
        """
        The parsed document
        """

    @property
    def baseuri(self) -> str:
        """
        The base URI where relative URLs are resolved against
        """
        if not (self.document.getroot() is None):
            bases = self.document.findall('.//base[@href]')
            if len(bases) > 0:
                return urljoin(self.url, bases[0].get('href'))


        return self.url

    @property
    def base(self) -> str:
        """ Alias for :any:`baseuri` """
        return self.baseuri

    @property
    def uri(self) -> str:
        """ Alias for :any:`url` """
        return self.url

    def open(self, url: str, **kwargs) -> 'Page':
        """
        Opens another page as if it was linked from the current page.

        Relative URLs are resolved properly, and a :code:`Referer` [sic] header
        is added. All additional arguments are forwarded to :any:`Browser.open`.
        """

        headers = { 'Referer': self.url }
        if ('additional_headers' in kwargs):
            for header, val in kwargs['additional_headers'].items():
                headers[header] = val

        kwargs['additional_headers'] = headers

        return self.browser.open(urljoin(self.baseuri, url), **kwargs)

