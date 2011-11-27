import urllib
import urllib2
import cookielib
import logging
from collections import OrderedDict
from BeautifulSoup import BeautifulSoup, NavigableString

logger = logging.getLogger("PyScrape")

class BrowserError(Exception):
    def __init__(self, msg="pyscrape.Browser encountered an error"):
        self.msg = msg
    def __str__(self):
        return self.msg

class HTTPRequestLogger(urllib2.BaseHandler):
    handler_order = 1000
    def http_request(self, request):
        logger.debug("HTTP %s: %s" % (request.get_method(), request.get_full_url()))
        data = request.get_data()
        if data:
            logger.debug("\tData: %s" % data)
        logger.debug("\tHeaders:")
        for k, v in request.header_items():
            logger.debug("\t\t%s: %s" % (k, v))
        return request
    https_request = http_request

# ------------------------------------------------------------------------------

class Browser(object):
    def __init__(self, userAgent="pyscrape/1.0"):
        self._userAgent = userAgent
        self._passwordManager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self._cookieJar = cookielib.CookieJar()

        self._opener = urllib2.build_opener(
            urllib2.HTTPCookieProcessor(self._cookieJar),
            urllib2.HTTPBasicAuthHandler(self._passwordManager),
            urllib2.HTTPDigestAuthHandler(self._passwordManager),
            HTTPRequestLogger(),
        )

        self.currentUrl = None
        self.page = None
        self.headers = {}
        self.soup = None
        self._forms = []

    def duplicate(self):
        """
        Return a duplicate of the browser with the current state.
        Usually used to call two follow_link's from the same page and to
        implement Back like behviour using a stack of Browser objects.
        The duplicate uses the same URL opener as the original and therefore
        is a rather light weight object.
        """
        browser = Browser.__new__(Browser)
        browser._opener = self._opener
        browser._userAgent = self._userAgent
        browser.currentUrl = self.currentUrl
        browser.page = self.page
        browser.soup = self.soup
        return browser

    def goto(self, url, postData=None, username=None, password=None, retries=3):
        """
        Goes to a URL, optionally passing it POST data.
        The loaded page can be accessed through self.page (as HTML text) and
        self.soup (as BeautifulSoup structure).
        """
        url = bytes(url, "ascii")
        if not url.startswith("http://") and not url.startswith("https://"):
            if self.currentUrl:
                url = urljoin(self.currentUrl, url)
            else:
                raise BrowserError("unknown url format, pass HTTP or HTTPS urls "
                    "or urls relative to current location (%s)" % (self.currentUrl))

        request = urllib2.Request(url)
        request.add_header("User-Agent", self._userAgent)

        # try several times to protect from short network problems
        while True:
            try:
                response = self._opener.open(request, postData)
                self.currentUrl = request.get_full_url()
                self.headers = response.info()
                self.page = response.read()
                self.soup = BeautifulSoup(self.page)
                self._forms = []
            except Exception:
                if retries <= 0:
                    raise
                import time
                time.sleep(1) # wait a second between retries
                retries -= 1
            else:
                break

        return self.currentUrl

    def follow_link(self, hrefContains):
        """
        Finds a link inside the current HTML page and goes to it.
        """
        assert(self.soup)
        return self.goto(self.get_link(hrefContains))

    def get_link(self, hrefContains):
        return self.get_links(hrefContains)[0]

    def get_links(self, hrefContains):
        """
        Finds links inside the current HTML page and returns their addresses.
        """
        assert(self.soup)
        aTags = self.soup.findAll("a", href=lambda v: v and hrefContains in v)
        if aTags:
            links = []
            for aTag in aTags:
                link = urljoin(self.currentUrl, aTag.get("href"))
                link = link.replace('&amp;','&')
                links.append(link)
            return links
        else:
            raise BrowserError("Can't find links containing '%s'" % hrefContains)

    def follow_frame(self, hrefContains):
        assert(self.soup)
        return self.goto(self.get_frame_link(hrefContains))

    def get_frame_link(self, hrefContains):
        return self.get_frame_links(hrefContains)[0]

    def get_frame_links(self, hrefContains):
        """
        Finds links inside the current HTML page and returns their addresses.
        """
        assert(self.soup)
        aTags = self.soup.findAll("frame", src=lambda v: v and hrefContains in v)
        if aTags:
            links = []
            for aTag in aTags:
                link = urljoin(self.currentUrl, aTag.get("src"))
                link = link.replace('&amp;','&')
                links.append(link)
            return links
        else:
            raise BrowserError("Can't find frame links containing '%s'" % hrefContains)

    @property
    def forms(self):
        assert(self.soup)
        if not self._forms:
            for formSoup in self.soup.findAll("form"):
                self._forms.append(Form(self, formSoup))
        return Forms(self._forms)

    def get_form(self, name):
        """
        Returns a Form object which can be used to submit form requests.
        """
        assert(self.soup)
        formSoup = self.soup.find("form", dict(name=name))
        if formSoup:
            return Form(self, formSoup)
        else:
            raise BrowserError("Can't find a form with name '%s'" % name)

    def sanitize(self, regexp):
        """
        Remove parts of the HTML using a regular expression and re-parse using
        BeautifulSoup. Use this if BeautifulSoup fails to parse the document
        correctly.
        """
        import re
        self.page = re.sub(regexp, "", self.page)
        self.soup = BeautifulSoup(self.page)

    def show_in_browser(self):
        """
        Saves the data of the current page in a temporary file and shows it in
        the default browser.
        """
        # use a separate soup for this because we're modifying it and don't want
        # to influence code that relies on self.soup
        soup = BeautifulSoup(self.page)

        # convert relative paths to absolute paths in all relevant tags
        relativeTags = [
            ("link", "href"),
            ("a", "href"),
            ("img", "src"),
            ("script", "src"),
            ("form", "action"),
        ]

        for tagName, attrName in relativeTags:
            for tag in soup.findAll(tagName):
                url = tag.get(attrName)
                if url:
                    absUrl = urljoin(self.currentUrl, url)
                    tag[attrName] = absUrl

        # add content type in the html
        if "Content-Type" in self.headers:
            headTag = soup.find("head")
            contentTypeTag = BeautifulSoup(
                '<meta http-equiv="content-type" content="%s">' %
                self.headers.get("Content-Type")
            )
            headTag.insert(0, contentTypeTag)

        # write page to temp file
        import tempfile
        import os
        (fno, tempName) = tempfile.mkstemp('.html', 'pyscrape-')
        os.close(fno)
        f = open(tempName, "w")
        f.write(str(soup))
        f.close()

        # display page in browser
        import webbrowser
        webbrowser.open(tempName)

    @property
    def title(self):
        return self.soup.find("title").string

# ------------------------------------------------------------------------------

class Forms(list):
    def get(self, name):
        forms = [form for form in self if form.id == name or form.name == name]
        if forms:
            return forms[0]
        return None

class Form(object):
    def __init__(self, browser, soup):
        self.name = soup.get("name")
        self.id = soup.get("id")
        self.browser = browser
        self.soup = soup
        self.fields = OrderedDict()
        self.submits = OrderedDict()
        self._load_defaults()
        self._update_submit_docstring()

    def submit(self, submitName=None, **kwargs):
        """
        Submits the form using arguments as form parameters. 'submitName' is
        the 'name' attribute of the submit input tag, useful if there is more
        than one submit button on the page.  Moves the parent Browser to the
        new page after successful submission.
        """
        return self._submit(submit=submitName, **kwargs)

    def _submit(self, submitName=None, **kwargs):
        action = urljoin(self.browser.currentUrl, self.soup.get("action"))
        fields = {}
        submitValue = None
        if submitName:
            submitValue = self.submits.get(submitName)
        elif len(self.submits) == 1:
            submitName, submitValue = self.submits.items()[0]
        elif len(self.submits) > 0:
            raise BrowserError("No submit name provided, use one of [%s]" % ", ".join(self.submits.keys()))
        if submitValue:
            fields[submitName] = submitValue
        fields.update(self.fields)
        fields.update(kwargs)
        fields = dict((bytes(k), bytes(v)) for (k, v) in fields.items() if v is not None)
        postData = urllib.urlencode(fields)
        self.browser.goto(action, postData)
        return self.browser.soup

    def _load_defaults(self):
        """
        Loads the default values for the form from the HTML.
        """
        # get default values for input self.fields
        for inputTag in self.soup.findAll("input"):
            name = inputTag.get("name")
            value = inputTag.get("value")
            inputType = inputTag.get("type")
            disabled = (inputTag.get("disabled") == "disabled")
            if name and not disabled:
                if inputType == "submit":
                    self.submits[name] = htmlentitiesdecode(value)
                elif inputType not in ["button"]:
                    self.fields[name] = htmlentitiesdecode(value)

        # get default values for textarea self.fields
        for textTag in self.soup.findAll("textarea"):
            name = textTag.get("name")
            value = textTag.get("value")
            disabled = (textTag.get("disabled") == "disabled")
            if name and not disabled:
                self.fields[name] = htmlentitiesdecode(value)

        # get default values for select self.fields
        for selectTag in self.soup.findAll("select"):
            name = selectTag.get("name")
            disabled = (inputTag.get("disabled") == "disabled")
            if name and not disabled:
                value = None
                for optionTag in selectTag.findAll("option"):
                    if optionTag.get("selected") == "selected":
                        value = optionTag.get("value").strip()
                if value:
                    self.fields[name] = htmlentitiesdecode(value)

        return self.fields
    
    def _update_submit_docstring(self):
        """
        Some Python magic to update the submit method's docstring according to
        the actual fields in the form. This is useful in interactive Python
        mode while developing scraping code.
        """
        def submit(self, submitName=None, **kwargs):
            self._submit(submitName, **kwargs)
        def shorten(s, l=30):
            if isinstance(s, basestring) and len(s) > l:
                return s[:l-3]+"..."
            return s
        params = ", ".join("%s=%r" % (k, shorten(v)) for k, v in self.fields.items())
        submit.__doc__ = "submit(submitName=None, %s)\n%s" % (params, self.submit.__doc__)
        self.submit = type(self.submit)(submit, self, type(self))

    def __str__(self):
        return self.soup.get("action")

    def __repr__(self):
        return "<Form name='%s' id='%s' action=%s'>" % (self.soup.get("name"), self.soup.get("id"), self.soup.get("action"))

def htmlentitiesdecode(text):
    if text is None:
        return text
    return unicode(BeautifulSoup(text, convertEntities=BeautifulSoup.XHTML_ENTITIES))

def urljoin(base, url):
    """Joins a base url and a relative path to create an absolute URL"""
    import urlparse
    joined = urlparse.urljoin(base, url)
    return joined.replace("../", "")

def soup2text(soup):
    text = []
    for e in soup.recursiveChildGenerator():
        if isinstance(e, NavigableString):
            text.append(htmlentitiesdecode(e))
    return " ".join(text)

def bytes(s, encoding="utf8"):
    if isinstance(s, unicode):
        return s.encode(encoding)
    else:
        return s
