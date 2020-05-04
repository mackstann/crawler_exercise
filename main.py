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
    * Efficiently return one new (arbitrary) uncrawled URL at a time.
    * Keep memory use reasonable by not storing duplicate URLs.
    * Store links in the order they're found, so we crawl progressively from the
      starting point outward.
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
    links = set()

    class LinkParser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag != 'a':
                return
            href = dict(attrs).get('href')
            if not href:
                return
            url = urlparse(href)
            if url.scheme in ('http', 'https'):
                links.add(href)

    LinkParser().feed(body)
    return links


async def fetch(session, url):
    async with session.get(url) as response:
        return (url, await response.text())


async def main(start_url, pool_size):
    # Use a limit-per-host to be a good web citizen. This would ideally be
    # better coordinated with the pool of async tasks, so that we don't have a
    # bunch of tasks for the same domain that are "running" but blocked from
    # actually doing work by this limit.
    conn = aiohttp.TCPConnector(limit_per_host=8)

    agenda = CrawlAgenda()
    agenda.add_new_url(start_url) # seed with the one initial url

    async with aiohttp.ClientSession(connector=conn) as session:
        http_tasks = set()

        # loop until we exhaust all links
        while http_tasks or agenda.more_to_crawl():

            # top up the task pool
            while len(http_tasks) < pool_size and agenda.more_to_crawl():
                url = agenda.acquire_url()
                logging.debug("acquired: %s", url)
                http_tasks.add(asyncio.create_task(fetch(session, url)))

            logging.debug("# http_tasks: %d", len(http_tasks))

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
    log_level = logging.DEBUG if '--debug' in sys.argv else logging.INFO
    pool_size = 100

    logging.basicConfig(level=log_level)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(start_url, pool_size))
