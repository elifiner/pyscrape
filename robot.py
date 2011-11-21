import urllib
import urllib2
from BeautifulSoup import BeautifulSoup

class BrowserError(Exception):
    def __init__(self, msg="robot.Browser encountered an error"):
        self.msg = msg
    def __str__(self):
        return self.msg

# ------------------------------------------------------------------------------

class Browser(object):
    def __init__(self, userAgent="robot/1.0"):
        self._userAgent = userAgent
        self._passwordManager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        
        self._opener = urllib2.build_opener(
            urllib2.HTTPCookieProcessor(),
            urllib2.HTTPBasicAuthHandler(self._passwordManager),
            urllib2.HTTPDigestAuthHandler(self._passwordManager)
        )
        
        self.currentUrl = None
        self.page = None
        self.headers = {}
        self.soup = None

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
        
        self.currentUrl = url
        request = urllib2.Request(self.currentUrl)
        request.add_header("User-Agent", self._userAgent)
        
        # try several times to protect from short network problems
        for i in range(retries):
            try:
                response = self._opener.open(request, postData)
                self.headers = response.info()
                self.page = response.read()
                self.soup = BeautifulSoup(self.page)
            except Exception, e:
                error = e
                import time
                time.sleep(1) # wait a second between retries
            else:
                error = None
                break
        
        if error:
            raise error
            
        return self.page
        
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
        (fno, tempName) = tempfile.mkstemp('.html', 'robot-')
        os.close(fno)
        f = open(tempName, "w")
        f.write(str(soup))
        f.close()
        
        # display page in browser
        import webbrowser
        webbrowser.open(tempName)
        
    def _get_title(self):
        return self.soup.find("title").string
    title = property(_get_title)

# ------------------------------------------------------------------------------
    
class Form(object):
    def __init__(self, browser, soup):
        self.browser = browser
        self.soup = soup
        self.defaults = {}
        self.submits = {}
        self._load_defaults()
    
    def submit(self, submitName=None, **kwargs):
        """
        Submits the form using keyword arguments as form parameters.
        The submitName is the 'name' attribute of the submit input tag, useful 
        if there is more than one submit button on the page.
        Moves the Browser object it was created from to the new page after submission.
        """
        action = urljoin(self.browser.currentUrl, self.soup.get("action"))
        fields = {}
        submitValue = self.submits.get(submitName)
        if submitValue:
            fields[submitName] = submitValue
        fields.update(self.defaults)
        fields.update(kwargs)
        fields = dict((bytes(k), bytes(v)) for (k, v) in fields.items())
        postData = urllib.urlencode(fields)
        self.browser.goto(action, postData)
        return self.browser.soup
        
    def _load_defaults(self):
        """
        Loads the default values for the form from the HTML.
        """
        self.defaults = {}
        
        # get default values for input self.defaults
        for inputTag in self.soup.findAll("input"):
            name = inputTag.get("name")
            value = inputTag.get("value") or ""
            type = inputTag.get("type")
            disabled = (inputTag.get("disabled") == "disabled")
            if name and value and not disabled:
                if type == "submit":
                    self.submits[name] = htmlentitiesdecode(value)
                else:
                    self.defaults[name] = htmlentitiesdecode(value)
                
        # get default values for textarea self.defaults
        for textTag in self.soup.findAll("textarea"):
            name = textTag.get("name")
            value = textTag.get("value") or ""
            disabled = (textTag.get("disabled") == "disabled")
            if name and value and not disabled:
                self.defaults[name] = htmlentitiesdecode(value)
                
        # get default values for select self.defaults
        for selectTag in self.soup.findAll("select"):
            name = selectTag.get("name")
            disabled = (inputTag.get("disabled") == "disabled")
            if name and not disabled:
                value = None
                for optionTag in selectTag.findAll("option"):
                    if optionTag.get("selected") == "selected":
                        value = optionTag.get("value").strip()
                if value:
                    self.defaults[name] = htmlentitiesdecode(value)
        
        return self.defaults
        
    def __str__(self):
        return self.soup.get("action")
                
def htmlentitiesdecode(text):
    entities = [BeautifulSoup.XML_ENTITIES, BeautifulSoup.HTML_ENTITIES]
    return unicode(BeautifulSoup(text, convertEntities=entities))
    
def urljoin(base, url):
    """Joins a base url and a relative path to create an absolute URL"""
    import urlparse
    joined = urlparse.urljoin(base, url)
    return joined.replace("../", "")
    
def bytes(s):
    if isinstance(s, unicode):
        return s.encode("utf8")
    else:
        return s
