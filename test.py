#!/usr/bin/env python3

import asyncio
import unittest

from main import main, CrawlAgenda

# Note: This test is inherently brittle because it's dependent on the structure
# and timing of live websites on the internet. Ideally we would test against a
# webserver(s) with controlled contents, or use more sophisticated
# fuzzy/statistical tests. :-)

class CrawlerTest(unittest.TestCase):
    def test_crawl(self):
        agenda = CrawlAgenda()
        start_url = 'http://spacejam.com'
        pool_size = 20
        request_limit = 100 # fetch this many pages, then return

        loop = asyncio.get_event_loop()
        loop.run_until_complete(main(agenda, start_url, pool_size, request_limit))

        # original page. it has just a handful of links.
        self.assertIn('http://spacejam.com', agenda._crawled)

        # 2nd level pages. these have lots of links.
        self.assertIn('https://www.wbshop.com/', agenda._crawled)
        self.assertIn('https://policies.warnerbros.com/privacy/', agenda._crawled)
        self.assertIn('http://policies.warnerbros.com/terms/en-us/', agenda._crawled)
        self.assertIn('http://policies.warnerbros.com/terms/en-us/#accessibility', agenda._crawled)
        self.assertIn('https://policies.warnerbros.com/privacy/en-us/#adchoices', agenda._crawled)
        self.assertIn('http://www.omniture.com', agenda._crawled)

        # 3rd level pages. there's much less certainty about which of these will
        # be visited within the allotted number of requests, but we can
        # reasonably expect that at least some of them were fetched.
        urls = '''
        http://www.wb.com/customer-service
        https://policies.warnerbros.com/privacy/da-eu
        https://policies.warnerbros.com/privacy/de-eu
        https://policies.warnerbros.com/privacy/en-au
        https://policies.warnerbros.com/privacy/en-au
        https://policies.warnerbros.com/privacy/en-eu
        https://policies.warnerbros.com/privacy/en-us/affiliates/
        https://policies.warnerbros.com/privacy/es-eu
        https://policies.warnerbros.com/privacy/fr-eu
        https://policies.warnerbros.com/privacy/it-eu
        https://policies.warnerbros.com/privacy/ja-jp
        https://policies.warnerbros.com/privacy/ko-kr
        https://policies.warnerbros.com/privacy/nb-eu
        https://policies.warnerbros.com/privacy/nl-eu
        https://policies.warnerbros.com/privacy/zh-cn
        https://policies.warnerbros.com/privacy/zh-hk
        https://www.facebook.com/wbshop'''.strip().split()

        results = [ u in agenda._crawled for u in urls ]
        matches = [ u for u in results if u ]
        expected_hit_rate = 0.6 # i usually got 90%+, but it depends on network timing
        print("3rd level page hit rate: %f" % (len(matches) / len(results)))
        self.assertTrue((len(matches) / len(results)) >= expected_hit_rate)


if __name__ == '__main__':
    unittest.main()
