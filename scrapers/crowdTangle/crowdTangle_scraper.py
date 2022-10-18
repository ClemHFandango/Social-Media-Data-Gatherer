#This file is part of Social Media Data Gatherer.
#
#Social Media Data Gatherer is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#Social Media Data Gatherer is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#You should have received a copy of the GNU General Public License along with Social Media Data Gatherer. If not, see <https://www.gnu.org/licenses/>. 

from queue import Empty
from time import time, mktime, sleep, perf_counter
import pandas as pd
import numpy as np
from scrapers.scraper import Scraper
from scrapers.crowdTangle import crowdTangle_auth
import requests
import json
import datetime
import re
import pickle
from tld import get_tld


class crowdTangle_scraper(Scraper):
    def __init__(self, query, language, country, data_dir):
        super().__init__(query, language, country, data_dir)
        self.search_endpoint = 'https://api.crowdtangle.com/posts/search'
        self.api_key = crowdTangle_auth.Auth_crowdTangle().API_key
        self.platform = 'crowdTangle'

    def scrape(self, start_time, end_time=None, flag=None):
        # TODO: FUCKAROUND WITH TIME FORMATS
        start_time = datetime.datetime.fromtimestamp(start_time).strftime('%Y-%m-%dT%H:%M:%S')
        end_time = None if end_time is None else datetime.datetime.fromtimestamp(end_time).strftime('%Y-%m-%dT%H:%M:%S')
        params = {'token': self.api_key, 'count': '100', 'startDate': start_time, 'endDate': end_time}

        query_res = []

        match flag:
            case 'lang':
                params['language'] = self.language
            case 'country':
                params['pageAdminTopCountry'] = self.country

        results_list = []
        pagination_token = None
        # params['and'] = self.query['and']
        params['searchTerm'] = self.query
        results = []
        response_err_counter = 0
        print("Now scraping: ", self.query, " (CrowdTangle)")
        while pagination_token != 'done':
            while response_err_counter < 5:
                try:
                    if pagination_token is None:
                        res = requests.get(self.search_endpoint, params)
                    else:
                        res = requests.get(pagination_token)
                        if 200 > res.json()['status'] > 300:
                            raise Exception('Live fast, die young')
                    res = json.loads(res.content.decode('utf-8'))['result']
                except Exception as e:
                    print("Error while scraping from Facebook/Instagram")
                    print(e)
                    response_err_counter += 1
                    sleep(300)
                    continue
                break
            if response_err_counter >= 5:
                print("Next Token: " + res['pagination'].get('nextPage', 'None'))
                pickling_on = open(self.data_dir + 'crowdTangle' + "_WIP.pickle", "wb")
                print("----------PICKLING----------")
                pickle.dump(self, pickling_on)
                pickling_on.close()
                quit()
            tic = perf_counter()
            # results = results + res['posts']
            for post in res['posts']:
                results_list.append(post)
                # print(post['message'])
                reaction_count = 0
                for reaction in post['statistics']['actual'].values():
                    reaction_count = reaction

                reactions = json.loads(json.dumps(post['statistics']['actual']))
                # print("The reaction count of the post is: ", reaction_count)

                date = datetime.datetime.strptime(post['date'], "%Y-%m-%d %H:%M:%S").timestamp()
                post_id = post['platformId']
                user_id = post['account']['id']
                user_link = post['account']['url']

                urls = []
                if post.get('link', False):
                    urls.append(post['link'])
                    parent_id = re.findall('(?<=\.).+?[^\/:](?=[?\/]|[`~!@#\$%\^&*()_+-=\[\]]*$)', post['link'])
                    parent_id = parent_id[0] if parent_id else None
                    if not parent_id:
                        self.update_url(parent_id, reaction_count, date)
                else:
                    parent_id = None
                domains = set()
                if post.get('expandedLinks', False):
                    for link in post['expandedLinks']:
                        if link.get('original', False):
                            url = link['original']
                            url, domain = self.clean_url(url)
                            if url is not None:
                                urls.append(url)
                                if domain is not None and post['platform'] not in domain:
                                    domains.add(domain)
                            # Old way of finding the domain
                            # If you don't look at it, it won't hurt you
                            '''
                            domain = re.findall(
                                '^(https?:\/\/)?(www?[0-9]?\.)?.+?[^\(?(/:)(\d{0,4})|](?=[?\/]'
                                + '|[`~!@#\$%\^&*()_+-=\[\]]*$)', link['original'])
                            if domain:
                                domain = domain[0]
                               #if "facebook.com" not in domain and "instagram.com" not in domain:
                               #     domains.add(domain)
                            '''                                
                # urls = ','.join(urls)
                #self.update_user(post_id, user_id, parent_id, reaction_count, date, platform=post['platform'].lower())

                text = ''
                if post.get('description', None) is not None:
                    text = post['description']
                if post.get('message', None) is not None:
                    text += post['message'] if text == '' else '\n' + post['message']
                if post.get('imageText', None) is not None:
                    text += post['imageText'] if text == '' else '\n' + post['imageText']

                self.posts[post_id] = {'time': date, 'author_id': user_id,
                                       'type_of_post': post['type'], 'parent_post_id': parent_id,
                                       'text': text, 'platform': post['platform'].lower(),
                                       'score': reactions, 'urls': urls, 'user_link': user_link,
                                       'domains': list(domains)}

            pagination_token = res['pagination'].get('nextPage', 'done')
            toc = perf_counter()
            # Being careful here, the rate limit isn't explicitly states so we abide by 5/min
            diff = 11 - (toc - tic)
            if diff > 0:
                sleep(diff)
        if len(self.posts) > 0:
            self.save_scraper_csv(self.platform, flag=flag)
        return results_list
