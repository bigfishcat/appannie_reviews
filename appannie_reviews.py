#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# AppAnnie Playground
# Set your API key and account numbers in settings.py
import requests
import markdown
import smtplib
import sys
import settings as _s
from email.mime.text import MIMEText
from datetime import date, timedelta
from time import sleep

COMMASPACE = ', '
DAY_REQUEST_LIMIT = 1000
MINUTE_REQUEST_LIMIT = 30
_minute_request_counter = 0
_day_request_counter = 0

def main(platform=None):
    """ Run the whole toolchain for all accounts. """
    account_map = {}
    for account in _accounts():
        if account['market'] in account_map:
            account_map[account['market']].append(account)
        else:
            account_map[account['market']] = [account]

    if platform and platform in account_map:
        title = 'App Annie Report ({})'.format(platform)
        html = _load_reviews(account_map[platform])
        _send_mail(title, html)
    else:
        for market in account_map:
            title = 'App Annie Report ({})'.format(market)
            html = _load_reviews(account_map[market])
            _send_mail(title, html)


def _send_mail(title, body):
    msg = MIMEText(body, 'html')
    msg['Subject'] = title
    msg['From'] = _s.sender['email']
    msg['To'] = COMMASPACE.join(_s.receivers)
    s = smtplib.SMTP(_s.sender['server'])
    s.ehlo()
    s.starttls()
    s.ehlo()
    if _s.sender['login'] and _s.sender['password']:
        s.login(_s.sender['login'], _s.sender['password'])
    s.sendmail(_s.sender['email'], _s.receivers, msg.as_string())
    s.quit()

def _load_reviews(accounts):
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=7)).isoformat()
    text = ""
    for account in accounts:
        apps = _apps(account['account_id'])
        if not apps:
            continue
        text += "# {} ({})\n\n".format(account['account_name'], account['market'])
        text += "**Publisher: {}**\n\n".format(account['publisher_name'])
        text += "**Status:** {}\n".format(account['account_status'])
        for app in apps:
            reviews = _reviews(app['product_id'], account['vertical'], account['market'], start, end)
            if not reviews:
                continue
            if 'devices' in app:
                text += "\n## {} ({})\n\n".format(app['product_name'], app['devices'])
            else:
                text += "\n## {}\n\n".format(app['product_name'])
            text += "**Status:** {}\n\n".format(app['status'])
            text += "| Date | Rating | Title | Text | Version | Country | Reviewer |\n"
            text += "| ---- | :----: | ----- | ---- | ------- | ------- | -------- |\n"
            for rev in reviews:
                stars = '%s%s' % (''.join([u"★" for i in range(rev['rating'])]),
                                  ''.join([u"☆" for i in range(5 - rev['rating'])]))
                text += '| {} | {} | {} | {} | {} | {} | {} |\n'.format(rev['date'], stars, rev['title'], rev['text'],
                                                                        rev['version'], rev['country'], rev['reviewer'])
            text += "\n"
        text += "***\n\n"
    return markdown.markdown(text, extensions=['markdown.extensions.tables'])


def _get(path):
    """ Sets up a requests object, composes the URL and downloads data from
    AppAnnie's API. """

    assert _s.api_key
    assert _s.base_url
    assert path and len(path) > 0

    global _minute_request_counter, _day_request_counter
    if _day_request_counter > DAY_REQUEST_LIMIT:
        sleep(86400)
        _day_request_counter = 0

    if _minute_request_counter > MINUTE_REQUEST_LIMIT:
        sleep(60)
        _minute_request_counter = 0

    headers = {
        'Authorization': 'Bearer {}'.format(_s.api_key)
    }

    url = _s.base_url + path
    r = requests.get(url, headers=headers)
    try:
        r.raise_for_status()
    except Exception as e:
        print("Failed to download:\n%s\n%s" % (url, e))

    _minute_request_counter += 1
    _day_request_counter += 1
    try:
        return r.json()
    except Exception as e:
        print(e)
        return None


def _load(path, entity_name, results):
    raw = _get(path)
    if not raw or raw['code'] != 200:
        return results

    results.extend(raw[entity_name])

    next_page = raw.get('next_page')
    if next_page is not None:
        return _load(next_page, results)

    return results


def _accounts():
    return _load('/accounts', 'accounts', [])


def _apps(account_id):
    return _load('/accounts/{}/products'.format(account_id), 'products', [])


def _reviews(app_id, vertical, market, start=None, end=None):
    """ Downloads app reviews. """

    path = '/{}/{}/{}/{}/reviews'.format(vertical, market, vertical[:-1], app_id)

    if start:
        path += '?start_date=' + start
    if end:
        if start is None:
            path += '?'
        else:
            path += '&'
        path += 'end_date=' + end

    return _load(path, 'reviews', [])


def _sf(string):
    """ Make a string CSV-safe. """
    if not string:
        return ''
    return string.replace('"', '""').encode('utf-8')


if '__main__' == __name__:
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()
