#This file is part of Social Media Data Gatherer.
#
#Social Media Data Gatherer is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#Social Media Data Gatherer is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#You should have received a copy of the GNU General Public License along with Social Media Data Gatherer. If not, see <https://www.gnu.org/licenses/>. 


from time import sleep
import langdetect
from langdetect import detect
import praw
import prawcore.exceptions
import requests
import scrapers.reddit.auth as auth
from queryParser import eval_claim
import re
from scrapers.scraper import Scraper


def verbose_post(post):
    # print some generic stuff
    print("=ID: ", post.id)
    print("  Title: ", post.title)
    print("  Score: ", post.score)
    print("  URL: ", post.url.encode('ascii', 'ignore'))
    print("  Text: ", post.selftext[:120])
    print('-posts-')
    print("Name: ", post.author.name)


def url_exists(path):
    """
    :param: path: the path to a url
    :return: True if the url exists, False if not
    """
    return requests.head(path).status_code == requests.codes.ok


def is_url_image(image_url):
    """
    :param: image_url: the path to an image url (will be checked if url exists)
    :return: True if url leads to an image, False if not
    """
    image_formats = ("image/png", "image/jpeg", "image/jpg")
    try:
        r = requests.head(image_url)
    except Exception as e:
        return False
    return True if r.headers.get("content-type", None) in image_formats and url_exists(image_url) else False


class Reddit_scraper(Scraper):
    def __init__(self, query, language, country, data_dir, compiled_code):
        super().__init__(query, language, country, data_dir)
        self.language = language
        self.country = ""
        self.comments = {}
        self.platform = 'reddit'
        self.compiled_code = compiled_code
        self.client = praw.Reddit(client_id=auth.Auth().clientid,
                                  client_secret=auth.Auth().clientsecret,
                                  user_agent="my bot",
                                  username=auth.Auth().username,
                                  password=auth.Auth().password)
        print('Signed in as: ', auth.Auth().username)

    def get_submission_comments(self, comment, all_comments, verbose=True):
        all_comments.append(comment)
        if not hasattr(comment, "replies"):
            replies = comment.comments()
            if verbose:
                print("fetching (" + str(len(all_comments)) + " comments fetched total)")
        else:
            replies = comment.replies
        for child in replies:
            self.get_submission_comments(child, all_comments, verbose=verbose)

    def get_by_submission_id(self, submission_id, verbose=True):
        """
        Returns a list of comments (CommentForest object) of a submission
        :param submission_id: The id of the submission
        :param verbose: Debugging information printed
        :return: A list of the comments out of the submission
        """
        submission = self.client.submission(submission_id)
        comments = submission.comments
        comments_list = []
        for comment in comments:
            self.get_submission_comments(comment, comments_list, verbose=verbose)
        return comments_list

    def update_links(self, post):
        # update links, skip images
        links_set = set()
        domains = set()
        # permalink is "in" url if the url is just the reddit post, and we skip it along with pictures, skip comments
        if not isinstance(post, praw.models.reddit.comment.Comment):
            text = post.selftext
            if post.permalink not in post.url and not is_url_image(post.url):
                #Not using users
                #self.update_user(post.id, post.url, None, post.score, post.created_utc)
                url, domain = self.clean_url(post.url)
                if domain is not None:
                    domains.add(domain)
                if url is not None:
                    links_set.add(url)
        else:
            text = post.body

        # --------------------------------------------------------
        # Abandon all hope, ye who enter here. There be dragons.|
        # --------------------------------------------------------

        # regex taken from https://pytutorial.com/check-strig-url
        regex = re.compile(
            r'^(?:http|ftp)s?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        for url in re.findall('\[.*?\]\((.*?)\)', text):
            if re.match(regex, url) is not None:
                url, domain = self.clean_url(url)
                if domain is not None:
                    domains.add(domain)
                if url is not None:
                    links_set.add(url)
                
        
        #Not using users
        #for link in links_list:
        #    self.update_user(post.id, link, None, post.score, post.created_utc)
        return list(links_set), list(domains)

    def update_reddit_comments(self, comment_forests, parent_id, verbose=True):
        """
        Extracts information out of a list of reddit comments that is found under a post.
        :param verbose: shows debug information
        :param comment_forests: Comment lists in PRAW are objects called "CommentForest", this is the list.
        :param parent_id: The id of the post that contained this CommentForest
        :return: Nothing, update the values of self.posts and call self.update_user
        """
        # get comments from post and update users from comments, note: no replies to comments are taken
        print("Scraping comments of post.")
        for comment_forest in comment_forests.values():
            for comment in comment_forest:
                # check if comment exists in search results
                # TODO: test is comment exists in database (untested)
                if comment.id in self.posts.keys():
                    print('found a comment from the results')
                else:
                    # skipping through comments with deleted authors
                    try:
                        if hasattr(comment, 'author') and comment.author is not None and hasattr(comment.author, 'id'):
                            #Update user functionality is not employed currently
                            #self.update_user(comment.id, comment.author.id, comment.submission.id, comment.score,
                            #                 comment.created_utc)
                            links_list, domains = self.update_links(comment)
                            self.posts[comment.id] = {'time': comment.created_utc, 'author_id': comment.author.id,
                                                      'type_of_post': 'comment', 'parent_post_id': parent_id,
                                                      'controversiality':
                                                          comment.controversiality, 'urls': links_list,
                                                      'score': {'score': comment.score, 'commentCount': 0},
                                                      'text': comment.body, 'platform': self.platform, 'domains': domains}
                    except prawcore.exceptions.NotFound as e:
                        print("Got a 404. Debug:\n", e)
        if verbose:
            print("\nFinished scraping comments.\n")

    # TODO: check if I take multiple links
    def scrape(self, query, start_time, end_time, subreddit='all', verbose=False):
        if verbose:
            print("Subreddit: ", subreddit)
            print("Keyword: ", query)

        subreddit = self.client.subreddit(subreddit)

        try:
            resp = subreddit.search(query=query, sort="new", limit=None)
        except Exception as e:
            print("Error with getting response.")
            print(e)
            sleep(100)

        # TODO: figure out sleeping to keep within rate limits (Alex)
        try:
            for post in resp:
                # end if post is older than end_time that we set
                if post.created_utc <= start_time:
                    break
                if post.created_utc > end_time:
                    continue

                # field for comments of post
                comment_forests = {}

                # check if claim is relevant
                if eval_claim(self.compiled_code, post.selftext) or eval_claim(self.compiled_code, post.title):
                    # print debugging stuff if verbose is true
                    if verbose:
                        verbose_post(post)
                    # skipping through posts with deleted authors
                    if post.author is None:
                        continue

                    lang_selftext, lang_title = "", ""
                    error_check = 0
                    try:
                        if post.selftext != "":
                            lang_selftext = detect(post.selftext)
                    except langdetect.LangDetectException as e:
                        error_check += 1

                    try:
                        if post.title != "":
                            lang_title = detect(post.title)
                    except langdetect.LangDetectException as e:
                        error_check += 1

                    # if we get TWO errors, something's wrong
                    if error_check > 1 and verbose:
                        print("Cannot find language of post, skipping.")
                        if hasattr(post, post.url):
                            print("Post URL: ", post.url)

                    # skip if we get empty language fields
                    if lang_selftext == lang_title == "":
                        continue

                    if lang_selftext != "" and lang_selftext != self.language:
                        continue
                    elif lang_title != "" and lang_title != self.language:
                        continue

                    # update user, specially handle crossposts
                    if hasattr(post, "crosspost_parent"):
                        # TODO: test if [0] is OP
                        # checking if the id of the author in post is the same on crosspost (ids here are like t3_*id*)
                        if 'author_fullname' in post.crosspost_parent_list[0].keys() and hasattr(post.author, 'id'):
                            if post.author.id == post.crosspost_parent_list[0]['author_fullname'][3:]:
                                self.update_user(post.id, post.author.id, None, post.score,
                                                 post.created_utc)
                            else:
                                self.update_user(post.id, post.author.id,
                                                 post.crosspost_parent_list[0]['author_fullname'][3:],
                                                 post.score,
                                                 post.created_utc)
                    else:
                        try:
                            if post.author is not None and hasattr(post.author, 'id'):
                                self.update_user(post.id, post.author.id, None, post.score,
                                                 post.created_utc)
                        except prawcore.exceptions.NotFound as e:
                            print("Got a 404, continuing. Debug:")
                            print(e)
                    # track spreader links
                    links_list, domains = self.update_links(post)

                    # check if post is submission and has an author and the author has an id (= is not banned)
                    try:
                        if isinstance(post,
                                      praw.models.reddit.submission.Submission) and post.author is not None and hasattr(
                                      post.author, 'id'):
                            self.posts[post.id] = {'time': post.created_utc, 'author_id': post.author.id,
                                                   'type_of_post': 'submission', 'parent_post_id': None,
                                                   'controversiality': 0, 'urls': links_list,
                                                   'score': {'score': post.score,
                                                             'commentCount': post.comments.__len__()},
                                                   'text': post.title + '\n' + post.selftext, 'platform': self.platform,
                                                   'user_link': 'https://www.reddit.com/u/' + str(post.author), 'domains': domains}
                            #if len(self.posts[post.id]['urls']) > 1:
                            #    print(self.posts[post.id]['urls'])
                            # get comments of submission
                            if hasattr(post, "comments"):
                                comment_forests[post.id] = post.comments

                        # if it is a comment
                        elif isinstance(post, praw.models.reddit.comment.Comment):
                            self.posts[post.id] = {'time': post.created_utc, 'author_id': post.author.id,
                                                   'type_of_post': 'comment', 'parent_post_id': None,
                                                   'controversiality': post.controversiality, 'platform': self.platform,
                                                   'score': {'score': post.score,
                                                             'commentCount': post.comments.__len__()},
                                                   'text': post.selftext, 'user_link': 'https://www.reddit.com/u/' + str(post.author),
                                                   'domains': domains}
                            #print("We got a comment")
                        else:
                            print("\nProblem with determining post type. Post ID: ")
                            print(post, '\n')
                    except prawcore.exceptions.NotFound as e:
                        print("Got a 404 on determining post type. Exception:\n", e)

                # process and save comments of post
                # self.update_reddit_comments(comment_forests, post.id)
            if len(self.posts) > 0:
                self.save_scraper_csv(platform='reddit', flag='lang')
        except KeyboardInterrupt:
            print("Scraping cancelled by user. Last post not saved.")
            pass
