#!/usr/bin/env python3

import asyncio
import logging
import sys
from collections import OrderedDict
from html.parser import HTMLParser
from urllib.parse import urlparse

import aiohttp


class CrawlAgenda:
    '''
    CrawlAgenda manages the growing set of URLs traveled by the crawler.

    Priorities:
    * Handle state management for each URL so the crawling code doesn't need to.
    * Avoid crawling the same URL twice (including by concurrent requests).
    * Efficiently return one new uncrawled URL at a time.
    * Keep memory use reasonable by not storing duplicate URLs.
    * Store uncrawled links in the order they're found, so we crawl
      progressively from the starting point outward.
    '''

    def __init__(self):
        self._crawled = set([])
        self._crawling = set([])
        self._to_crawl = OrderedDict()

    def add_new_url(self, url):
        if url not in self._crawled and url not in self._crawling:
            self._to_crawl[url] = None

    def more_to_crawl(self):
        return bool(self._to_crawl)

    def acquire_url(self):
        url, _ = self._to_crawl.popitem(last=False) # pop the first (oldest) url
        self._crawling.add(url)
        return url

    def mark_crawled(self, url):
        self._crawling.remove(url)
        self._crawled.add(url)


def crawl_html(body):
    links = []

    class LinkParser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag != 'a':
                return
            href = dict(attrs).get('href')
            if not href:
                return
            url = urlparse(href)
            if url.scheme in ('http', 'https'):
                links.append(href)

    LinkParser().feed(body)
    return links


async def fetch(session, url):
    try:
        async with session.get(url) as response:
            content_type = response.headers.get('Content-Type')
            if content_type:
                content_type = content_type.split(';')[0]
                if content_type == 'text/html':
                    return (url, await response.text())
    except (aiohttp.ClientError, ValueError) as ex:
        # In a production system, we would want retry logic, a dead letter
        # queue, etc. for failed requests -- but for this exercise we'll just
        # discard them.
        #
        # Also, catching ValueError is a bit broad, and not ideal, but aiohttp
        # throws some ValueErrors for redirect problems that we have no control
        # over:
        # https://github.com/aio-libs/aiohttp/blob/cd5c48a619ba61bff48ac1f30be7845f1506896f/aiohttp/client.py#L534-L535
        logging.debug('%s exception for url %r: %s', ex.__class__.__name__, url, ex)

    return (url, '')


async def main(agenda, start_url, pool_size, request_limit):
    # Use a limit-per-host to be a good web citizen. This would ideally be
    # better coordinated with the pool of async tasks, so that we don't have a
    # bunch of tasks for the same domain that are "running" but blocked from
    # actually doing work by this limit.
    conn = aiohttp.TCPConnector(limit_per_host=8)

    agenda.add_new_url(start_url) # seed with the one initial url

    async with aiohttp.ClientSession(connector=conn) as session:
        http_tasks = set()
        requests_started = 0

        # loop until we exhaust all links (not likely)
        while http_tasks or agenda.more_to_crawl():

            # top up the task pool
            while (len(http_tasks) < pool_size and
                    agenda.more_to_crawl() and
                    requests_started < request_limit):
                url = agenda.acquire_url()
                logging.debug("acquired: %s", url)
                http_tasks.add(asyncio.create_task(fetch(session, url)))
                requests_started += 1

            logging.debug("# http_tasks: %d", len(http_tasks))
            if not http_tasks:
                if requests_started == request_limit:
                    print('Reached limit of %d requests' % request_limit)
                else:
                    print('Ran out of links to follow.')
                break

            # Handle any completed requests, but don't wait for more than one --
            # that way, we can quickly add another request to the pool to
            # maximize throughput.
            done, _ = await asyncio.wait(http_tasks, return_when=asyncio.FIRST_COMPLETED)
            for d in done:
                http_tasks.remove(d)
                url, body = d.result()
                logging.debug("finished crawling %s", url)
                agenda.mark_crawled(url)

                links = crawl_html(body)
                for link in links:
                    agenda.add_new_url(link)

                # print report to stdout for this finished page
                print(url)
                for link in links:
                    print("  %s" % link)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: %s <start_url>' % sys.argv[0])
        raise SystemExit(1)

    start_url = sys.argv[1]
    pool_size = 20
    request_limit = 10000

    if '--debug' in sys.argv:
        log_level = logging.DEBUG
        logging.basicConfig(level=log_level)
    else:
        # disable noisy logging of caught errors from asyncio
        logging.disable()

    agenda = CrawlAgenda()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(agenda, start_url, pool_size, request_limit))
