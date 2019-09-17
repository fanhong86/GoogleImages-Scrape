#!/usr/bin/python
#from __future__ import with_statement

"""
Florian Schroff (schroff@robots.ox.ac.uk)
Engineering Departement 
University of Oxford, UK

Copyright (c) 2007, Florian Schroff
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
    * Neither the name of the University of Oxford nor Microsoft Ltd. nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


Please cite the following publication(s) in published work that used or was inspired by this code/work:

- Schroff, F. , Criminisi, A. and Zisserman, A.: Harvesting Image Databases from the Web, Proceedings of the 11th International Conference on Computer Vision, Rio de Janeiro, Brazil (2007)

---------------------------------------

Use Google Translator to translate text.
Can also be used as a library.
"""

__author__ = "Florian Schroff <schroff@robots.ox.ac.uk>"
__version__ = "Version 0.1"
__date__ = "2007"
__copyright__ = "Copyright 2007 Florian Schroff"

import sys
import urllib
import urllib2
import BeautifulSoup
import optparse

# We give the USER_AGENT a simple browser type, because some sites will disable
# irritating AJAX things for us if we do.
USER_AGENT = 'Lynx/2.8.5rel.1 libwww-FM/2.14 SSL-MM/1.4.1 OpenSSL/0.9.8a'

class GoogleTranslater:

    def __init__(self):
        self.google_translate_baseurl="http://translate.google.com"
        self.google_translate_url="http://translate.google.com/translate_t?text=%s&hl=en&langpair=%s"
        self.request_headers = { 'User-Agent': USER_AGENT }
        self.translations={}
         
    def translate(self,text,language_pair):
        qtext = urllib.quote(text)
        request_url = self.google_translate_url%(qtext,language_pair)

        request = urllib2.Request(request_url, None, self.request_headers)  # Build the HTTP request
        htmlpage = urllib2.urlopen(request).read(1000000)  # Send the request to Google.
        soup = BeautifulSoup.BeautifulSoup(htmlpage)
        try:
            self.translations[text]=soup('div', {'id' : 'result_box'})[0].string
        except:
            print soup
            print 'Google blocked me???'

        return self.translations[text]
    
    def getLanguagePairs(self):
        
        request = urllib2.Request(self.google_translate_baseurl, None, self.request_headers)  # Build the HTTP request
        htmlpage = urllib2.urlopen(request).read(1000000)  # Send the request to Google.
        
        soup = BeautifulSoup.BeautifulSoup(htmlpage)
        langpairs=soup('select', {'name' : 'langpair'})[0]('option')
        languagePairs={}
        for pair in langpairs:
            languagePairs[pair['value']]=pair.string
        return languagePairs

def main():

    usage = """usage: %prog [options] [language pair] [text] 
    
    language pair   en|ge, en|es, ... -l to list all
    text            text to translate

    default values for options are given in []
    """
    version= "%prog "+ "%s\n%s\n%s\n%s"%(__version__,__date__,__author__,__copyright__)

    optionparser = optparse.OptionParser(usage=usage,version=version)
    optionparser.add_option("-l","--list",default=False,action="store_true",dest="list",help="List possible language pairs [%default]")
    optionparser.add_option("-t","--translate",default='en|de',action="store",dest="translate",help="Language pairs see -l [%default]")
    (options, args) = optionparser.parse_args()

    if (len(args) != 1) and not options.list:  
        print 'You must at least specify the text to translate from English to German. Use -h for help.'
        sys.exit(1)

    if options.list:
        gglT=GoogleTranslater()
        print "Possible Translation Language Pairs:"
        print "    Shortcut        Description"
        print "------------------------------------------------------------"
        lpairs = gglT.getLanguagePairs()
        for pp in lpairs:
            print "    %-15s %s"%(pp,lpairs[pp])

    if len(args) == 1:
        print "Translate "+options.translate+":"
        print args[0]
        print "Result:"
        gglT=GoogleTranslater()
        result=gglT.translate(args[0],options.translate)
        print result.encode("iso-8859-1")


if __name__ == "__main__":
    main()
