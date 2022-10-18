#This file is part of Social Media Data Gatherer.
#
#Social Media Data Gatherer is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#Social Media Data Gatherer is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#You should have received a copy of the GNU General Public License along with Foobar. If not, see <https://www.gnu.org/licenses/>. 

import re
import datetime
import time

queries = {'twitter': '', 'reddit': '', 'crowdTangle': ''}
AND_operators = {'twitter': '', 'reddit': 'AND', 'crowdTangle': 'AND'}
OR_operators = {'twitter': 'OR', 'reddit': 'OR', 'crowdTangle': 'OR'}
NEG_operators = {'twitter': '-', 'reddit': 'NOT', 'crowdTangle': 'NOT'}
parentheses = {'twitter': ['(', ')'], 'reddit': ['(', ')'], 'crowdTangle': ['(', ')']}
times = {'START_TIME': None, 'END_TIME': None}


# def keyword_parser(query_file, claim_dir='claim/'):

# This function is for simple queries, i.e, one word per line.
# An example:
# LANGUAGE_CODE::en
# COUNTRY_CODE::au
# START_TIME::2020-11-01T00:00:00.00Z
# END_TIME::2022-03-07T11:00:00.00Z

# dog, dogs, hound
# cat, cats
def keyword_parser(dict_file, claim_dir='claim/', arg_time = None):
    try:
        lines = dict_file.readlines()
    except FileNotFoundError:
        print(dict_file + " not found")
        quit()

    # get lines of file with claims
    lines = [line.strip() for line in lines if line[0] != '#' and line.strip() != '']

    for line in lines[2:4]:
        split_line = line.strip().split('::')
        times[split_line[0]] = None if split_line[1] == '' else split_line[1]

    language_code = lines[0].strip().split('::')[1]
    country_code = lines[1].strip().split('::')[1]
    lines = lines[4:]
    all_queries = {}

    query_codes = {}
    for platform in queries.keys():
        OR_operator = OR_operators[platform]
        platform_queries = []
        for line in lines:
            match platform:
                case 'twitter':
                    res = (' ' + OR_operator + ' ').join(["\"" + x.strip() + "\"" for x in line.split(',')])
                case 'reddit':
                    res = (' ' + OR_operator + ' ').join([x.strip() for x in line.split(',')])
                    query_codes[res] = (code_from_query([x for x in line.split(',')], {x: [x] for x in line.split(',')}))
                    # for word in line.split(','):
                case 'crowdTangle':
                    res = (' ' + OR_operator + ' ').join(["\"" + x.strip() + "\"" for x in line.split(',')])
            platform_queries.append(res)
        all_queries[platform] = platform_queries
    print(query_codes)

    # convert end time and start time
    try:
        
        # We need to offset the time by our timezone as Twitter uses GMT-0, then another 10 seconds to satisfy
        # Twitter's requirements
        now = datetime.datetime.now()
        offset = time.timezone - 10        
        match time.localtime().tm_isdst:
            case 1:
                offset -= 3600
            case 0:
                pass
            case -1:
                print('Manually change offset for the datetime, there is a problem detecting daylight savings time')
                quit()
        
        if arg_time:
            match arg_time:
                case 'd':
                    start_timestamp = (now - datetime.timedelta(days=1)).timestamp() 
                case 'w':
                    start_timestamp = (now - datetime.timedelta(weeks=1)).timestamp()
                    pass
                case 'm':
                    start_timestamp = (now - datetime.timedelta(months=1)).timestamp()
                case _:
                    print("-t/--time argument not correct: choose between: d (1 day ago), w (1 week ago) and " +
                    "m (1 month ago) \n Exiting.")
                    quit()
            start_timestamp += offset
            end_timestamp = now.timestamp() + offset
        else:
            # Adjust the timestamps passed in by our offset. 
            start_timestamp = datetime.datetime.strptime(times['START_TIME'], "%Y-%m-%dT%H:%M:%S.%UZ").timestamp() + offset
            end_timestamp = datetime.datetime.now().timestamp() + offset if times['END_TIME'] is None else \
                datetime.datetime.strptime(times['END_TIME'], "%Y-%m-%dT%H:%M:%S.%UZ").timestamp() + offset
    except:
        print("Either the beginning date or end date are not in the correct format")
        quit()

    if end_timestamp <= start_timestamp:
        print("The start date must be earlier than the end date")
        quit()
    return all_queries, query_codes, start_timestamp, end_timestamp, language_code, country_code



'''
This is a function to handle boolean keywork searches. Each file you point the parser torwards should
contain synonyms of the same word, e.g dog, hound, canine, etc. The file should contain one word per line
with no other punctuation. The parser then ORs these words together. So in our previous example, the, all
occurrences of say, W1, that are pointed to our file get replaced with "dog OR hound OR canine" in the search
in the query. 
Sample input:
NEG (W1 OR W2) AND (W3 OR W4)
START_TIME::%Y-%m-%dT%H:%M:%S.%UZ
END_TIME::%Y-%m-%dT%H:%M:%S.%UZ <-- You may leave this blank
W1::filename1.txt
W2::filename2.txt
W3::filename3.txt
W4::filename4.txt
'''

def boolean_keyword_parser(query_file, claim_dir, arg_time = None):
    dict_words = {}

    try:
        lines = query_file.readlines()
    except FileNotFoundError:
        print(query_file + " not found")
        quit()
    lines = [line.strip() for line in lines if line[0] != '#' and line.strip() != '']
    language_code = lines[1].strip().split('::')[1]
    country_code = lines[2].strip().split('::')[1]

    # set it up the dictionary that contains the mapping of the word key to the choice of words
    for line in lines[5:]:
        split_line = line.strip().split('::')
        try:
            word_key = split_line[0]
            print(claim_dir + split_line[1])
            with open(claim_dir + split_line[1], 'r') as f:
                dict_lines = f.readlines()
                dict_words[word_key] = [dict_line.strip() for dict_line in dict_lines]

        except FileNotFoundError:
            print(split_line[1] + " was not found")
            quit()
        except Exception as e:
            print("There was some error:\n", e)
            quit()

    words = {}
    res = re.findall(r'\w+|[^\s\w]+', lines[0])
    for site in queries.keys():
        AND_operator = AND_operators[site]
        OR_operator = OR_operators[site]
        NEG_operator = NEG_operators[site]
        parenthesis = parentheses[site]
        for word in res:
            match word:
                case '(':
                    queries[site] += parenthesis[0]
                case ')':
                    queries[site] += parenthesis[1]
                case 'AND':
                    # A space implies an AND in Twitter by default, hence we don't need 3 spaces
                    # This reduces the character count of the query
                    if site == "twitter":
                        queries[site] += ' '
                    else:
                        queries[site] += ' ' + AND_operator + ' '
                case 'NEG':
                    # Twitter only negates in the following manner -Q, hence, no spaces are required
                    if site == 'twitter':
                        queries[site] += NEG_operator
                    else:
                        queries[site] += NEG_operator + ' '
                case 'OR':
                    queries[site] += ' ' + OR_operator + ' '
                # Default Case: Word names
                case _:
                    queries[site] += word
        for line in lines[3:5]:
            split_line = line.strip().split('::')
            times[split_line[0]] = None if split_line[1] == '' else split_line[1]

        try:
            # We need to offset the time by our timezone as Twitter uses GMT-0, then another 10 seconds to satisfy
            # Twitter's requirements
            now = datetime.datetime.now()
            offset = time.timezone - 10        
            match time.localtime().tm_isdst:
                case 1:
                    offset -= 3600
                case 0:
                    pass
                case -1:
                    while (True):
                        print('There is a problem detecting daylight savings')
                        manual_ds = input('Please enter 1 if it\'s currently daylight savings time or 0 otherwise: ')
                        try:
                            int(manual_ds)
                        except:
                            print('Please either enter 0 or 1')
                            continue
                        if int(manual_ds) == 1:
                            offset -= 3600
                        elif int(manual_ds) != 0:
                            print('Please enter either 0 or 1')

            # Adjust the timestamps passed in by our offset. 
            if arg_time:
                match arg_time:
                    case 'd':
                        start_timestamp = (now - datetime.timedelta(days=1)).timestamp() 
                    case 'w':
                        start_timestamp = (now - datetime.timedelta(weeks=1)).timestamp()
                        pass
                    case 'm':
                        start_timestamp = (now - datetime.timedelta(months=1)).timestamp()
                    case _:
                        print("-t/--time argument not correct: choose between: d (1 day ago), w (1 week ago) and " +
                        "m (1 month ago) \n Exiting.")
                        quit()
                start_timestamp += offset
                end_timestamp = now.timestamp() + offset
            else:
                start_timestamp = datetime.datetime.strptime(times['START_TIME'], "%Y-%m-%dT%H:%M:%S.%UZ").timestamp() + offset
                end_timestamp = now.timestamp() + offset if times['END_TIME'] is None else \
                datetime.datetime.strptime(times['END_TIME'], "%Y-%m-%dT%H:%M:%S.%UZ").timestamp() + offset
        except Exception as e:
            print("Either the beginning date or end date are not in the correct format. Error:\n", e)
            quit()

        if end_timestamp <= start_timestamp:
            print("The start date must be earlier than the end date")
            quit()
        # Here the query is populated by replacing each occurrence of the variable representing the word
        # with a series of OR'd words obtained from the dictionary pointed to by that variable's corresponding
        # filename
        for word in dict_words:
            words = (' ' + OR_operator + ' ').join(dict_words[word])
            queries[site] = queries[site].replace(word, words)

        if len(queries[site]) > 1024:
            print("Query too long")
            quit()
        queries[site] = [queries[site]]
            
        

    code = [code_from_query(res, dict_words)]
    print(queries)
    return queries, code, start_timestamp, end_timestamp, language_code, country_code




#If you touch this code it may completely fall apart. If you have to debug this, 
def code_from_query(query_elem_list, dict_words, text_var='text_var'):
    # words: a dictionary with each key corresponding to the word name in the input and it's
    # corresponding value a string of OR'd words in a string
    query = "True if "
    for elem in query_elem_list:
        match elem:
            case '(':
                query += "("
            case ')':
                query += ")"
            case 'AND':
                query += " and "
            case 'NEG':
                query += "not "
            case 'OR':
                query += " or "
            case _:
                #
                ord_words = '|'.join(dict_words[elem])
                query += r"re.findall(r'\b" + ord_words + r"\b'," + text_var + ", re.IGNORECASE)"
    query += " else False"
    # TODO: Add security measures to ensure that this can't be used maliciously
    #print(query)
    return compile(query, '', 'eval')


def eval_claim(compiled_code, text):
    return eval(compiled_code, {'re': re}, {'text_var': text})
