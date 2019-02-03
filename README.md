# Blog Migration Scripts

[![Python 3.7](https://img.shields.io/badge/python-3.7-blue.svg)](https://www.python.org/downloads/release/python-370/)
[![MIT](https://img.shields.io/github/license/Bytewerk/blogMigration.svg?style=flat)](https://github.com/Bytewerk/blogMigration/blob/master/LICENSE)

These scripts can be used to

- register an OAuth 1.0a application
- scrape the old serendipity Bingo Blog
- transform and upload content to a Wordpress site

## Scrape Serendipity Blog

Use `collectBlog.py` to scrape the Bingo e.V. blog.

URLs are static and content is parsed using BeautifulSoup4 with lxml.
Can probably be made to work with other somewhat recent serendipity versions (≥1.5.3-2) as well.

After scraping is done, the generated `authors.yml` file needs to be edited to add a Wordpress slug for every serendipity user:

    <serendipity id>:
       name: ...
       slug: <wordpress slug>
       posts: ...

## OAuth Script

The `oauth.py` works using YAML configuration files like shown in `config.example.yml`.
As a bare minimum, you need the following information to register with a new site:

    url: http://wordpress.example.com
    oauthCallback: oob
    consumerKey: <Field Client Key>
    consumerSecret: <Field Client Secret>

`oob` is the only callback supported by the script.

### Register OAuth 1.0a application

This code words in conjunction with the [WordPress REST API – OAuth 1.0a Server](https://wordpress.org/plugins/rest-api-oauth1/) plugin.  
Once installed, create a new application and use `oob` (out-of-band) callback and fill in the `consumerKey` and `consumerSecret` as indicated above.  
Then use `oauth.py --config siteConfig.yml register` to register with the new site.
This requires logging into your Wordpress using an account with the desired privileges, granting the application access and then pasting the verifier token into the Python command line.
After that, the script will finish registration and print out a complete configuration file.

You only need to register once even if you want to transfer multiple times.

### Transfer Content

Use `oauth.py --config siteConfig.yml transfer path/to/scraped/data` to transfer the scraped data to Wordpress.
The script can create the required users in an optional step using the `--create-users` command line option.

## Known Issues

There is no support for directly adding media files from serendipity yet, as there were so few.
The files are downloaded and the metadata is stored in the corresponding post data, but no upload
functionality was implemented.