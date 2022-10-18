#This file is part of Social Media Data Gatherer.
#
#Social Media Data Gatherer is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#Social Media Data Gatherer is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#You should have received a copy of the GNU General Public License along with Social Media Data Gatherer. If not, see <https://www.gnu.org/licenses/>. 


from queue import Empty
import re
from time import time, mktime, sleep, perf_counter
import tweepy
import pandas as pd
import numpy as np
# from datetime import datetime
from scrapers.scraper import Scraper
from scrapers.twitter import twitter_auth
import pickle
import datetime
from tld import get_tld
import pandas as pd
import os


def determine_tweet_type(tweet):
    if tweet.get('referenced_tweets', None) is None:
        tweet_type = "original_tweet"
    else:
        # print(tweet['referenced_tweets'][0]['type'])
        tweet_type = tweet['referenced_tweets'][0]['type']  # possible types: (retweeted, quoted, replied_to)
    return tweet_type


class Twitter_scraper(Scraper):
    def __init__(self, query, language, country, data_dir):
        super().__init__(query, language, country, data_dir)
        self.platform = 'twitter'
        self.client = tweepy.Client(bearer_token=twitter_auth.Auth_twitter().Bearer_token,
                                    consumer_key=twitter_auth.Auth_twitter().API_key,
                                    consumer_secret=twitter_auth.Auth_twitter().API_key_secret,
                                    wait_on_rate_limit=True)

    # .strftime('%Y-%m-%dT%H:%M.%S0Z') USEFUL FOR DIPSPLAYING LATER

    def parse_claim_tweets(self, tweets):
        for raw_tweet in tweets:
            domains = set()
            tweet = dict(raw_tweet)
            # self.raw_tweets.append(tweet)
            type_of_post = determine_tweet_type(tweet)

            author_id = str(tweet['author_id'])
            created_at = tweet['created_at'].timestamp()
            # Add Tweet to list of tweets
            post_id = str(tweet['id'])

            # retweeted, quoted, replied_to
            public_metrics = tweet['public_metrics']

            engagement_count = public_metrics['retweet_count'] + public_metrics['reply_count'] + \
                               public_metrics["quote_count"] + public_metrics["like_count"]
            score = {'retweet_count': public_metrics['retweet_count'], 'reply_count': public_metrics['reply_count'],
                     'quote_count': public_metrics['quote_count'], 'like_count': public_metrics['like_count']}
            urls = []
            base_urls = []
            if tweet.get('entities', False):
                base_urls = tweet['entities'].get('urls', [])

            if base_urls is not Empty:
                # print(base_urls)
                for raw_url in base_urls:
                    url, domain = self.clean_url(raw_url['expanded_url'])
                    # print(filtered_url)
                    if domain is not None and 'twitter.com' not in domain:
                        domains.add(domain)
                    if url is not None and 'twitter.com' not in url:
                        urls.append(url)
                        #This feature isn't being used
                        #self.update_url(domain, engagement_count, created_at)

            # Turn the list into a string of comma delimited URLs so that it can be nicely saved as CSV
            # urls = ','.join(urls)
            self.posts[post_id] = {'time': created_at, 'author_id': author_id,
                                   'type_of_post': type_of_post, 'domains': list(domains),
                                   'conversation_id': str(tweet['conversation_id']), 'text': tweet['text'],
                                   'platform': self.platform, 'score': score, 'urls': urls,
                                   'parent_post_id': None}

            # There should be some adjustments here, perhaps some function to give weights on retweets, replies, etc.
            match type_of_post:
                case "original_tweet":
                    if domains is Empty:
                        self.update_user(None, author_id, None, engagement_count, created_at)
                    else:
                        for base_url in domains:
                            # TODO ADD MULTIPLE URL HANDLING
                            self.update_user(None, author_id, base_url, engagement_count, created_at)
                case "retweeted":
                    self.posts[post_id]['parent_post_id'] = tweet['referenced_tweets'][0][
                        'id']  # FIND THE THING TO PUT HERE
                    self.update_user(tweet['referenced_tweets'][0]['id'], author_id, None, 1, created_at)

                # Here only the score and user is registered. It is not untill we have all the tweets regarding
                # the claim that we may update the parent. If it is true that there is a URL in the OP, then
                # there is of course no post ID for us to observe.
                case "replied_to" | "quoted":
                    if domains is None:
                        self.posts[str(tweet['id'])]['parent_id'] = None  # tweet['in_reply_to_user_id']
                        self.update_user(tweet['referenced_tweets'][0]['id'], author_id, None, engagement_count,
                                         created_at)
                    else:
                        self.update_user(None, author_id, None, engagement_count, created_at)

    def add_users_from_likes(self):
        for post_id in self.posts:
            # A retweet shares the same likes as that of the OP. Therefore, we skip all retweets.
            if self.posts[post_id]['type_of_post'] == 'retweeted':
                continue
            next_token = None
            # First pass, getting tweets that contain the claim keywords
            while next_token != 'done':
                response_err_counter = 0
                while response_err_counter < 5:
                    try:
                        response = self.client.get_liking_users(post_id, pagination_token=next_token)
                    except Exception as e:
                        print("Error while scraping users from likes. Error:\n", e)
                        response_err_counter += 1
                        sleep(100)
                        continue
                    break
                if response_err_counter >= 5:
                    print('Post ID: ' + post_id)
                    print("Next Token: " + response.meta.get('next_token', 'done'))
                    quit()
                tic = perf_counter()
                next_token = response.meta.get('next_token', 'done')
                # If there are no "liked tweets" then
                if response.data is None:
                    continue
                for user in response.data:
                    user_id = str(dict(user)['id'])
                    self.update_user(post_id, user_id, str(self.posts[post_id]['author_id']), 0, np.inf)
                toc = perf_counter()
                diff = 12 - (toc - tic)
                if diff > 0:
                    sleep(diff)

    # Checks the users that are following the user, then updates them in the user list.
    def check_following(self):
        # users = self.users
        for user_id in self.users:
            # Skip over URLs (as we treat URLs as user ids)
            if 'http' in user_id:
                continue
            next_token = None
            while next_token != 'done':
                response_err_counter = 0
                while response_err_counter < 5:
                    try:
                        response = self.client.get_users_followers(user_id, pagination_token=next_token)
                    except:
                        print("Error while scraping users from following")
                        response_err_counter += 1
                        sleep(100)
                        continue
                    break

                if response_err_counter >= 5:
                    print('User ID: ' + user_id)
                    print("Next Token: " + response.meta.get('next_token', 'done'))
                    quit()
                tic = perf_counter()
                next_token = response.meta.get('next_token', 'done')

                # If response.data is equal to none there the user isn't following anyone.
                if response.data is None:
                    continue
                for raw_user in response.data:
                    followed_user_id = str(dict(raw_user)['id'])
                    if followed_user_id in self.users:
                        followed_user = self.users[followed_user_id]
                        if followed_user['earliest_date'] < self.users[user_id]['earliest_date']:
                            self.update_user(followed_user['parent_post_id'], user_id, \
                                             followed_user['user_id_first_engage'], 0, followed_user['earliest_date'])
                            # print("UPDATING")
                toc = perf_counter()
                diff = 60 - (toc - tic)
                if diff > 0:
                    sleep(diff)

    # The problem with this function is that it adds ALL users from a conversation, even if only 1 of the replies in
    # the conversation mentions the claim. We cannot say that all users have interacted with this claim unfortunately.
    def add_users_from_replies(self, start_time, end_time):
        for tweet in self.posts:
            if self.posts[tweet]['type_of_post'] != 'retweeted':
                conversation_id = self.posts[tweet]['conversation_id']
                tweet_fields = ['author_id', 'created_at', 'referenced_tweets', ]
                query_con = "conversation_id:" + str(conversation_id)

                # get conversation using conversation_id
                next_token = None
                # print("Finding replies from tweet id: " + str(conversation_id))
                while next_token != 'done':
                    response_err_counter = 0
                    while response_err_counter < 5:
                        try:
                            response = self.client.search_all_tweets(query=query_con,
                                                                     next_token=next_token,
                                                                     start_time=start_time,
                                                                     end_time=end_time,
                                                                     tweet_fields=tweet_fields,
                                                                     max_results=500)
                        except Exception as e:
                            print("Error while scraping users from replies. Error:\n", e)
                            response_err_counter += 1
                            sleep(100)
                            continue
                        break

                    if response_err_counter >= 5:
                        print('Tweet ID: ' + tweet)
                        print("Next Token: " + response.meta.get('next_token', 'done'))
                        quit()
                    tic = perf_counter()
                    next_token = response.meta.get('next_token', 'done')
                    if response.data is not None:
                        for raw_tweet_con in response.data:
                            tweet = dict(raw_tweet_con)
                            post_id = str(tweet['id'])
                            if tweet.get('referenced_tweets', None) is not None:
                                for raw_ref in tweet['referenced_tweets']:
                                    referenced_tweet = dict(raw_ref)
                                    ref_post_id = str(referenced_tweet['id'])
                                    if ref_post_id in self.posts:
                                        self.update_user(post_id, str(tweet['author_id']), \
                                                         self.posts[ref_post_id]['author_id'], 0,
                                                         tweet['created_at'].timestamp())

                    # Save data incase of failure
                    # pickling_on = open("twitter_scraper/data/WIP.pickle", "wb")
                    # pickle.dump([self, next_token], pickling_on)
                    # pickling_on.close()
                    toc = perf_counter()
                    diff = 3 - (toc - tic)
                    if diff > 0:
                        sleep(diff)

    # This function runs through all the users, checking if the tweet they responded to mentions the claim of
    # interest. If it does it updates the user id of first engagement for that user. Maybe this function should also
    # update the time, however we cannot know when someone retweets a tweet but we DO know when someone quote tweets
    # or replies to a tweet.
    def update_rt_qt_r(self):
        '''
        for post_id in self.posts:
            if self.posts[post_id]['type_of_tweet'] != "retweeted":
                print(post_id)
        '''
        for user in self.users:
            parent_post_id = self.users[user]['parent_post_id']
            # We skip over those posts that are not in our self.posts structure as this means they are not related
            # to the claim and therefore not considered to be parents. We also skip over any post where a user has
            # retweeted or quote tweeted themselves
            if parent_post_id in self.posts and self.posts['parent_post_id']['author_id'] != parent_post_id:
                self.users[user]['user_id_first_engage'] = self.posts[parent_post_id]['author_id']
                # self.users[user_key]['earliest_date'] = self.posts[parent_post_id]['time']

    def get_claim_tweets(self, start_time, end_time,  # datetime.utcnow().isoformat("T") + "Z",
                         tweet_fields=['created_at', 'id',
                                       'author_id',
                                       'conversation_id',
                                       'in_reply_to_user_id',
                                       'referenced_tweets',
                                       'entities',
                                       'public_metrics',
                                       'source'], flag=None):
        since_id = None
        next_token = None
        results = []

        match flag:
            case 'lang':
                self.query += " lang:" + self.language
            case 'country':
                self.query += " place_country:" + self.country

        # First pass, getting tweets that contain the claim keywords
        # sleep(11)
        while next_token != 'done':
            response_err_counter = 0
            while response_err_counter < 5:
                try:

                    print('Now scraping: ', self.query, " (Twitter)")
                    response = self.client.search_all_tweets(query=self.query,
                                                             since_id=since_id,
                                                             start_time=start_time,
                                                             end_time=end_time,
                                                             next_token=next_token,
                                                             tweet_fields=tweet_fields,
                                                             media_fields=['url'],
                                                             max_results=500)
                except Exception as e:
                    print("Error while scraping users from query")
                    print(e)
                    response_err_counter += 1
                    sleep(100)
                    continue
                break
            if response_err_counter >= 5:
                print("Next Token: " + response.meta.get('next_token', 'done'))
                quit()
            tic = perf_counter()
            # Code to fetch the most recent ID
            if response.data is not None:
                self.parse_claim_tweets(response.data)
            else:
                print("No Tweets found")
                next_token = 'done'
                toc = perf_counter()
                diff = 3 - (toc - tic)
                if diff > 0:
                    sleep(diff)
                return
            next_token = response.meta.get('next_token', 'done')
            toc = perf_counter()
            diff = 3 - (toc - tic)
            if diff > 0:
                sleep(diff)
        print('Processed ' + str(len(self.posts)) + " tweets")
        # Only save if we have found any users
        if len(self.posts) > 0:
            self.save_scraper_csv(self.platform, flag=flag)

    def scrape(self, start_time, end_time=None, flag=None):
        start_time = datetime.datetime.fromtimestamp(start_time).strftime('%Y-%m-%dT%H:%M:%S.%UZ')
        end_time = end_time if end_time is None else \
            datetime.datetime.fromtimestamp(end_time).strftime('%Y-%m-%dT%H:%M:%S.%UZ')

        # Find the tweets that can be found by searching with the logic query
        print("----------Finding Tweets----------")
        results = self.get_claim_tweets(start_time, end_time, flag=flag)
        # Update the retweets, quote tweets and replies before getting the users from the replies as this way there
        # are less users to go through
        print("----------Updating the Retweets, Quote Tweets and Replies----------")
        # self.update_rt_qt_r()
        # Second pass, getting the list of users who liked each tweet and adding them to our graph with strength 0
        print("----------Getting users from likes----------")
        # self.add_users_from_likes()
        # Fetch those users that have replied to a tweet containing the COI but did not contain the associated keywords
        print("----------Getting users from replies----------")
        # self.add_users_from_replies(start_time, end_time)
        # Third pass, getting the list of users who replied to/retweeted/quoted each tweet
        # -Get the conversation id -> put it into the query -> get tweets -> only keep reply tweets
        # -Then search the parent ID for each tweet to see if it's in our list of tweets, if it is,
        # update user list with first engagement

    # For testing + backup purposes.
    def save_df(self, platform=None, flag=None):
        platform = self.platform if hasattr(self, "platform") else ""

        shortened_query = re.sub("(\")|( lang:..)|( place_country:..)|(https?:/{0,2})|/.*$", '', self.query)

        match flag:
            case 'lang':
                flag_str = flag + '_' + self.language
                folder_str = self.language
            case 'country':
                flag_str = flag + '_' + self.country
                folder_str = self.country

        if not os.path.isdir(self.data_dir + 'df/' + 'users'):
            os.mkdir(self.data_dir + 'df/' + 'users')

        if not os.path.isdir(self.data_dir + 'df/' + 'users/' + flag):
            os.mkdir(self.data_dir + 'df/' + 'users/' + flag)

        path = self.data_dir + 'df/' + 'users/' + flag + '/' + folder_str
        if not os.path.isdir(path):
            os.mkdir(path)

        file_name = path + '/' + shortened_query + "_" + flag_str + "_users" + ".csv"
        if os.path.isfile(file_name):
            self.df.to_csv(file_name, mode='a', index=False, header=False)
        else:
            self.df.to_csv(file_name, index=False)
