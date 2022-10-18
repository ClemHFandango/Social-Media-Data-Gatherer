This script was written by Benedict Treeby and Alexandros Tsakiris and licensed under the GPL.


# Social Media Data Gatherer

This scraper scrapes posts given one or more keywords or queries (more than 1 keywords) utilising three APIs: Tweepy (Twitter), PyCrowdTangle (Facebook, Instagram), PRAW (Reddit). It performs boolean or keyword search, creating either boolean search queries out of keywords or searching for the keywords themselves. In the input/ folder there are example files for both cases. 

## Installation

Install the requirements through pip

`pip install -r requirements.txt`


## Authorization
The code expects an auth.py file in each of the scrapers sub folders. These files are provided but need to be populated with the corresponding credentials.


## Input Files
The input files contain special lines such as the example for a KEYWORD search.

---
```
LANGUAGE_CODE::no
COUNTRY_CODE::no
START_TIME::2022-04-03T00:00:00.00Z
END_TIME::

sanksjoner
```

---
Where `LANGUAGE_CODE` and `COUNTRY_CODE` correspond to the a search made on Twitter and CrowdTangle specific for those country codes and Reddit uses langdetect to make sure the results correspond to `LANGUAGE_CODE`. `START_TIME` is the date of the oldest post to be found, END_TIME is the date of the newest post to be found, if empty it is the date of the script's execution.

The same principle holds for the BOOLEAN search. It is a function to handle boolean keywork searches. Each file you point the parser torwards should contain synonyms of the same word, e.g dog, hound, canine, etc. The file should contain one word per line with no other punctuation. The parser then ORs these words together. So in our previous example, the, all occurrences of say, `W1`, that are pointed to our file get replaced with `dog OR hound OR canine` in the search in the query.

Sample input text file:

---
```
NEG (W1 OR W2) AND (W3 OR W4)
START_TIME::%Y-%m-%dT%H:%M:%S.%UZ
END_TIME::%Y-%m-%dT%H:%M:%S.%UZ #<-- You may leave this blank
W1::filename1.txt
W2::filename2.txt
W3::filename3.txt
W4::filename4.txt
```
---

## Usage

Performs a boolean search on Twitter and CrowdTangle, using the test_boolean.txt file in input/ and
creates a folder called output/ where a folder named twitter_ct_search/ includes results.csv of the search
Example:
`python run.py -o results -s b -i input -q test_boolean.txt -p tc -n twitter_ct_search`


Performs a keyword search on Reddit, using text_keyword.txt in input/ and created a folder named out/ instead where the folder test/ includes results.csv
Example:
`python run.py -o results -d out -s k -i input -q test_keyword.txt -p r -n test`

