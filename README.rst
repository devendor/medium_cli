Medium Command Line Client
==========================

`medium_cli.py`_ is command line client for interacting with medium.com.

Summary
-------

Medium command line client allows you to push html, markdown, or restructured text files to
`medium.com`_

HTML rendering is fairly limited by supported tags at medium, but the cli at least preserves line
breaks in code/pre tags.

Markdown is probably the most reliable since it is also very limited in what is supported.

Restructured text is handled by munging out some unsupported tags and mangling things like
ordered lists that allow multi-part list items in rst, but have no counterpart in medium.

Installation
------------

#. Install requirements and set executable bit.

   .. code-block:: console

      user@myhost$ git clone https://github.com/devendor/medium_cli.git
      user@myhost$ cd medium_cli
      user@myhost$ pip install -r requirements.txt
      user@myhost$ chmod +x medium_cli.py

#. Make an initial request to get the the config template (~/.medium)

   .. code-block:: console

      user@myhost$ ./medium_cli.py
      You must specify one of --list --user or file to post
      Usage: Allows post of html, markdown, or rst files to medium.

      usage: medium_cli.py [options] [file]

      Options:
        -h, --help            show this help message and exit
        -c CODE, --code=CODE  code from redirect url after approval
        -u, --user            print user info
        -l, --list-publications
                              list-publications
        -t TITLE, --title=TITLE
                              article title
        -a PUBLICATION, --authors=PUBLICATION
                              show contributor info for pub
        -p PUB, --pub=PUB     posts to publication
        -r URL, --ref-url=URL
                              canonicalUrl. Ref if originally posted elsewhere
        -k, --keep-tmpfiles   Keep /tmp/article.rst and /tmp/article.html tmp files
                              when processing rst
      user@myhost$ ./medium_cli.py -u
      Error Config file not found: /home/rferguson/.medium

      # Config file example
      [medium]
      client_id=supplied_when_registering_app
      client_secret=supplied_when_registering_app
      redirect_url=http://192.0.2.1/must_match_registered_url
      state=canBeAnything

      Traceback (most recent call last):
        File "/home/rferguson/bin/medium_cli.py", line 73, in <module>
          os.exit(1)
      AttributeError: 'module' object has no attribute 'exit'


#. On medium.com settings, scroll down to developer applications, and register an application.
   You can pick any redirect_url.

#. Fill in a config file with the client_id, and client_secret returned from medium.com along with
   the redirect_url you used when requesting it.

   .. code-block:: console
      user@myhost$ cat <<'EOF'>~/.medium
      [medium]
      client_id=supplied_when_registering_app
      client_secret=supplied_when_registering_app
      redirect_url=http://192.0.2.1/must_match_registered_url
      state=eipaik2ieMei0iemoun1queik9leixae
      EOF

#. Once you have a config, just make another request to get an authorization url.

   .. code-block:: console

      user@myhost$ medium_cli.py -u
      Authorized the app by following the url, and passing the code= value in the redirect url to --code to generate a new bearer token

      https://medium.com/m/oauth/authorize?scope=...

#. Follow that url in a browser, click the authorize button on medium.com, and make note of the
   **code=....** value in the url your are redirected to.

#. Make a request and provide that initial authorization code to receive a bearer token.

   .. code-block:: console

      user@myhost$ medium_cli.py -c 1f127f985cfe -u
      {
       "username": "Ray.Ferguson",
       "url": "https://medium.com/@Ray.Ferguson",
       "imageUrl": "https://cdn-images-1.medium.com/fit/c/400/400/0*GmLZd7BSAeKonMEV.",
       "id": "1ea052e3e51b23b17fbbb0825cc6f3c8963e2438da106f96f12d2d0b01183961e",
       "name": "Raymond Ferguson"
      }

#. Once a bearer token is established, it is stored and kept up to date in ~/.medium_bearer allowing
   you to use the cli without passing a new code.

   .. code-block:: console

      user@myhost$ ./medium_cli.py -u
      {
       "username": "Ray.Ferguson",
       "url": "https://medium.com/@Ray.Ferguson",
       "imageUrl": "https://cdn-images-1.medium.com/fit/c/400/400/0*GmLZd7BSAeKonMEV.",
       "id": "1ea052e3e51b23b17fbbb0825cc6f3c8963e2438da106f96f12d2d0b01183961e",
       "name": "Raymond Ferguson"
      }


Usage Notes
-----------

To post to a publication, you need the publication id and permissions on the publication.

.. code-block:: console

   user@myhost$ ./medium_cli.py -l
   [
    {
     "url": "https://medium.com/devendor-tech",
     "imageUrl": "https://cdn-images-1.medium.com/fit/c/400/400/1*l9geaqCJ_QQtvRB_ddEgPw.png",
     "description": "Technical publications from Devendor Tech",
     "id": "71cdf2d7072c",
     "name": "Devendor Tech"
    },
    {
     "url": "https://medium.com/free-code-camp",
     "imageUrl": "https://cdn-images-1.medium.com/fit/c/400/400/1*MotlWcSa2n6FrOx3ul89kw.png",
     "description": "Our community publishes stories worth reading on development, design, and data science.",
     "id": "336d898217ee",
     "name": "freeCodeCamp"
    }
   ]

Inbound file type is determined by extension.

.. code-block:: ini

   *.md=markdown
   *.rst=restructured text
   *.*=anything else is assumed to be html

Related Projects
----------------

* `medium-sdk-python`_ provides the base of my inline class.  It looks like they have several
pull reauests that try to contribute additional features but nobodies rolling them in so I
decided to embed my own.
* `medium-sdk-docs`_ provides api information.


.. _medium-sdk-python: https://github.com/Medium/medium-sdk-python/tree/master
.. _medium-sdk-docs: https://github.com/Medium/medium-api-docs
.. _medium.com: https://medium.com
.. _medium_cli.py: https://github.com/devendor/medium_cli.git