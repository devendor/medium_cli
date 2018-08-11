#! /usr/bin/env python
import locale

try:
    locale.setlocale(locale.LC_ALL, '')
except:
    pass

import time
import sys
import os
import io
import json
from optparse import OptionParser
from docutils.core import publish_cmdline
from docutils.writers import s5_html as w
import re

try:
    from ConfigParser import SafeConfigParser, NoOptionError, NoSectionError
except ImportError:
    # try to be python3 compatible
    from configparser import SafeConfigParser, NoOptionError, NoSectionError
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode
import requests

bearer_file = os.path.expanduser('~/.medium_bearer')
config_file = os.path.expanduser('~/.medium')
config_example = """
# Config file example
[medium]
client_id=supplied_when_registering_app
client_secret=supplied_when_registering_app
redirect_url=http://192.0.2.1/must_match_registered_url
state=canBeAnything
"""
scopes = ["basicProfile", "publishPost", "listPublications"]
usage = "Allows post of html, markdown, or rst files to medium.\n\nusage: %prog [options] [file]"

op = OptionParser(usage, add_help_option=True)
op.add_option("-c", "--code", dest="code", default=None, help="code from redirect url after "
                                                              "approval")
op.add_option("-u", "--user", action="store_true", default=False, dest='user',
              help='print user info')
op.add_option("-l", "--list-publications", action="store_true", default=False, dest='list',
              help='list-publications')
op.add_option("-t", "--title", default=None, dest='title', help='article title')
op.add_option("-a", "--authors", default=None, dest='publication',
              help='show contributor info for pub')
op.add_option("-p", "--pub", default=None, dest='pub', help='posts to publication')
op.add_option("-r", "--ref-url", default=None, dest='url', help="canonicalUrl. Ref if originally "
                                                                "posted elsewhere")
op.add_option("-k", "--keep-tmpfiles", action="store_false", dest="remove_tmpfiles", default=True,
              help="Keep /tmp/article.rst and /tmp/article.html tmp files when processing rst")
(o, args) = op.parse_args()

if len(args) == 1:
    s_file = args[0]
    if os.path.isfile(s_file) is False:
        raise UserWarning("Cannot find file for posting %s" % s_file)
else:
    s_file = None

if (int(s_file is not None) + int(o.list) + int(o.user) + int(o.publication is not None)) != 1:
    print "You must specify one of --list --user or file to post"
    op.print_help()
    sys.exit(0)

c = SafeConfigParser()
if len(c.read(config_file)) == 0:
    print "Error Config file not found: %s\n%s" % (config_file, config_example)
    os.exit(1)
try:
    client_id = c.get('medium', 'client_id')
    client_secret = c.get('medium', 'client_secret')
    redirect_url = c.get('medium', 'redirect_url')
    state = c.get('medium', 'state')
except [NoOptionError, NoSectionError] as e:
    print "Configuration Error %s\n%s" % (e, config_example)
    sys.exit(1)


class MediumClient(object):
    """A client for the Medium OAuth2 REST API."""

    def __init__(self, application_id=None, application_secret=None,
                 access_token=None):
        self.application_id = application_id
        self.application_secret = application_secret
        self.access_token = access_token
        self._user = None
        self._BASE_PATH = "https://api.medium.com"

    @property
    def user_id(self):
        """Current User ID.

        :return: User id from .get_current_user()['id']
        :rtype: string
        """
        if self._user is None:
            self._user = self.get_current_user()
        return self._user['id']

    def get_authorization_url(self, state, redirect_url, scopes):
        """Get a URL for users to authorize the application.

        :param str state: A string that will be passed back to the redirect_url
        :param str redirect_url: The URL to redirect after authorization
        :param list scopes: The scopes to grant the application
        :returns: str
        """
        qs = {
            "client_id":     self.application_id,
            "scope":         ",".join(scopes),
            "state":         state,
            "response_type": "code",
            "redirect_uri":  redirect_url,
        }

        return "https://medium.com/m/oauth/authorize?" + urlencode(qs)

    def exchange_authorization_code(self, code, redirect_url):
        """Exchange the authorization code for a long-lived access token, and
        set the token on the current Client.

        :param str code: The code supplied to the redirect URL after a user
            authorizes the application
        :param str redirect_url: The same redirect URL used for authorizing
            the application
        :returns: A dictionary with the new authorizations ::
            {
                'token_type': 'Bearer',
                'access_token': '...',
                'expires_at': 1449441560773,
                'refresh_token': '...',
                'scope': ['basicProfile', 'publishPost']
            }
        """
        data = {
            "code":          code,
            "client_id":     self.application_id,
            "client_secret": self.application_secret,
            "grant_type":    "authorization_code",
            "redirect_uri":  redirect_url,
        }
        return self._request_and_set_auth_code(data)

    def exchange_refresh_token(self, refresh_token):
        """Exchange the supplied refresh token for a new access token, and
        set the token on the current Client.

        :param str refresh_token: The refresh token, as provided by
            ``exchange_authorization_code()``
        :returns: A dictionary with the new authorizations ::
            {
                'token_type': 'Bearer',
                'access_token': '...',
                'expires_at': 1449441560773,
                'refresh_token': '...',
                'scope': ['basicProfile', 'publishPost']
            }
        """
        data = {
            "refresh_token": refresh_token,
            "client_id":     self.application_id,
            "client_secret": self.application_secret,
            "grant_type":    "refresh_token",
        }
        return self._request_and_set_auth_code(data)

    def get_current_user(self):
        """Fetch the data for the currently authenticated user.

        Requires the ``basicProfile`` scope.

        :returns: A dictionary with the users data ::

            {
                'username': 'kylehg',
                'url': 'https://medium.com/@kylehg',
                'imageUrl': 'https://cdn-images-1.medium.com/...',
                'id': '1f86...',
                'name': 'Kyle Hardgrave'
            }
        """
        if self._user is None:
            self._user = self._request("GET", "/v1/me")
        return self._user

    def create_post(self, title, content, content_format, publication_id=None, tags=None,
                    canonical_url=None, publish_status=None, license=None):
        """Create a post for the current user.

        Requires the ``publishPost`` scope.

        :param str title: The title of the post
        :param str content: The content of the post, in HTML or Markdown
        :param str content_format: The format of the post content, either
            ``html`` or ``markdown``
        :param: str publication_id: Publication ID when publishing to publication.
        :param list tags: (optional), List of tags for the post, max 3
        :param str canonical_url: (optional), A rel="canonical" link for
            the post
        :param str publish_status: (optional), What to publish the post as,
            either ``public``, ``unlisted``, or ``draft``. Defaults to
            ``public``.
        :param license: (optional), The license to publish the post under:
            - ``all-rights-reserved`` (default)
            - ``cc-40-by``
            - ``cc-40-by-sa``
            - ``cc-40-by-nd``
            - ``cc-40-by-nc``
            - ``cc-40-by-nc-nd``
            - ``cc-40-by-nc-sa``
            - ``cc-40-zero``
            - ``public-domain``
        :returns: A dictionary with the post data ::

            {
                'canonicalUrl': '',
                'license': 'all-rights-reserved',
                'title': 'My Title',
                'url': 'https://medium.com/@kylehg/55050649c95',
                'tags': ['python', 'is', 'great'],
                'authorId': '1f86...',
                'publishStatus': 'draft',
                'id': '55050649c95'
            }
        """
        data = {
            "title":         title,
            "content":       content,
            "contentFormat": content_format,
        }
        if tags is not None:
            data["tags"] = tags
        if canonical_url is not None:
            data["canonicalUrl"] = canonical_url
        if publish_status is not None:
            data["publishStatus"] = publish_status
        if license is not None:
            data["license"] = license

        if publication_id is None:
            path = "/v1/users/%s/posts" % self.user_id
        else:
            path = "/v1/publications/%s/posts" % publication_id
        return self._request("POST", path, json=data)

    def upload_image(self, file_path, content_type):
        """Upload a local image to Medium for use in a post.

        Requires the ``uploadImage`` scope.

        :param str file_path: The file path of the image
        :param str content_type: The type of the image. Valid values are
            ``image/jpeg``, ``image/png``, ``image/gif``, and ``image/tiff``.
        :returns: A dictionary with the image data ::

            {
                'url': 'https://cdn-images-1.medium.com/0*dlkfjalksdjfl.jpg',
                'md5': 'd87e1628ca597d386e8b3e25de3a18b8'
            }
        """
        with open(file_path, "rb") as f:
            filename = os.path.basename(file_path)
            files = {"image": (filename, f, content_type)}
            return self._request("POST", "/v1/images", files=files)

    def _request_and_set_auth_code(self, data):
        """Request an access token and set it on the current client."""
        result = self._request("POST", "/v1/tokens", form_data=data)
        self.access_token = result["access_token"]
        return result

    def _request(self, method, path, json=None, form_data=None, files=None):
        """Make a signed request to the given route."""
        url = self._BASE_PATH + path
        headers = {
            "Accept":         "application/json",
            "Accept-Charset": "utf-8",
            "Authorization":  "Bearer %s" % self.access_token,
        }

        resp = requests.request(method, url, json=json, data=form_data,
                                files=files, headers=headers)
        json = resp.json()
        if 200 <= resp.status_code < 300:
            try:
                return json["data"]
            except KeyError:
                return json

        raise MediumError("API request failed", json)

    def get_contributors(self, publication_id):
        """Fetch a list of contributors to a publication.

        Requires ``listPublications`` scope.

        :param publication_id: The appllication-specific publication id as returned by
           ``get_publications()``
        :return: publications
        :rtype: `dict`
        """
        return self._request("GET", "/v1/publications/%s/contributors" % publication_id)

    def get_publications(self):
        """Fetch a list of publications associated with the user.

        Requires ``listPublications`` scope.

        :return: users data
        :rtype: `dict`
        """
        return self._request("GET", "/v1/users/%s/publications" % self.user_id)


class MediumError(Exception):
    """Wrapper for exceptions generated by the Medium API."""

    def __init__(self, message, resp={}):
        self.resp = resp
        try:
            error = resp["errors"][0]
        except KeyError:
            error = {}
        self.code = error.get("code", -1)
        self.msg = error.get("message", message)
        super(MediumError, self).__init__(self.msg)


client = MediumClient(application_id=client_id, application_secret=client_secret)

if os.path.isfile(bearer_file):
    with io.open(bearer_file, encoding='utf-8', mode='r') as bf:
        try:
            bearer = json.load(bf, encoding='utf-8')
            bearer = client.exchange_refresh_token(bearer['refresh_token'])
        except MediumError, e:
            print "Token failure. You must refresh your token.\n%s" % (e)
            os.unlink(bearer_file)
        except Exception, e:
            print "Token decode failure. You must refresh your token.\n%s" % (e)
            os.unlink(bearer_file)

if os.path.isfile(bearer_file) is False:
    if o.code is None and os.path.isfile(bearer_file) is False:
        auth_url = client.get_authorization_url(state, redirect_url, scopes)
        print "Authorized the app by following the url, and passing the code= value in " \
              "the redirect url to --code to generate a new bearer token\n\n%s" % auth_url
        sys.exit(0)
    else:
        bearer = client.exchange_authorization_code(o.code, redirect_url)

with open(bearer_file, mode='w') as bf:
    json.dump(bearer, bf, encoding='utf-8', indent=3)

if o.user:
    resp = client.get_current_user()
elif o.list:
    resp = client.get_publications()
elif o.publication is not None:
    resp = client.get_contributors(o.publication)
elif s_file is not None:
    in_format = "markdown" if s_file.lower()[-3:] == '.md' else "html"
    title = "%s %s" % (os.path.basename(os.path.splitext(s_file)[0]).replace("_", " "),
                       time.strftime("%Y%m%d-%X%Z")) if o.title is None else o.title
    if s_file[-4:].lower() == ".rst":
        html_file = "/tmp/%s.html" % os.path.basename(s_file)[:-4]
        tmp_rst = "/tmp/%s" % os.path.basename(s_file)
        re_number = re.compile(u'^(\s*)(?:#|\d+)\.\s(\S.*)$')

        with io.open(s_file, mode="r", encoding="utf-8") as content_in:
            with io.open(tmp_rst, mode='w', encoding='utf-8') as content_out:
                content_out.write(u'.. role:: index(raw)\n   :format: html\n\n')
                for line in content_in:
                    if u'.. todo:: ' in line:
                        line = line.replace(u'.. todo:: ', u'.. note:: TODO: ')
                    i = line.find(u'.. code-block::')
                    if i >= 0:
                        line = line[:i] + u'.. code-block::\n'
                    m = re_number.match(line)
                    if m is not None:
                        line = u'%s   %s' % m.groups()

                    content_out.write(line)

        publish_cmdline(writer=w.Writer(), argv=[tmp_rst, html_file])
        s_file = html_file

    with io.open(s_file, mode="r", encoding="utf-8") as content:
        if o.pub is None:
            print "posting to user"
            resp = client.create_post(title=title, content=content.read(),
                                      content_format=in_format, publish_status="draft",
                                      canonical_url=o.url)
        else:
            print "posting to publication"
            resp = client.create_post(publication_id=o.pub, title=title, content=content.read(),
                                      content_format=in_format, publish_status="draft",
                                      canonical_url=o.url)

    if o.remove_tmpfiles and "tmp_rst" in vars():
        os.unlink(tmp_rst)
        os.unlink(html_file)

print json.dumps(resp, indent=1)
