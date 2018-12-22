#!/usr/bin/env python3
# coding: utf-8

import code
import os
import sys
import argparse
import locale
import pycurl
import yaml
import re
from copy import copy
from datetime import datetime, timedelta, timezone
from io import BytesIO
from bs4 import BeautifulSoup
from bs4.element import Tag, NavigableString, Comment

# 02:00 on start day until 03:00 end day
germany_summertime = {
    2009: {'start': {'day': 29, 'month': 3}, 'end': {'day': 25, 'month': 10}},
    2010: {'start': {'day': 28, 'month': 3}, 'end': {'day': 31, 'month': 10}},
    2011: {'start': {'day': 27, 'month': 3}, 'end': {'day': 30, 'month': 10}},
    2012: {'start': {'day': 25, 'month': 3}, 'end': {'day': 28, 'month': 10}},
    2013: {'start': {'day': 31, 'month': 3}, 'end': {'day': 27, 'month': 10}},
    2014: {'start': {'day': 30, 'month': 3}, 'end': {'day': 26, 'month': 10}},
    2015: {'start': {'day': 29, 'month': 3}, 'end': {'day': 25, 'month': 10}},
    2016: {'start': {'day': 27, 'month': 3}, 'end': {'day': 30, 'month': 10}},
    2017: {'start': {'day': 26, 'month': 3}, 'end': {'day': 29, 'month': 10}},
    2018: {'start': {'day': 25, 'month': 3}, 'end': {'day': 28, 'month': 10}},
}

def getTimezone(date, time):
    tz = timezone(timedelta(hours=1))
    summertime = germany_summertime[date.year]
    if (
        (
            date.month > summertime['start']['month']
            or (
                date.month == summertime['start']['month']
                and date.day >= summertime['start']['day']
                and time.hour > 2
            )
        )
        and (
            date.month < summertime['end']['month']
            or (
                date.month == summertime['end']['month']
                and date.day <= summertime['end']['day']
                and time.hour < 3
            )
        )
    ):
        tz = timezone(timedelta(hours=2))
    return tz

def postProcessBody(soup, body, exclude, strip_attr, unwrap, transAddress):
    
    result = copy(body)
    result.clear()
    media = []
    
    for c in body.children:
        if (type(c) == NavigableString):
            result.append(NavigableString(c.string.strip('\r\n')))
        elif (type(c) == Tag):
            if (c.name in exclude and c.has_attr('class')):
                if (any(x in c['class'] for x in exclude[c.name])):
                    continue
            # strip serendipity images,, but include info in media
            if (c.name == 'a' and c.has_attr('class') and 'serendipity_image_link' in c['class']):
                img = c('img', class_=lambda x: x.startswith('serendipity_image'))[0]
                s9ymdb_ix = -1
                prev = img.previous_sibling
                if (type(prev) == Comment):
                    comment = prev.string.strip()
                    if (comment.startswith('s9ymdb:')):
                        s9ymdb_ix = int(comment[7:])
                media.append({'url': c['href'], 's9ymdb_index': s9ymdb_ix, 'filename': os.path.basename(c['href'])})
                continue
            d, dm = postProcessBody(soup, c, exclude, strip_attr, unwrap, transAddress)
            media += dm
            if (c.name == 'span' and 'style' in c.attrs):
                # normalize
                style = c.attrs['style']
                style = re.sub(' +:', ':', style)
                style = re.sub(' +;', ';', style)
                style = ''.join(style.split())
                style = style.split(';')
                if ('font-weight:bold' in style):
                    b_tag = soup.new_tag('b')
                    b_tag.append(d)
                    result.append(b_tag)
                else:
                    result.append(d)
            else:
                result.append(d)
            if (c.name in strip_attr):
                for attr in strip_attr[c.name]:
                    if (c.has_attr(attr)):
                        del d[attr]
            # special-case p style="margin: 0cm 0cm 0pt;" --> <br/>
            if (c.name == 'p' and c.has_attr('style') and c['style'] == 'margin: 0cm 0cm 0pt;'):
                d.unwrap()
                result.append(soup.new_tag('br'))
            if (c.name in unwrap):
                if (unwrap[c.name] == []):
                    d.unwrap()
                elif (c.has_attr('class') and any(x in c['class'] for x in unwrap[c.name])):
                    d.unwrap()
        elif (type(c) == Comment):
            continue
        else:
            print('Info: found unknown type {0!s}'.format(type(c)))
            print('-'*72)
            print(c)
            print('-'*72)
    
    # merge adjacent NavigableString
    
    return result, media

def processCommentPage(url):
    
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    c.close()
    
    results = {'url': url, 'entries': []}
    media = []
    soup = BeautifulSoup(buffer.getvalue().decode('UTF-8'), 'lxml')
    comments_area = soup('div', class_='serendipity_section_comments')[0]
    
    for comment in comments_area('div', class_='serendipity_comment'):
        
        body = comment('div', class_='serendipity_commentBody')[0]
        source = comment('div', class_='serendipity_comment_source')[0]
        
        author = list(source('span', class_='comment_source_author')[0].stripped_strings)[0]
        date = source('span', class_='comment_source_date')[0].string
        date = datetime.strptime(date, '%d.%m.%Y %H:%M')
        tz = getTimezone(date.date(), date.time())
        date = date.replace(tzinfo=tz)
        
        body, comment_media = postProcessBody(
            soup,
            body,
            {'div': ['serendipity_commentcount']},
            {'p': ['style', 'class'], 'a': ['style', 'class']},
            {'address': [], 'br': [], 'font': [], 'pre': [], 'span': [], 'div': []},
            False
            )
        media += comment_media
        
        results['entries'].append(
            {
                'date': str(date),
                'authorName': str(author),
                'content': '\r\n'.join(filter(None, [str(e).strip() for e in body.contents])),
            }
        )
    
    return results, media

def main():

    site = 'http://blog.bingo-ev.de'
    author_url = '{0:s}/index.php?/authors/'.format(site)
    archive_url = '{0:s}/index.php?/archives/P{{0:d}}.html'.format(site)
    
    # locale for date/time
    # https://docs.microsoft.com/en-us/cpp/c-runtime-library/language-strings
    locale.setlocale(locale.LC_ALL, 'american-english')
    
    authors = {}
    datetime.now()
    
    directory = datetime.now().strftime('%Y%m%dT%H%M%S')
    os.makedirs(directory, exist_ok=True)
    post_id = 0
    
    for page in range(1, 8 + 1):
    #for page in range(3, 8 + 1):
        
        buffer = BytesIO()
        c = pycurl.Curl()
        c.setopt(c.URL, archive_url.format(page))
        c.setopt(c.WRITEDATA, buffer)
        c.perform()
        c.close()
        
        soup = BeautifulSoup(buffer.getvalue().decode('UTF-8'), 'lxml')
        content = soup.find('td', id='content')
        
        for entry in content('div', class_='serendipity_Entry_Date', recursive=False):
            
            # extract date
            date = entry('h3', class_='serendipity_date')
            date = datetime.strptime(date[0].string, '%A, %d. %B %Y')
            
            # FIXME: while loop here
            for ix, title in enumerate(entry('h4', class_='serendipity_title')):
            
                # extract title
                url = title.a['href']
                title = title.a.string
                
                # body and footer
                entry_contents = entry('div', class_='serendipity_entry')[ix]
                entry_body = entry_contents('div', class_='serendipity_entry_body')[0]
                entry_footer = entry_contents('div', class_='serendipity_entryFooter')[0]
                
                # check if extended entry and download content if so
                entry_extended_link = entry_contents('a', href=lambda x: x.endswith('#extended'))
                if (entry_extended_link):
                    a = entry_extended_link[0]
                    subbuffer = BytesIO()
                    c = pycurl.Curl()
                    c.setopt(c.URL, (site + a['href']) if a['href'].startswith('/') else a['href'])
                    c.setopt(c.WRITEDATA, subbuffer)
                    c.perform()
                    c.close()
                    
                    subsoup = BeautifulSoup(subbuffer.getvalue().decode('UTF-8'), 'lxml')
                    entry_contents = subsoup('div', class_='serendipity_entry')[0]
                    entry_extended = entry_contents('div', class_='serendipity_entry_extended')[0]
                    for c in entry_extended.children:
                        if (c.name == 'a' and c.has_attr('id') and c['id'] == 'extended'):
                            continue
                        entry_body.append(copy(c))
                
                # extract author and time
                entry_footer_fields = entry_footer.contents
                entry_footer_strings = list(entry_footer.stripped_strings)
                categories_beg = entry_footer_strings.index('in') + 1
                time_beg = entry_footer_strings.index('um') + 1
                comments_beg = -1 if '|' not in entry_footer_strings else entry_footer_strings.index('|') + 1
                
                # extract category (without commas)
                categories = [str(e.string) for e in entry_footer_fields[categories_beg:time_beg - 1] if e.string != ', ']
                
                # extract time
                time  = entry_footer_fields[time_beg].string
                time = datetime.strptime(time, '%H:%M')
                # figure out UTC offset
                tz = getTimezone(date.date(), time.time())
                date = datetime.combine(date.date(), time.time(), tz)
                
                # extract author ID and name
                author_field = entry_footer_fields[1]
                author_id = -1
                author = author_field.string
                if ('href' in author_field.attrs and author_field['href'].startswith(author_url)):
                    author_string = author_field['href'][len(author_url):]
                    # extract ID from 99-First-Last
                    author_id = int(author_string.split('-', 1)[0])
                else:
                    print('Warning: Author {0:s} without ID in {1:s}!'.format(author, title))
                
                # add author to global list
                # also check if duplicate author for whatever reason
                if (author_id not in authors):
                    authors[author_id] = {'name': str(author), 'posts': 0}
                
                authors[author_id]['posts'] += 1
                
                if (str(author) != authors[author_id]['name']):
                    print('Error: Author {0:s} ({1:d}) name changed from {2:s}'.format(auhtor, author_id, authors[author_id]['name']))
                
                # process comments
                comments = []
                if (comments_beg >= 0):
                    comment_field = entry_footer_fields[comments_beg]
                    if (comment_field.string != 'Kommentare (0)'):
                        # replace #comments with &serendipity[cview]=linear#comments
                        # to get comments in a linear fashion that is hopefully easier to parse
                        comment_url = site + str(comment_field['href'])
                        comment_url = comment_url.replace('#comments', '&serendipity[cview]=linear#comments')
                        comments, comment_media = processCommentPage(comment_url)
                        if (comment_media):
                            print(f'Error: comment media unsupported for \'{comment_url}\'.')
                
                body, media = postProcessBody(
                    soup,
                    entry_body,
                    {'div': ['serendipity_authorpic']},
                    {'p': ['style', 'class'], 'a': ['style', 'class']},
                    {'address': [], 'br': [], 'font': [], 'pre': [], 'span': [], 'div': []},
                    True
                    )
                
                post = {
                    'date':       str(date),
                    'author':     str(author),
                    'author_id':  author_id,
                    'categories': [str(e) for e in categories],
                    'title':      str(title),
                    'content':    '\r\n'.join(filter(None, [str(e).strip() for e in body.contents])),
                    'comments':   comments,
                    'url':        (site + url) if url.startswith('/') else url,
                    'media':      media,
                }
                
                # dump media files
                for m in media:
                    with open(os.path.join(directory, m['filename']), 'wb') as mediafile:
                        filename = m['filename']
                        print(f'Collecting media file \'{filename}\'...')
                        c = pycurl.Curl()
                        c.setopt(c.URL, (site + m['url']) if m['url'].startswith('/') else m['url'])
                        c.setopt(c.WRITEDATA, mediafile)
                        c.perform()
                        c.close()
                
                post_data = yaml.dump(post, encoding='utf-8', allow_unicode=True, default_flow_style=False)
                with open(directory + '/{0:03d}.yml'.format(post_id), 'bw') as f:
                    f.write(post_data)
                #code.interact(local=locals())
                post_id += 1
    
    author_data = yaml.dump(authors, encoding='utf-8', allow_unicode=True, default_flow_style=False)
    with open(directory + '/authors.yml', 'bw') as f:
        f.write(author_data)
    
if __name__ == '__main__':
    sys.exit(main())
