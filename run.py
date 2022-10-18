#This file is part of Social Media Data Gatherer.
#
#Social Media Data Gatherer is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#Social Media Data Gatherer is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#You should have received a copy of the GNU General Public License along with Social Media Data Gatherer. If not, see <https://www.gnu.org/licenses/>. 

import sys
from scrapers.reddit import reddit_scraper
from scrapers.twitter import twitter_scraper
from scrapers.crowdTangle import crowdTangle_scraper
import queryParser
import os
import argparse


def safe_makedir(dir_path):
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)


def scrape_twitter(queries_list, language, start_time, end_time, country_code, data_dir, flag=None):
    for query in queries_list['twitter']:
        scraper = twitter_scraper.Twitter_scraper(query, language, country_code, data_dir)
        scraper.scrape(start_time, end_time=end_time, flag=flag)


def scrape_crowdtangle(queries_list, language, start_time, end_time, country_code, data_dir, flag=None):
    for query in queries_list['crowdTangle']:
        scraper = crowdTangle_scraper.crowdTangle_scraper(query, language, country_code, data_dir)
        scraper.scrape(start_time, end_time=end_time, flag=flag)


def scrape_reddit(queries_list, compiled_codes, language, start_time, end_time, country_code, data_dir):
    for query, compiled_code in tuple(zip(queries_list['reddit'], compiled_codes.values())):
        #print(query)
        scraper = reddit_scraper.Reddit_scraper(query=query, data_dir=data_dir, country=country_code,
                                                language=language, compiled_code=compiled_code)
        scraper.scrape(query=query, start_time=start_time, end_time=end_time)


def main():	
    my_parser = argparse.ArgumentParser(usage='%(prog)s [options]')
    my_parser.add_argument('-o', '--output', type=str, help='Output file name')
    my_parser.add_argument('-d', '--directory', type=str, default='output',
                           help='Output directory name, default :output')
    my_parser.add_argument('-s', '--search', type=str.lower, required=True,
                           help='Boolean (b/boolean) or keyword (k/keyword) search')
    my_parser.add_argument('-i', '--input', type=str, default='input', help='Input directory, default: input')
    my_parser.add_argument('-q', '--query', type=str, action='append',
                           help='The query file(s), required for keyword search.')
    my_parser.add_argument('-p', '--platform', type=str.lower, default='tcr', required=True,
                           help='Select platform(s): Twitter (t), CrowdTangle (c) and Reddit (r)')
    my_parser.add_argument('-n', '--name', type=str, default='test',
                           help='Name of the search, output will be [name]_[platform].csv. Default: test')
    my_parser.add_argument('-t', '--time', type=str, default=None,
                           help='Enter d (day), w (week), or m (month). This signifies up to the time the' +
                                'search will be carried out (from today). ' +
                                'If nothing is entered, the time provided in the query file will be used.' +
                                'This overwrites the time given in the query file. Example usage: -t w. This means that ' +
                                'the query will searched from 1 week ago until now. Similarly for d (day) and m (month)')

    args = my_parser.parse_args()

    # arg check
    if args.search != 'b' and args.search != 'boolean' and args.search != 'k' and args.search != 'keyword':
        print("-s/--search argument not correct: choose between: b, boolean, k, keyword\n Exiting.")
        sys.exit()
    if 't' not in args.platform and 'c' not in args.platform and 'r' not in args.platform:
        print("Could not find any platform to scrape. Example usage: -p c, -p rc, -pcr\n Exiting.")
        sys.exit()
    if args.query is None:
        print("No query files found. Example usage: -q test_keyword.txt for single, -q test_keyword.txt -q test2.txt for multiple."
              "\n Exiting")
        sys.exit()


    claim_dir = args.input + "/"
    data_dir = args.directory + "/"
    search_name = args.name

    # creating output folder plus a folder named after the "name" of the search
    try:
        if not os.path.isdir(data_dir + search_name):
            os.makedirs(data_dir + search_name + "/")
    finally:
        access = 0o755
        if not os.path.isdir(data_dir):
            os.mkdir(data_dir, access)
        if not os.path.isdir(data_dir + search_name):
            os.mkdir(data_dir + search_name + "/")

    if os.path.isdir(data_dir + search_name):
        print("You've already done another query with the same name")
        # sleep(10)
    data_dir = data_dir + search_name + '/'

    filename_list = args.query
    for filename in filename_list:
        f = open(claim_dir + filename, 'r')
        queries_list, compiled_codes, start_time, end_time, language, country_code = None, None, None, None, None, None
        # queries is a list of lists, with the top level entries being the list of queries per platform
        type_of_search = args.search
        if type_of_search == 'k' or type_of_search == 'keyword':
            queries_list, compiled_codes, start_time, end_time, language, country_code = queryParser.keyword_parser(
                f, claim_dir, args.time)
        elif type_of_search == 'b' or type_of_search == 'boolean':
            queries_list, compiled_codes, start_time, end_time, language, country_code = \
                queryParser.boolean_keyword_parser(f, claim_dir, args.time)
        if 't' in args.platform:
            scrape_twitter(queries_list, language, start_time, end_time, country_code, data_dir, flag="lang")
            scrape_twitter(queries_list, language, start_time, end_time, country_code, data_dir, flag="country")
        if 'c' in args.platform:
            scrape_crowdtangle(queries_list, language, start_time, end_time, country_code, data_dir, flag="lang")
            scrape_crowdtangle(queries_list, language, start_time, end_time, country_code, data_dir, flag="country")
        if 'r' in args.platform:
            scrape_reddit(queries_list, compiled_codes, language, start_time, end_time, country_code, data_dir)


if __name__ == '__main__':
    main()

'''
Given all URLs collected (Davide, and ones sourced from Twitter and Crowdtangle, search the domain on CrowdTangle) and score, title, date, etc. over the same time span.
heatmap x - dates, y-keywords - colour no. tweets, engagement score, etc.

Network with edges as the time that the URL was posted
'''
