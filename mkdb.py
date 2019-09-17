#!/usr/bin/python
#from __future__ import with_statement

"""
Florian Schroff (schroff@robots.ox.ac.uk)
Engineering Departement 
University of Oxford, UK
Copyright (c) 2007
All Rights Reserved.

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

Skript to download images from flickr
and homepages including the images on them from google

(uses code from http://www-128.ibm.com/developerworks/webservices/library/ws-pyth14/ (send google queries)
webgobbler http://sebsauvage.net/python/webgobbler/
flickr.py)
"""

__author__ = "Florian Schroff <schroff@robots.ox.ac.uk>"
__version__ = "Version 0.1"
__date__ = "2007"
__copyright__ = "Copyright 2007 Florian Schroff"

import optparse
import sys
import getpass
import os
import re
import errno
#import SOAPpy #Only needed if soap is used, for flickr it is currently necessary
import Image
import urllib
import urllib2
import socket
import urlparse
import string
import StringIO
import copy
import logging
import math
import sha
from FLOSlog import myLog
import mkdb_mod
import flickr
import traceback
import BeautifulSoup
import threading
import Queue
from downloader import downloader, internetFile
from GoogleTranslate import GoogleTranslater
import time
import gc
import cookielib



# We give the USER_AGENT a simple browser type, because some sites will disable
# irritating AJAX things for us if we do.
USER_AGENT = 'Lynx/2.8.5rel.1 libwww-FM/2.14 SSL-MM/1.4.1 OpenSSL/0.9.8a'

# stop words that will be removed before the context of an image is extracted
HTML_STOP_WORDS=['nbsp','html']

class Queryservice(myLog):
    """Provide functionality to send search queries to google and flickr.
    
    The retrieved images (flickr) and images from the retrieved websites (google)
    are being stored on hard disk.

    """
    def __init__(self,query,options,callingdetails):
        self.options=options
        self.query=query
        self.callingdetails=callingdetails
        self.servicename='unknown'

    def _fetchURL(self,url):
        """download the webpage for the given url"""
        try:
            request_headers = { 'User-Agent': USER_AGENT }
            request = urllib2.Request(url, None, request_headers)  # Build the HTTP request
            htmlpage = urllib2.urlopen(request).read(500000)
        except Exception, exc:
            self._logDebug('Could not fetch: %s (%s)'%(str(url),str(exc)))
            return None
        else:
            return htmlpage

    class pageParser(myLog,threading.Thread):
        """Parses one downloaded webpage (from downloader) adds schedules all urls in this page for download, and then processes ALL already downloaded images.

        """
        class imgpageref(object):
            def __init__(self):
                self.webpages = {}
                self.imgpageref = {}
            def add(self,imgtagID,pagename,page):
                self.webpages[pagename]=page
                self.imgpageref[imgtagID]=pagename
            def poppage(self,imgtagID):
                try:
                    pagename = self.imgpageref[imgtagID]
                except KeyError:
                    return None,(None,None,None)
                pagetuple = self.webpages[pagename]
                del self.imgpageref[imgtagID]
                if not (pagename in self.imgpageref.values()):
                    del self.webpages[pagename]
                return pagename,pagetuple
            def nrpages(self):
                return len(self.webpages)
            def nrimgtags(self):
                return len(self.imgpageref)


        def __init__(self,dd,addInfo,options):
            self.addInfo=addInfo
            self.options=options
            threading.Thread.__init__(self)
            self.setName('pageParser')
            self.setDaemon(True)
            self.rp = 'A3X4S34h5jDdfgFj4r3Et4v3d2heYHNMDSRH3325790qWACXZXSDERTgfb57jmkfh25E4c2' # "unique" string used to replace all imagetags in one page
            self.rppat=re.compile(self.rp+'\d+')
            self.queryinfo = {}
            self.imgpage=self.imgpageref()
            self.dd = dd #this is the downloader which provides the downloaded webpages to parse
            self.__shutdown=False
            self.parse_throughput=0

        def getThroughput(self):
            tp = self.parse_throughput
            self.parse_throughput=0
            return tp

        def shutdown(self):
            self.__shutdown=True

        def run(self): #with some changes this could be threaded
            while not self.__shutdown:
                time.sleep(0.5)
                if self.imgpage.nrpages()<self.options.max_parsedpages:
                    self.parseOnePage()
                self.processAllImages()

        def parseOnePage(self):
            #get some downloaded webpages (URLs) and parse them
            webpage,wid,recurselevel=self.dd.getWPage()
            if webpage == None: #currently now webpages there
                #self._logDebug('No webpages to parse')
                return False
            urldir = '/'.join(string.split(webpage.url, '/')[:-1])+'/'
            self._logDebug('Parse: %s'%str(webpage.url))
                #    #Recursive download of images from html pages
                #    if image.isHTML and (recurselevel>0):
                #        recurselist.append(imageurl)
                #    continue
            try:
                #soup = BeautifulSoup.BeautifulSoup(cachedpage)
                soup = BeautifulSoup.BeautifulStoneSoup(webpage.data)
            except: #TODO: maybe using only simple regular expressions instead of BeautifulSoup is better, however BeautifulStoneSoup might be fine
                self._logDebug('    Could not parse page: %s'%str(webpage.url))
                self.dd.webpage_done()
                return False 
            self.parse_throughput+=1
            websitetitle = str(soup('title'))
            imagetags=soup('img') #extract all image-tags
            hreftags=soup('a') #extract link-tags <a href="...(jpg|png...)">, could be images too, or for recursive download
            self._logDebug("    Found %d imagetags and %d hreftags" %(len(imagetags),len(hreftags)))
            #only save if really images were downloaded
            pagename=webpage.saveToDisk(self.options.output,'.'+self.options.fileext)  # Save the image to disk.

            #replace tags (so that context can be extracted later) and "flatten" the page
            tagIDs=[]
            for tag in imagetags+hreftags:
                tagid=self.dd.getID()
                tagIDs.append(tagid)
                try:
                    tag.insert(' '+self.rp+'%d '%tagid) #Replace this tag with a unique string, to retrieve the context
                except AttributeError:
                    self._logInfo('Couldnt insert tag,properly!!!!')
                    raise #this shouldn't happen

            #remove all tags (TODO: might wanna use BeautifulSoup here as well)
            text = mkdb_mod.stripTags(str(soup))
            text = re.sub(' +',' ',re.sub('[^a-zA-Z0-9 ]',' ',text))
            pagetext = text.split(' ')
            #remove some stopwords
            for sw in HTML_STOP_WORDS:
                try:
                    while True:
                        pagetext.remove(sw)
                except ValueError:
                    pass

            webpagetext=(copy.copy(pagetext),websitetitle,webpage.url)
            tagnr=-1
            for tag in imagetags+hreftags:
                tagnr+=1
                #prepare image download
                if tag.name=='img': #imagetag
                    try:
                        imageurl=tag['src']
                    except KeyError:
                        self._logDebug("    Something wrong with this tag: %s"%tag)
                        continue
                if tag.name=='a': #link tag
                    try:
                        imageurl=tag['href']
                    except KeyError:
                        self._logDebug("    Something wrong with this tag: %s"%tag)
                        continue
                imageurl = urlparse.urljoin(urldir,imageurl)
                imageurl = re.sub(' ','%20',imageurl) #escape spaces in the image url
                if not self.dd.put_url(imageurl,tagIDs[tagnr],imagediscardsize=self.options.discardsize,recurselevel=(recurselevel-1)):
                    #url already scheduled for download or downloaded; FIXME could add the context and metadata of this occurence to the already downloaded image-file
                    # too much spam self._logDebug("    Url already scheduled for download or downloaded: %s"%imageurl)
                    continue
                self.imgpage.add(tagIDs[tagnr],pagename,webpagetext)
                #self.imgpageref[tagIDs[tagnr]]=(pagename,webpagetext)
                #image=internetFile(imageurl,self.discardsize)
                self.queryinfo[tagIDs[tagnr]]={}
                self.queryinfo[tagIDs[tagnr]].update({'linktype':tag.name})
                if tag.name=='img':
                    try:
                        self.queryinfo[tagIDs[tagnr]].update({'image_title':mkdb_mod.strip2Alphanum(tag['title'])})
                    except KeyError:
                        pass
                    try:
                        self.queryinfo[tagIDs[tagnr]].update({'image_alt':mkdb_mod.strip2Alphanum(tag['alt'])})
                    except KeyError:
                        pass
            self.dd.webpage_done()
            return True
        
        def processAllImages(self):
            #get ALL downloaded images and match them with their context
            imagenr=0
            #self._logDebug('processing %d images'%self.dd.downloaded_images.qsize())
            for image,tagid,recurselevel in self.dd.getImageIterator():
                pagename,webpagetext=self.imgpage.poppage(tagid)
                try:
                    if pagename == None:
                        continue
                    #try:
                    #    pagename,webpagetext=self.imgpageref[tagid]
                    #except KeyError:
                    #    self.dd.image_done()
                    #    continue #happens for the seed-webpages
                    if image==None: #just to recognize that the image was handled
                        continue
                    #self._logDebug("IMAGE: id: %d; reclvl: %d"%(tagid,recurselevel))
                    image.info.addQueryInfo(self.queryinfo[tagid])
                    image.info.addQueryInfo(('recurselevel',str(self.options.recurselevel-recurselevel)))
                    #extract the contents for each image
                    index=0
                    origpagetext,websitetitle,url = webpagetext

                    #self._logDebug("\n%s\n%s\n\n%s\n%s\n\n"%(self.imgpageref[tagid],origpagetext,websitetitle,url))
                    pagetext=copy.copy(origpagetext)
                    try:
                        index=pagetext.index(self.rp+'%d'%tagid)
                    except ValueError:
                        #self._logDebug('This is the whole page (%s): %s\n'%(pagename,pagetext))
                        #self._logDebug('tags replaced: %s\n'%(page_withrp))
                        #self._logDebug('Looking for %s %d'%(rp,tagnr))
                        self._logDebug('Some parsing errors (no tag for this image)!!!!')
                        continue
                    pagetext[index]='thisIsWhereTheImageWas' #leave original image position marked
                    for ii in xrange(len(pagetext)-1,-1,-1):
                       if self.rppat.match(pagetext[ii]):
                           pagetext.pop(ii)
                    try:
                        index=pagetext.index('thisIsWhereTheImageWas')
                    except ValueError:
                        self._logInfo('Oh there is something seriously wrong here (thisIsWhereTheImageWas tag is missing)!!!!')
                        raise "missing 'thisIsWhereTheImageWas'!!!"
                    context = pagetext[max(0,index-self.options.nrcontext):(index+self.options.nrcontext+1)]
                    #imagenr+=1
                    #tagnr+=1
                    #Write the Imageinfo and save Images
                    context=' '.join(context)
                    surl = str(url)
                    self._logDebug('url: %s'%surl)
                    #self._logDebug('url (unquoted): %s'%urllib.unquote(surl))
                    image.info.addQueryInfo(('website_url',surl))
                    if len(websitetitle) > 0:
                        websitetitle =mkdb_mod.stripTags(str(websitetitle[0]))
                        image.info.addQueryInfo(('website_title',mkdb_mod.strip2Alphanum(websitetitle)))
                    image.info.addQueryInfo(('website_stored',pagename))
                    image.info.addQueryInfo(('context',context))
                    image.info.addQueryInfo(self.addInfo)
                    if not self.options.noresize:
                        image.resizeArea()
                    image.saveToDisk(self.options.output,'.'+self.options.fileext)  # Save the image to disk.
                    imagenr+=1
                finally:
                    self.dd.image_done()
                    ##print pagename,tagid,self.imgpageref,self.webpages.keys(),'\n\n\n'
                    #del self.imgpageref[tagid] #delete this entry
                    ###check if webpage can be deleted
                    ##if not pagename in self.imgpageref.values():
                    ##    del self.webpages[pagename]
                    ###else:
                    ###    c=0
                    ###    for p in self.imgpageref.values():
                    ###        if p==pagename:
                    ###            c+=1
                    ###    #print pagename,c
            #self._logDebug("Processed %d images."%imagenr)

    def query_flickr(self): 
        tags = self.query.split(' ')
        #tags = '76228432@N00'
        #photos = flickr.photos_search(user_id=tags, per_page=self.number, sort='relevance')
        photos = flickr.photos_search(tags=tags, per_page=self.options.nritems, tag_mode='all', sort='relevance')
        self._logInfo("Found %d" %len(photos))
    
        nrimages=0
        for photo in photos:
            image=None
            nrprefix = "%05d"%nrimages
            try:
                imageurl=photo.getURL(size='Original', urlType='source')
                image=internetFile(imageurl,nrprefix=nrprefix)
            except flickr.FlickrError:
                #print "Could not get size %s of %d" %('Original',photo.id)
                pass #probably size does not exist try next
            if image==None or image.discardReason=="too big":
                try:
                    imageurl=photo.getURL(size='Large', urlType='source')
                    image=internetFile(imageurl,nrprefix=nrprefix)
                except flickr.FlickrError:
                    #print "Could not get size %s of %d" %('Large',photo.id)
                    pass #probably size does not exist try next
            if image==None or image.discardReason=="too big":
                try:
                    imageurl=photo.getURL(size='Medium', urlType='source')
                    image=internetFile(imageurl,nrprefix=nrprefix)
                except flickr.FlickrError:
                    #print "Could not get size %s of %d" %('Medium',photo.id)
                    pass #probably size does not exist try next
    
            if image==None or image.discardReason=="too big":
                self._logDebug("Cannot find proper size of %s"%photo.id)
                continue
            if image.isNotAnImage:
                self._logDebug("Image discarded because: %s"%image.discardReason)
                continue
            
            image.info.addQueryInfo(('flickr_id',photo.id))
            image.info.addQueryInfo(('query',self.query))
            try:
                context=' '.join([tag.text for tag in photo.tags])
            except AttributeError:
                context = ''
                pass
            image.info.addQueryInfo(('context',context))
            if not self.options.noresize:
                image.resizeArea()
            image.info.addQueryInfo(('callingdetails',self.callingdetails))
            image.info.addQueryInfo(('service','flickr'))
            image.saveToDisk(self.options.output)  # Save the image to disk.
            nrimages=nrimages+1
    
        self._logInfo("%d images were downloaded!" %nrimages)
    
    class QuerySearchEngine(myLog):

        class Results: 
            class ResultElement: pass
            def __init__(self):
                self.resultElements=[]
    
        def __init__(self,language,engine,options):
            #Start google search initialization
            self.options = options
            self.engine = engine
            if engine=="Google":
                self.request_url = "http://www.google.com/search?q=%s&num=%d&start=%d&ie=utf-8&oe=utf-8&client=firefox-a&rls=org.mozilla:en-US:official"
                self.num_perPage=20 #TODO: why are only twenty returned and not 21 as in the browser???
                self.request_url_IMG="http://images.google.com/images?q=%s&svnum=10&hl=en&lr=&safe=off&client=firefox-a&rls=en&start=%d&sa=N&ndsp=21&lr=lang_%s"
                self.language = language
                self.linkfinder = self.__GoogleWebLinks
                self.imgfindregexp=re.compile('imgurl=(.*?)&imgrefurl=(.*?)&(amp;)?(h=.*?)?start=(\d+)')
                self.serviceImg='gImgSearch'
                self.rankpos=-1
                self.rootpos=1
                self.imgpos=0
            elif engine=="Yahoo":
                self.request_url_IMG = "http://images.search.yahoo.com/search/images?p=%s&ei=UTF-8&b=%d&vl=lang_%s" #language does not work
                self.language = language
                self.num_perPage=20 
                self.linkfinder = None
                self.imgfindregexp=re.compile('imgurl=(.*?)%26rurl=(.*?)%26.*?no=(\d+)')
                self.serviceImg='yahooImgSearch'
                self.rankpos=2
                self.rootpos=1
                self.imgpos=0
            elif engine=="Live":
                self.serviceImg='liveImgSearch'
                self.request_url_IMG = "http://search.live.com/images/results.aspx?q=%s&first=%d&mkt=%s" #language does not work 
                self.language = language+'-'+language
                self.num_perPage=20
                self.linkfinder = None
                self.imgfindregexp=re.compile('su=(.*?)&iu=(.*?)&')
                self.rankpos=-1000
                self.rootpos=0
                self.imgpos=1
            else:
                raise "Unknown search engine"

        def __GoogleWebLinks(self,soup):
            return soup('div', {'class' : 'g'})

        def _initAPI(self):
            self._url = 'http://api.google.com/search/beta2'
            self._namespace = 'urn:GoogleSearch'
            self.__license_key = 'fM+j22NQFHLmVU6ndcdVNuzd+ZVMiYhf' 

            # need to marshall into SOAP types
            SOAP_FALSE = SOAPpy.Types.booleanType(0)
            SOAP_TRUE = SOAPpy.Types.booleanType(1)

            # create SOAP proxy object
            self.google = SOAPpy.SOAPProxy(self._url, self._namespace)
            self._filter = SOAP_FALSE
            self._safeSearch = SOAP_FALSE

            # Google search options
            self._start = 0
            self._maxResults = 10
            self._restrict = ''
            self._lang_restrict = ''
            
        def searchAPI(self,query):
            """Returns list of webpages returned from Google-API to the query"""
            # call search method over SOAP proxy
            results = self.google.doGoogleSearch( self.__license_key, query, 
                                             self._start, self._maxResults, 
                                             self._filter, self._restrict,
                                             self._safeSearch, self._lang_restrict, '', '' )
            return results
        
        def _fetchGoogleCache(self,url):
            """fetch the cachedwebpage to the given url"""
            # call search method over SOAP proxy
            results = self.google.doGetCachedPage( self.__license_key, url )
            return results #}}}

        def searchWEB(self,query,number):#{{{
            """Returns list of webpages returned from Google (or other search engine), to the given query"""
            results=self.Results()
            num_perPage=100
            for start_result in range(0,number,num_perPage):
                self._logInfo('Return results %s to %s (%s web search)'%(start_result+1,start_result+num_perPage,self.engine))
                try:
                    request_url = self.request_url%(urllib.quote_plus(query),num_perPage,start_result);
                    request_headers = { 'User-Agent': USER_AGENT }
                    request = urllib2.Request(request_url, None, request_headers)  # Build the HTTP request
                    htmlpage = urllib2.urlopen(request).read(1000000)  # Send the request to Google.
                except Exception, exc:
                    self._logCritical("Cannot query search engine") 
                    return results
                
                #Extract returned google-results from google search site
                soup = BeautifulSoup.BeautifulSoup(htmlpage)
                #print soup.prettify()
                links=self.linkfinder(soup)
                self._logInfo('    found #%d links'%len(links))
                for link in links:
                    linktitle=link.a.renderContents()
                    linkurl=link.a['href']
                    resultelement=self.Results.ResultElement()
                    setattr(resultelement,'title',linktitle)
                    setattr(resultelement,'URL',linkurl)
                    results.resultElements.append(resultelement)
                if len(links)<num_perPage:
                    self._logInfo("stop here, %s doesn't return more results"%self.engine)
                    break
            return results#}}}

        def searchIMAGES(self,query,number):#{{{
            """Returns a list of websites retrieved from google image search by taking the root-site of the returned images"""
            results=self.Results()
            for start_result in range(0,number,self.num_perPage):
                self._logInfo('Return results %s to %s (%s Image search)'%(start_result+1,start_result+self.num_perPage,self.engine))
                request_url= self.request_url_IMG%(urllib.quote_plus(query.encode("iso-8859-1")),start_result,self.language)
                self._logInfo("Query: %s"%request_url)
                request_headers = { 'User-Agent': USER_AGENT }
                try:
                    request = urllib2.Request(request_url, None, request_headers)  # Build the HTTP request
                    htmlpage = urllib2.urlopen(request).read(1000000)  # Send the request to Google.
                except Exception, exc:
                    self._logCritical("Cannot query %s"%self.engine) 
                    return results
                
                #Extract returned google-results from google search site
                #matches=re.compile('dyn.Img\((.*?)\);').findall(htmlpage)
                #print htmlpage
                matches=self.imgfindregexp.findall(htmlpage,re.M)
                downloadedimgnr = 0
                for match in matches:
                    #rooturl=urllib.unquote_plus(re.sub('%25','%',match[self.rootpos]))
                    #imgurl=urllib.unquote_plus(re.sub('%25','%',match[self.imgpos]))
                    rooturl=re.sub('%25','%',match[self.rootpos])
                    imgurl=re.sub('%25','%',match[self.imgpos])
                    #dynImg=match.split(',')
                    #mainpage = dynImg[0]
                    #linkurl = re.sub('&h=.*$','',mainpage).strip('"')
                    resultelement=self.Results.ResultElement()
                    #setattr(resultelement,'title',dynImg[6].strip('"'))
                    setattr(resultelement,'URL',rooturl)
                    results.resultElements.append(resultelement)
                    #download the google images directly -> get an extra query section containing some google information
                    image=internetFile(imgurl,self.options.discardsize)
                    if image.isNotAnImage:
                        self._logInfo("    Image #%s (%s): discarded because: %s"%(match[-1],imgurl,image.discardReason))
                        #raise "uhhhhh, something wrong"
                        continue
                    image.info.addQueryInfo(('service',self.serviceImg))
                    image.info.addQueryInfo(('query',query))
                    if self.rankpos==-1000:
                        rank=str(downloadedimgnr+1)
                    else:
                        rank=match[self.rankpos]
                    image.info.addQueryInfo(('position',rank))
                    self._logDebug('url: %s'%rooturl)
                    image.info.addQueryInfo(('website_url',str(rooturl)))
                    image.resizeArea()
                    image.saveToDisk(self.options.output,'.'+self.options.fileext)  # Save the image to disk.
                    downloadedimgnr += 1
                    if downloadedimgnr>=number:
                        break
                self._logInfo('    found #%d images; downloaded #%d images'%(len(matches),downloadedimgnr))
                if len(matches)<self.num_perPage:
                    self._logInfo("stop here, %s doesn't return more images"%self.engine)
                    break
            return results#}}}

    def query_engine(self,language='en',engine='Google',searchtype='WEB'):
        """Download images from the webpages returned by a standard google search"""
        self.servicename=engine+searchtype
        qg=self.QuerySearchEngine(language,engine,self.options)
        #results=qg.searchAPI(self.query)
        if searchtype=='WEB':
            results = qg.searchWEB(self.query,self.options.nritems)
        if searchtype=='IMAGES':
            results = qg.searchIMAGES(self.query,self.options.nritems)

        numresults = len(results.resultElements)
        self._logInfo('%s found %d pages\n'%(engine,numresults))

        if self.options.recurselevel==-1:
            self._logInfo('Downloaded all seeds/images, NO recursion AT ALL!')
            return
 
        addInfo={'query':self.query,'callingdetails':self.callingdetails,'service':self.servicename}
        dd=downloader(nrthreads=self.options.nrthreads,maxdownloaded_wpages=self.options.max_storedpages)
        #initialize page parser

        for i in range(min(self.options.nritems,numresults)):
            #Add URL to the downloader
            url=str(results.resultElements[i].URL)
            self._logDebug('Add seed-url for download: %s'%url)
            self._logDebug('    on recurselevel: %d'%(self.options.recurselevel))
            dd.put_url(url=url,recurselevel=(self.options.recurselevel+1))

        #for t in xrange(nrthreads): NOTE: if there will be multiple parser, you need to make sure that each parser gets the images of the webpages it processed, since it can only retrieve the context for those images. OR alternatively there is a pool of all processed webpages and each parser can get the context for each image from there
        pparser=self.pageParser(dd,addInfo,self.options)
        pparser.start() #start the parser thread
        self._logInfo('Page-parser started.\n\nDownloading...')
        
        #wait until everything is done
        try:
            os.mkdir(os.path.join(self.options.output,'stats'))
        except OSError:
            pass
        fstats=open(os.path.join(self.options.output,'stats','download_proceed_stats.txt'),'w')
        print >>fstats, dd.allstats_header(), " parser-WP parser-imgtags thru-put"
        while True:
            gc.collect()
            #refs=gc.get_referrers(internetFile)
            #objs=gc.get_objects()
            #f=open('/import/morocco_databases/mkdb_download/pythonrefs.txt','w')
            #f.write(str(refs))
            #f.close()
            #f=open('/import/morocco_databases/mkdb_download/pythonobjs.txt','w')
            #f.write(str(objs))
            #f.close()
            time.sleep(10)
            statistics_string=dd.check_if_finished()
            throughput=pparser.getThroughput();
            print >>fstats, dd.getall_stats()+"%9d %9d %7d"%(pparser.imgpage.nrpages(),pparser.imgpage.nrimgtags(),throughput)
            self._logDebug("Parser stored webpages: %d; Imagetags: %d; Throughput: %d"%(pparser.imgpage.nrpages(),pparser.imgpage.nrimgtags(),throughput))
            if statistics_string[0]:
                pparser.shutdown()
                self._logInfo('Wait until page-parser finishes...')
                pparser.join()
                self._logInfo('    page-parser finished!')
                break
            if not pparser.isAlive(): 
                self._logInfo('Unexeptional termination of page-parser!')
                statistics_string=(False,None)
                break
        fstats.close()
        if statistics_string[1]==None:
            self._logInfo('Unexeptional termination of threads!')
        else:
            f=open(os.path.join(self.options.output,'stats','download_stats.txt'),'w')
            #with open(os.path.join(self.options.output,'stats','download_stats.txt'),'w') as f:
            f.write(statistics_string[1])
            f.close()


def main():

    usage = """usage: %prog [options] [service query] 
    
    service     google OR googleImages OR yahooIMAGES OR flickr
    query       querystring given in ""

    default values for options are given in []
    """
    version= "%prog "+ "%s\n%s\n%s\n%s"%(__version__,__date__,__author__,__copyright__)

    optionparser = optparse.OptionParser(usage=usage,version=version)
    optionparser.add_option("-l","--translate",default='',action="store",type='string',dest="translate",help='Translate query into different languages. (e.g. --translate "en|de,en|fr,en|es"). [%default].',metavar="LANG.-PAIRS")
    optionparser.add_option("-n","--number",default=10,action="store",type="int",dest="nritems",help="Number of images/pages to return [%default]")
    optionparser.add_option("-o","--output",default="/tmp/mkdb_mod",action="store",type="string",dest="output",help="Destination DIRectory for files (or text-file of image files, for indexing) [%default]",metavar='DIR')
    optionparser.add_option("--getImages",default='',action="store",type='string',dest="getImages",help="Download images from the given page only.",metavar='URL')
    optionparser.add_option("-r","--recursive",default=0,action="store",type="int",dest="recurselevel",help="Follow links recursively until given depth. -1 only downloads seed pages/images. [%default]",metavar='DEPTH')
    optionparser.add_option("-f","--force",default=False,action="store_true",dest="force",help="Force overwriting of destination directory OR recompute documentlist.txt[%default]")
    optionparser.add_option("--onlyService",default=5,action="store",type='int',dest="onlyService",help="Mask to select which service is being when the imagecollection is read from a directory ('googleWEB': 1; 'googleIMAGES': 2; 'gImgSearch': 4; 'ignore': -1;). [%default]",metavar='M')
    optionparser.add_option("--ext",default='png',action="store",type='string',dest="fileext",help="File extension that the images will be saved as. Empty string for original. [%default].",metavar="EXTENSION")
    optionparser.add_option("--log",default=False,action="store_true",dest="log",help="Creates a log file in the output directory.")
    optionparser.add_option("-q","--quiet",default=False,action="store_true",dest="quiet",help="Be all quiet.")
    optionparser.add_option("--maxparseWP",default=50,action="store",type='int',dest="max_parsedpages",help="Number of parsed webpages that will be stored, if exceeded no more pages will be parsed. [%default]",metavar='NR') #TODO: this influences the number of urls in urlqueue (there is no limit on urlqueue
    optionparser.add_option("--maxstoreWP",default=200,action="store",type='int',dest="max_storedpages",help="Number of parsed webpages that will be stored, if exceeded no more pages will be parsed. [%default]",metavar='NR')
    optionparser.add_option("--threads",default=10,action="store",type='int',dest="nrthreads",help="Number of threads that are used for downloading. [%default]",metavar='NR')
    optionparser.add_option("-c","--context",default=50,action="store",type="int",dest="nrcontext",help='Number of words surrounding the image (imagetag/link) that are extracted as "context" [%default]',metavar='CONTEXTLENGTH')
    optionparser.add_option("-t","--contexttypes",default='context10,context10_stem,context10_stop,context10_stemstop,context10_stemdict,context,context_stem,context_stop,context_stemstop,context_stemdict',action="store",type="string",dest="contexttypes",help='Comma seperated list of contexttypes that is used during computation of wordfreq." [%default]',metavar='CONTEXTTYPES')
    optionparser.add_option("--minsize",default=(120,120),action="store",dest="discardsize",help="Discard images smaller than minsize [%default]")
    optionparser.add_option("--noresize",default=False,action="store_true",dest="noresize",help="Do NOT resize downloaded images.")
    optionparser.add_option("--thumbsize",default='120x120',type='string',action="store",dest="thumbsize",help="Thumbnailsize to be used (e.g. 120x120). ")

    (options, args) = optionparser.parse_args()

    if (len(args) != 2) and (len(args) != 0):  
        print 'You must specify the service and a query OR nothing (e.g. for indexing only): '+sys.argv[0]+' service query. Use -h for help.'
        sys.exit(1)
    service = ''
    query = ''
    if len(args) == 2 or options.getImages!='' or (options.add!=''):
        if len(args) == 2:
            service = args[0]
            query = args[1]
        if not os.path.isfile(options.output):
            try:
                os.makedirs(options.output,0700)
            except OSError, exc:
                if exc.errno==errno.EEXIST and not options.force:
                    print "Directory %s already exists. Use -f."%options.output
                    return

    callingdetails=__version__+'; Called: '+' '.join(sys.argv)

    #set timeout instead of using the default: None
    socket.setdefaulttimeout(15)

    # Set up the default log:
    # Attach a handler to this log:
    handler_stdout = logging.StreamHandler(sys.stdout)
    handler_stdout.setLevel(logging.INFO)  # By default, only display informative messages and fatal errors.
    handler_stdout.setFormatter(logging.Formatter('%(name)s: %(message)s'))
    #handler_stdout.setFormatter(logging.Formatter('%(name)s: %(message)s'))  # Change format of messages.
    #handler.setFormatter(logging.Formatter('[%(thread)d] %(name)s: %(message)s'))
    logging.getLogger().addHandler(handler_stdout)
    logging.getLogger().setLevel(logging.DEBUG)
    log = logging.getLogger('main')    # The log for the main()

    if options.log:  # If we are running in debug mode:
        # And log everything to a file:
        handler = logging.FileHandler(options.output+'_'+'_'.join(query.split(' '))+'.log') # Log to a file.
        handler.setLevel(logging.DEBUG)  # And switch to DEBUG view (=view all messages)
        handler.setFormatter(logging.Formatter('%(name)s: %(message)s'))
        logging.getLogger().addHandler(handler) 
    
    log.info('Version: %s'%__version__)
    nothing=False
    if (query != '') and (service != ''):
        log.info('Use "%s"' %service + ' to search for: %s'%query)
        lquery=[];
        if (options.translate != ''):
            langpairs = options.translate.split(',')
            gglT=GoogleTranslater()
            for lp in langpairs:
                if lp == 'en|en':
                    lquery.append(query)
                else:
                    lquery.append(gglT.translate(query,lp))
                    log.info('Translated query (%s): %s'%(lp,lquery[-1].encode("iso-8859-1")))
        else:
            lquery.append(query)
            langpairs = [None];

        for i in xrange(0,len(lquery)):
            query = lquery[i]
            log.info('\nDownload: %s (%s)'%(query,langpairs[i]))
            if langpairs[i]==None:
                language='en'
            else:
                language = re.sub('.*\|','',langpairs[i])
            qservice=Queryservice(query,options,callingdetails)
            service= service.lower()
            if service=='google':
                qservice.query_engine(language,'Google','WEB')
            elif service=='googleimages':
                qservice.query_engine(language,'Google','IMAGES')
            elif service=='yahooimages':
                qservice.query_engine(language,'Yahoo','IMAGES')
            elif service=='liveimages':
                qservice.query_engine(language,'Live','IMAGES')
            elif service=='flickr':
                qservice.query_flickr()
            else:
                optionparser.print_help()
    else:
        nothing=True

    if nothing:
        print "You didn't tell me anything to do. *me puzzled*"

    log.info("    done!")
    print "    done!"

if __name__ == "__main__":
    try:
        main()
    except mkdb_mod.endProgram:
        pass
    except:
        logging.getLogger('main').debug(traceback.format_exc())
        raise
