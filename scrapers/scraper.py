# This file is part of Social Media Data Gatherer.
#
# Social Media Data Gatherer is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
# Social Media Data Gatherer is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with Social Media Data Gatherer. If not, see <https://www.gnu.org/licenses/>.


import numpy as np
import pickle
import csv
import os
import threading
import re
import pandas as pd
from datetime import date
from tldextract import extract
import urlexpander

csv_writer_lock = threading.Lock()


class Scraper(object):
    def __init__(self, query, language, country, data_dir):
        self.data_dir = data_dir
        self.users = {}
        self.posts = {}
        self.query = query
        self.language = language
        self.country = country
        self.platform = None
        self.checked_urls = dict()
        self.known_shorteners = urlexpander.constants.all_short_domains.copy() + ['youtu.be']

    # init for reddit
    @classmethod
    def reddit_init(cls, query, data_dir, compiled_code):
        return cls(query=query, data_dir=data_dir, language=None, country=None)

    # This function is now defunct
    def __add__(self, other):
        return [self.users.update(other.users), self.posts.update(other.posts)]

    # update user to the scraper object, get information about the user
    def update_user(self, post_id, user_id, parent_id, score, date, platform=None):
        platform = self.platform if platform is None else platform
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {'earliest_date': np.inf, 'parent_post_id': post_id,
                                   'engagement_count': score, 'user_id_first_engage': None, 'platform': platform}
            # TODO: Handle if platform is in [twitter, facebook, etc]
        else:
            self.users[user_id]['engagement_count'] += score

        if date < self.users[user_id]['earliest_date']:
            self.users[user_id]['earliest_date'] = date
            self.users[user_id]['user_id_first_engage'] = parent_id
            self.users[user_id]['parent_post_id'] = post_id

    def update_url(self, url, score, date):
        if url not in self.users:
            self.users[url] = {'earliest_date': np.inf, 'parent_post_id': None,
                               'engagement_count': score, 'user_id_first_engage': None, 'platform': 'other'}
        else:
            self.users[url]['engagement_count'] += score

        if date < self.users[url]['earliest_date']:
            self.users[url]['earliest_date'] = date

    # DEPECRATED. This function shouldn't be used. Simply save as CSV instead.
    def save_scraper(self, platform=None):
        platform = self.platform if hasattr(self, "platform") else platform
        # type_scraper = type(self).__name__.split('_')[0].lower()
        if not hasattr(self, 'compiled_code'):
            with open(self.data_dir + platform + "_processed.pickle", "wb") as f:
                pickle.dump(self, f)
                f.close()
        else:
            code = self.compiled_code
            self.compiled_code = None
            with open(self.data_dir + platform + "_processed.pickle", "wb") as f:
                pickle.dump(self, f)
                f.close()
            self.compiled_code = code

    def save_posts_csv(self, flag=None):
        # Strip away the possible Twitter language part of the search to avoid long file names.
        # Strip away any HTTP elements or '/' characters so we can actually save the file
        # shortened_query = re.sub("(\")|( lang:..)|( place_country:..)|(https?:/{0,2})|/.*$", '', self.query)

        df = pd.DataFrame(columns=['id', 'time', 'author_id', 'type_of_post', 'domains', 'score', 'text',
                                   'conversation_id', 'platform', 'urls', 'user_link', 'parent_post_id',
                                   'controversiality', 'likeCount', 'shareCount', 'commentCount', 'loveCount',
                                   'wowCount', 'hahaCount', 'sadCount', 'angryCount', 'thankfulCount', 'careCount',
                                   'favoriteCount', 'retweet_count', 'like_count', 'reply_count', 'quote_count',
                                   'country', 'language', 'query'])

        post_dict_keys = ['time', 'author_id', 'controversiality', 'type_of_post', 'conversation_id', 'text',
                          'platform', 'score',
                          'urls', 'parent_post_id', 'user_link']

        platform_responses = {'twitter': ['retweet_count', 'like_count', 'reply_count', 'quote_count'],
                              'crowdTangle': ['likeCount', 'shareCount', 'commentCount', 'loveCount',
                                              'wowCount', 'hahaCount', 'sadCount', 'angryCount', 'thankfulCount',
                                              'careCount',
                                              'favoriteCount'],
                              'reddit': ['score', 'commentCount']}

        # Populate the dataframe with ids
        df['id'] = list(self.posts.keys())
        # Set the default 
        for key in platform_responses.keys():
            for col in platform_responses[key]:
                df[col] = 0

        df['query'] = re.sub("(\")|( lang:..)|( place_country:..)|(https?:/{0,2})|/.*$", '', self.query)

        match flag:
            case 'lang':
                df['language'] = self.language
                df['country'] = ''
            case 'country':
                df['country'] = self.country
                df['language'] = ''

        for key in post_dict_keys:
            match [key, self.platform]:
                case ['score', _]:
                    scores = [{r_key: x[key][r_key] for r_key in platform_responses[self.platform] if r_key in x[key]}
                              for x in list(self.posts.values())]
                    df.update(pd.json_normalize(scores))
                    continue

                case ['conversation_id', 'twitter']:
                    df['conversation_id'] = [x[key] for x in list(self.posts.values())]
                    # TODO ADD DEFAULT TO CONVERSATION ID
                    continue

                # Default case for Facebook and Reddit since conversation ID doesn't exist
                case ['conversation_id', _]:
                    df['conversation_id'] = ''
                    continue

                case ['user_link', 'twitter' | 'reddit']:
                    df['user_link'] = ''
                    continue

                case ['parent_post_id', 'crowdTangle']:
                    df['parent_post_id'] = ''
                    continue

                case ['parent_post_id', _]:
                    df['parent_post_id'] = ['' if not x[key] else x[key] for x in list(self.posts.values())]
                    continue

                case ['controversiality', 'twitter' | 'crowdTangle']:
                    df['controversiality'] = 0
                    continue

                case [_, _]:
                    df[key] = [x[key] for x in list(self.posts.values())]

        file_name = self.data_dir + str(date.today()) + "_results" + ".csv"
        if not os.path.isfile(file_name):
            df.to_csv(file_name, index=False, header=True, sep='\t', mode='w+')
        else:
            df.to_csv(file_name, index=False, header=False, sep='\t', mode='a')

    # The csv writing part of this function needs to be rewritten, it will cause a headache if used as is.
    def save_users_csv(self, platform=None, flag=None):
        platform = self.platform if hasattr(self, "platform") else ""

        def convert(dict_of_dicts):
            return [(lambda d: d.update(id=key) or d)(val) for (key, val) in dict_of_dicts.items()]
            # return ", ".join("%s : %s" % (key, value) for key, value in dct.items())

        user_list = convert(self.users)

        shortened_query = re.sub("(\")|( lang:..)|( place_country:..)|(https?:/{0,2})|/.*$", '', self.query)

        match flag:
            case 'lang':
                flag_str = flag + '_' + self.language
                folder_str = self.language
            case 'country':
                flag_str = flag + '_' + self.country
                folder_str = self.country

        if not os.path.isdir(self.data_dir + 'users/' + flag):
            os.mkdir(self.data_dir + 'users/' + flag)

        path = self.data_dir + 'users/' + flag + '/' + folder_str
        if not os.path.isdir(path):
            os.mkdir(path)

        file_name = path + '/' + shortened_query + "_" + flag_str + "_users" + ".csv"
        with open(file_name, "a") as f:
            with csv_writer_lock:
                writer = csv.DictWriter(f, user_list[0].keys(), delimiter='\t')
                if os.stat(file_name).st_size == 0:
                    writer.writeheader()
                writer.writerows(user_list)
            f.close()

    def save_scraper_csv(self, platform=None, flag=None):
        # self.save_users_csv(platform, flag)
        self.save_posts_csv(flag=flag)

    def clean_url(self, url):

        # Some incredibly basic checks to see if the URL is valid (to save time on bad function calls
        # Derive the domain of the URL. 

        def get_domain(url_):
            domain_ = ''
            try:
                tsd, td, tsu = extract(url_)  # www.hostname.com -> www, hostname, com
                if td != '' and tsu != '':
                    domain_ = td + '.' + tsu  # www.hostname.com -> hostname.com
            except:
                # If tld cannot extract the URL from the URL, don't add the URL to the URL list.
                pass
            return domain_

        # Remove twitter URLs from Twitter posts, these URLs just add clutter as each retweet, quote, etc.
        # contain these URLs (this information is still captured in parent_post_id and conversation_id)
        if 'twitter.com' in url and self.platform == 'twitter':
            return None, None

        # Fix as for some reason urlexpander fails to expand some urls if they do not contain the http prefix.
        url = url if re.search('^(http|https)://', url) else 'https://' + url
        domain = get_domain(url)

        # If we've already checked this URL, no need to do the work again.
        if url in self.checked_urls:
            url = self.checked_urls[url]
            # Get new domain from the expanded URL
            # Guarunteed not to fail as it already exists in the checked_urls.
            domain = get_domain(url)
        # If the domain is in our list of known shorteners then the URL must be expanded.
        elif domain in self.known_shorteners:
            try:
                expanded_url = urlexpander.expand(url)
                if not '__CONNECTIONPOOL_ERROR__' in expanded_url:
                    self.checked_urls[url] = expanded_url
                    url = expanded_url
                # Collect the "real" domain rather than the shortener domain.
                domain = get_domain(url)

            except:
                # If the URL fails to resolve, we skip it
                print("failed to expand: " + url)
                return None, None

        return url, domain
