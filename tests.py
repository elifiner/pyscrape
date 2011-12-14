import unittest
from mock import MagicMock as Mock, patch

import pyscrape

class BrowserTestBase(unittest.TestCase):
    def setUp(self):
        # A mapping of URLs to HTMLs that will be returned by mock_http_open
        self.mockReturnedHtmls = {
            "http://www.example.com" : "<html>Example</html>"
        }

        # A mapping of URLs to URLs that mock_http_open will simulate redirecting to
        self.mockRedirectedUrls = {
        }

        # This function will be called instead of the real http_open un urrlib2
        def _http_open(req):
            response = Mock(name="response")
            response.read = lambda: self.mockReturnedHtmls[req.get_full_url()]
            response.geturl = lambda: self.mockRedirectedUrls.get(req.get_full_url()) or req.get_full_url()
            response.info.return_value.dict = {"content-type":"text/html; charset=ut8"}
            return response

        self.mock_http_open = Mock(name="http_open", side_effect=_http_open)

    def patch_http_open(self):
        return patch("urllib2.HTTPHandler.http_open", self.mock_http_open)

    def last_request(self):
        return self.mock_http_open.call_args[0][0]

class MiscTests(BrowserTestBase):
    def test(self):
        self.mockReturnedHtmls["http://www.example.com"] = "<html>text</html>"
        with self.patch_http_open():
            browser = pyscrape.Browser()
            browser.goto("http://www.example.com")

        assert "http://www.example.com" == self.last_request().get_full_url()
        assert "pyscrape/1.0" == self.last_request().headers["User-agent"]
        assert browser.page == "<html>text</html>"

    def test_user_agent(self):
        self.mockReturnedHtmls["http://www.example.com"] = "<html>text</html>"
        with self.patch_http_open():
            browser = pyscrape.Browser(userAgent="momo/1.0")
            browser.goto("http://www.example.com")

        assert self.last_request().headers["User-agent"] == "momo/1.0"

    def test_show_in_browser(self):
        self.mockReturnedHtmls["http://www.example.com"] = "<html>text</html>"
        with self.patch_http_open():
            browser = pyscrape.Browser()
            browser.goto("http://www.example.com")
            with patch("webbrowser.open"):
                browser.show_in_browser()

class FormTests(BrowserTestBase):
    def test_form(self):
        self.mockReturnedHtmls["http://www.example.com"] = """\
<html>
    <form id="login" action="login.cgi">
        <input name="username">
        <input name="password">
        <input typ="submit" name="submit" value="done">
    </form>
</html>
"""
        self.mockReturnedHtmls["http://www.example.com/login.cgi"] = "<html>Login OK</html>"

        with self.patch_http_open():
            browser = pyscrape.Browser()
            browser.goto("http://www.example.com")
            form = browser.forms.get("login")
            assert ["username", "password", "submit"] == form.fields.keys()
            form.submit(username="guest", password="12345678")

            assert self.last_request().get_full_url() == "http://www.example.com/login.cgi"
            assert self.last_request().data == "username=guest&password=12345678&submit=done"

class LinkTests(BrowserTestBase):
    def test_link(self):
        self.mockReturnedHtmls["http://www.example.com"] = """\
<html>
    <a href="one.html">one</a>
    <a href="two.html">two</a>
</html>
"""
        self.mockReturnedHtmls["http://www.example.com/one.html"] = "<html>one</html>"
        self.mockReturnedHtmls["http://www.example.com/two.html"] = "<html>two</html>"

        with self.patch_http_open():
            browser = pyscrape.Browser()
            browser.goto("http://www.example.com")
            assert len(browser.links) == 2
            browserCopy = browser.duplicate()

            browser.links.get("one").goto()
            assert self.last_request().get_full_url() == "http://www.example.com/one.html"
            assert browser.page == "<html>one</html>"

            browserCopy.links.get("two").goto()
            assert self.last_request().get_full_url() == "http://www.example.com/two.html"
            assert browserCopy.page == "<html>two</html>"

class FrameTests(BrowserTestBase):
    def test_frame(self):
        self.mockReturnedHtmls["http://www.example.com"] = """\
<html>
    <frameset cols="25%,75%">
       <frame src="frame_a.htm" />
       <frame src="frame_b.htm" />
    </frameset>
</html>
"""
        self.mockReturnedHtmls["http://www.example.com/frame_a.htm"] = "<html>frame_a</html>"
        self.mockReturnedHtmls["http://www.example.com/frame_b.htm"] = "<html>frame_b</html>"

        with self.patch_http_open():
            browser = pyscrape.Browser()
            browser.goto("http://www.example.com")
            browserCopy = browser.duplicate()
            assert len(browser.frames) == 2

            browser.frames.get("frame_a").goto()
            assert self.last_request().get_full_url() == "http://www.example.com/frame_a.htm"
            assert browser.page == "<html>frame_a</html>"

            browserCopy.frames.get("frame_b").goto()
            assert self.last_request().get_full_url() == "http://www.example.com/frame_b.htm"
            assert browserCopy.page == "<html>frame_b</html>"

class BackTests(BrowserTestBase):
    def test_back(self):
        self.mockReturnedHtmls["http://www.example.com/1"] = "location1"
        self.mockReturnedHtmls["http://www.example.com/2"] = "location2"
        self.mockReturnedHtmls["http://www.example.com/3"] = "location3"
        with self.patch_http_open():
            browser = pyscrape.Browser()
            browser.goto("http://www.example.com/1")
            browser.goto("2")
            assert self.last_request().get_full_url() == "http://www.example.com/2"
            browser.back()
            assert self.last_request().get_full_url() == "http://www.example.com/1"
            browser.goto("3")
            assert self.last_request().get_full_url() == "http://www.example.com/3"

