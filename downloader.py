#!/usr/bin/python

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

Class which downloads an image from the internet
Skript to download images from flickr

(uses code from http://www-128.ibm.com/developerworks/webservices/library/ws-pyth14/ (send google queries)
webgobbler http://sebsauvage.net/python/webgobbler/)
"""

__author__ = "Florian Schroff <schroff@robots.ox.ac.uk>"
__version__ = "Version 0.1"
__date__ = "2007"
__copyright__ = "Copyright 2007 Florian Schroff"

import Image
import urllib
import urllib2
import StringIO
import sha
import math
import os
from FLOSlog import myLog
import mkdb_mod
import threading
import Queue
import time
import re

### a few classes for threading; taken from crawler.py (James Philbin <philbinj@gmail.com>) ###
class LockedID:
  """A class which contains a locked counter and so guarantees it always
returns a unique number."""
  def __init__(self):
    self.number_lock = threading.Lock()
    self.number = 0

  def get(self):
    self.number_lock.acquire()
    ret = self.number
    self.number += 1
    self.number_lock.release()
    return ret

class LockedSet:
  """Class which implements a thread-safe set."""
  def __init__(self):
    self.set = set([])
    self.set_lock = threading.Lock()

  def put(self, item):
    self.set_lock.acquire()
    self.set.add(item)
    self.set_lock.release()

  def contains(self, item):
    self.set_lock.acquire()
    ret = item in self.set
    self.set_lock.release()
    return ret

class LockedStats:
  """A class which collects various statistics about the crawl."""
  def __init__(self):
    self.__avg = {}
    self.__count = {}
    self.__max = {}
    self.stats = {}
    self.stats['html_dl'] = 0
    self.stats['img_dl'] = 0
    self.stats['html_bytes'] = 0
    self.stats['img_bytes'] = 0
    self.stats['requests'] = 0
    self.stats_lock = threading.Lock()

  def avg(self,item,value):
    self.stats_lock.acquire()
    self.__avg[item]=self.__avg.get(item,0)+value
    self.__count[item]=self.__count.get(item,0)+1
    self.stats_lock.release()
  def getAvg(self,item):
    self.stats_lock.acquire()
    average = self.__getAvg(item)
    self.stats_lock.release()
    return average
  def __getAvg(self,item):
    return float(self.__avg[item])/self.__count[item]

  def max(self,item,value):
    self.stats_lock.acquire()
    if self.__max.get(item,0)<=value:
      self.__max[item]=value
    self.stats_lock.release()
  def getMax(self,item):
    self.stats_lock.acquire()
    maximum = self.__getMax(item)
    self.stats_lock.release()
    return maximum
  def __getMax(self,item):
    return self.__max[item]

  def touch_request(self):
    self.stats_lock.acquire()
    self.stats['requests'] += 1
    self.stats_lock.release()
  
  def touch_html(self):
    self.stats_lock.acquire()
    self.stats['html_dl'] += 1
    self.stats_lock.release()
  
  def touch_img(self):
    self.stats_lock.acquire()
    self.stats['img_dl'] += 1
    self.stats_lock.release()

  def touch_html_bytes(self, bytes):
    self.stats_lock.acquire()
    self.stats['html_bytes'] += bytes
    self.stats_lock.release()

  def touch_img_bytes(self, bytes):
    self.stats_lock.acquire()
    self.stats['img_bytes'] += bytes
    self.stats_lock.release()

  def getheader(self):
    return 'url-requests pages images htmlMB imgMB       max_dl_imgs max_q_html Max_q_url max_urlhist Max_dl_wp avg_dl_imgs avg_q_html avg_q_url avg_dl_wp'
  def get_flat(self):
    self.stats_lock.acquire()
    ret =   '%6d %10d %5d %7.2f %6.2f' % \
            (self.stats['requests'],self.stats['html_dl'], self.stats['img_dl'], \
             self.stats['html_bytes'] * (1.0/2**20), self.stats['img_bytes'] * (1.0/2**20))
    for k in self.__max.keys():
        ret += ' %11d'%(self.__getMax(k))
    for k in self.__avg.keys():
        ret += ' %10.2f'%(self.__getAvg(k))
    self.stats_lock.release()
    return ret

  def get_str(self):
    self.stats_lock.acquire()
    ret =   '%d url-requests, %d pages, %d images, %.2f html MB, %.2f img MB\n' % \
            (self.stats['requests'],self.stats['html_dl'], self.stats['img_dl'], \
             self.stats['html_bytes'] * (1.0/2**20), self.stats['img_bytes'] * (1.0/2**20))
    for k in self.__max.keys():
        ret += 'Max (%s): %d; '%(k,self.__getMax(k))
    ret += '\n'
    for k in self.__avg.keys():
        ret += 'Avg (%s): %.2f; '%(k,self.__getAvg(k))
    ret += '\n'
    self.stats_lock.release()
    return ret

class LockedQueue(Queue.Queue,myLog):
    """Checks if all tasks are done, similar to join() but returns True or false instead of blocking"""
    def all_done(self):
        self.all_tasks_done.acquire()
        try:
            #self._logDebug("%d"%self.unfinished_tasks)
            if self.unfinished_tasks <= 0:
                if self.unfinished_tasks < 0:
                    raise ValueError('task_done() called too many times')
                return True
        finally:
            self.all_tasks_done.release()
        return False
    def get_notdone(self):
        self.all_tasks_done.acquire()
        nrnotdone = self.unfinished_tasks
        self.all_tasks_done.release()
        return nrnotdone


MIME_TYPES = ['jpg', 'gif', 'png', 'bmp', 'pcx', 'tiff']


class downloader(myLog):
    """Maintains a Queue where urls (images and html) can be added.

    The downloading is performed by several threads.

    """
    def __init__(self,nrthreads=10,maxqueue=0,maxurlhistory=1000000,maxdownloaded_wpages=1000,maxdownloaded_Images=100):
        self.maxurlhistory = maxurlhistory
        self.max_downloadedwpages = maxdownloaded_wpages
        self.max_downloadedImages = maxdownloaded_Images
        self.urlset = [] #queue of all urls that were scheduled for download; to avoid multiple downloads; could use set here but difficult to ensure max size
        self.urlqueue = {'url':LockedQueue(maxqueue),'html':LockedQueue()} #this is a locked queue; NOTHING SHALL BE ADDED TO THE QUEUE OUTSIDE THIS CLASS using put_url (TODO:should be wrapped in a seperate class)
        self.urlqueue_added = {'url':False,'html':False}
        self.downloaded_images = LockedQueue()
        self.downloaded_wpages = LockedQueue()
        self.threadlist = []
        self.stats= LockedStats()
        self.ids=LockedID()
        for t in xrange(nrthreads):
            new_thread=downloader_thread(self)
            new_thread.start()
            new_thread.setName('Downloader-%d'%t)
            self.threadlist.append(new_thread) 
            self._logInfo('Started thread: "Downloader-%d'%t)

    def __del__(self):
        for t in self.threadlist:
            t.shutdown()
        for t in self.threadlist:
            t.join()

    def getID(self):
        return self.ids.get()

    def put_html(self,url,id=None,recurselevel=0):
        self.put_url(url,id,None,recurselevel,'html',force=True) #it is known that this is an html file, and it needs forced to be added, since usually already added before

    def put_url(self,url,id=None,imagediscardsize=(120,120),recurselevel=0,queue='url',force=False):
        """Check if url already scheduled for download otherwise add to queue
        
        If recurselevel<0 only images will be downloaded
        """
        if force or (url not in self.urlset):
            if len(self.urlset)>=self.maxurlhistory:
                self.urlset.pop(0) #remove the oldest item; NOTE: it is possible that some urls are downloaded multiple times; if everything is stored
            self.urlset.append(url)
            self.urlqueue_added[queue] = True
            if id == None:
                id = self.getID()
            self.urlqueue[queue].put((id,url,imagediscardsize,recurselevel)) #add url to THE queue where it gets handled by THE threads
            return True
        return False

    def getImageIterator(self):
        while True:
            try:
                tuple = self.downloaded_images.get_nowait() #(image,id)
            except Queue.Empty:
                break
            yield tuple
    def image_done(self):
        self.downloaded_images.task_done()

    def getWPage(self):
        try:
            return self.downloaded_wpages.get_nowait() #(webpage,url,recursivelevel,id)
        except Queue.Empty:
            return None,None,None
    def webpage_done(self):
        self.downloaded_wpages.task_done()

    def getstats(self):
        return " %8d %9d %9d %9d"%(self.urlqueue['url'].qsize(),self.urlqueue['html'].qsize(),self.downloaded_wpages.qsize(),self.downloaded_images.qsize())
    def stats_header(self):
        return " urlqueue htmlqueue dl_wpages dl_images"

    def getall_stats(self):
        return self.stats.get_flat()+self.getstats()
    def allstats_header(self):
        return self.stats.getheader()+self.stats_header()

    def check_if_finished(self):
        #time.sleep(0.1)
        for k in self.urlqueue.keys():
            self.stats.avg('urlqueue_%s'%k,self.urlqueue[k].qsize())
        self.stats.avg('dl_wpages',self.downloaded_wpages.qsize())
        self.stats.avg('dl_images',self.downloaded_images.qsize())
        for k in self.urlqueue.keys():
            self.stats.max('urlqueue_%s'%k,self.urlqueue[k].qsize())
        self.stats.max('dl_wpages',self.downloaded_wpages.qsize())
        self.stats.max('dl_images',self.downloaded_images.qsize())
        self.stats.max('urlhist',len(self.urlset))
        stats_string=self.stats.get_str()
        self._logDebug(stats_string)
        self._logDebug(self.stats_header())
        self._logDebug(self.getstats())

        allalive=True
        for th in self.threadlist:
            allalive = allalive and th.isAlive()
        if not allalive:
            return (True,None)
            
        queues_done = True
        for k in self.urlqueue.keys():
            self.urlqueue_added[k] = False #checks if something is added to the queue during the following check
            queues_done = queues_done and self.urlqueue[k].all_done()
            if self.urlqueue[k].qsize()==0:
                print k+' unfinished: %d'%self.urlqueue[k].get_notdone()
        if not (queues_done and self.downloaded_wpages.all_done()): #urlqueue can be filled up bye non-processed downloaded_wpages. can fill up downloaded_wpages and downloaded_images; self.downloaded_wpages.join() could fill up urlqueue, but will change urlque_added in that case. 
            if self.downloaded_wpages.qsize()==0:
                print 'dl-wpages unfinished: %d'%self.downloaded_wpages.get_notdone()
            return (False,None)

        queues_added = False
        for k in self.urlqueue.keys():
            queues_added = queues_added or self.urlqueue_added[k]
        if queues_added: #something was added to one of the queues  need to check everything again
            return (False,None)

        if self.downloaded_images.qsize()==0:
            print 'dl-images unfinished: %d'%self.downloaded_images.get_notdone()
        if self.downloaded_images.all_done(): #doesn't effect the other queues just waiting until all of them are processed
            #all done, shutdown downloader_threads
            self._logInfo('Shutdown threads...')
            for thread in self.threadlist:
                thread.shutdown()
            for thread in self.threadlist:
                thread.join()
            self._logInfo('    done, shutdown threads!!!')
            self._logInfo('####################')
            self._logInfo('Download statistics:')
            self._logInfo(stats_string)
            self._logInfo('####################')
            return (True,stats_string)

        return (False,None)


class downloader_thread(myLog,threading.Thread):
    def __init__(self,dd):
        threading.Thread.__init__(self)
        #self.setName('downloader')
        self.setDaemon(True)
        self.downloader=dd
        self.__shutdown=False

    def shutdown(self):
        self.__shutdown=True

    def run(self):
        while not self.__shutdown:
            time.sleep(0.1)
            imageonly=False 
            put_back_in_queue=False

            if self.downloader.downloaded_wpages.qsize()>=self.downloader.max_downloadedwpages: #NOTE: this does NOT enforce a strict limit on the queue due to multithreading
                put_back_in_queue=True #if it is an html, will not be downloaded in this case due to imageonly=True
                imageonly=True #only download images, which are needed to "close" parsed webpages and so on

            if self.downloader.downloaded_images.qsize()>=self.downloader.max_downloadedImages: #NOTE: this does NOT enforce a strict limit on the queue 
                #nothing to do since too many images donwloaded already TODO: could change this to download webpages only, but there are usually enough downloaded
                time.sleep(1)
                continue

            try:
                queue='url'
                id,url,imagediscardsize,recurselevel = self.downloader.urlqueue[queue].get_nowait() 
            except Queue.Empty:
                #check if some html-files are in the queue and download those if size of downloaded_wpages not exceeded
                try:
                    if imageonly:
                        continue #really nothing to do at the moment, due to exceeded size of downloaded_wpages queue
                    queue='html' #FIXME: should download form here if downloaded_wpages is empty and parsed_wpages not full
                    id,url,imagediscardsize,recurselevel = self.downloader.urlqueue[queue].get_nowait() 
                    if recurselevel<=0:
                        raise "something wrong, this can't happen"
                except Queue.Empty:
                    continue # queue is currently empty nothing to do
            
            if recurselevel<=0:
                imageonly=True
                put_back_in_queue=False #don't download webpages, i.e. don't put the url back in the queue if it turned out to be html

            image = internetFile(url,discardsize=imagediscardsize,imageonly=imageonly,stats=self.downloader.stats)

            #print "URL: ",self.getName(),id,url,imagediscardsize,recurselevel,image.isHTML
            if image.isNotAnImage:
                self.downloader.downloaded_images.put((None,id,None)) #just to know which urls have been downloaded, so that their context can be deleted in pageParser
            else:
                self.downloader.downloaded_images.put((image,id,recurselevel))

            if image.isHTML:
                #print recurselevel,put_back_in_queue,imageonly,image.downloaded
                if image.downloaded:
                    self.downloader.downloaded_wpages.put((image,id,recurselevel))
                elif put_back_in_queue: #not downloaded due to exceeded queuesize, but needs to be downloaded
                    self.downloader.put_html(url,id,recurselevel)
            elif image.isNotAnImage: #neither image nor html
                #too much spam self._logDebug("ID: %d; URL: %s; discarded because: %s"%(id,url.encode('utf-8'),image.discardReason))
                pass

            self.downloader.urlqueue[queue].task_done() #reports to the queue that this images is downloaded and handled


class internetFile(myLog):
    """Represents and downloads an image/webpage from the internet.

    Will download the image/webpage from the internet and assign a unique name to the image.
    Maximum image size: 5 Mb.  (Download will abort if file is bigger than 2 Mb.)
    Minimum image size: 120x120 (Download will abort if file is smaller than specified)
    Contains the infoDesc corresponding to that specific image

    Heavily based on: webGobbler 1.2.5 (http://sebsauvage.net/python/webgobbler/)

    """
    # We give the USER_AGENT a simple browser type, because some sites will disable
    # irritating AJAX things for us if we do.
    USER_AGENT = 'Lynx/2.8.5rel.1 libwww-FM/2.14 SSL-MM/1.4.1 OpenSSL/0.9.8a'

    MAXIMUMIMAGESIZE = 5000000

    # Accepted MIME type.
    # Only these types will be considered images and downloaded.
    # key=MIME type (Content-Type),  value=file extension (which will be used to save
    # the file in the imagepool directory)
    ACCEPTED_MIME_TYPES = { 'image/jpeg': '.jpg',
                            'image/gif' : '.gif',
                            'image/png' : '.png',
                            'image/pjpeg':'.jpg', #probably some IE proprietary format
                            'image/bmp' : '.bmp',   # Microsoft Windows space-hog file format
                            'image/pcx' : '.pcx',   # old ZSoft/Microsoft PCX format (used in Paintbrush)
                            'image/tiff': '.tiff'
                          }

    def __init__(self,url,discardsize=(120,120),nrprefix=None,imageonly=True,stats=LockedStats()):
        ''' url (string): url of the image to download.
        '''
        self.stats=stats
        self.image = None         # Raw binary image data (as downloaded from the internet) saved in a file (parser has problems)
        self.url=url
        self.filename = None      # Image filename (computed)
        self.downloaded = False
        self.isNotAnImage = True  # True if this URL is not an image.
        self.isHTML = False 
        self.discardReason = ""   # Reason why
        self.discardsize = discardsize # Discard images smaller than ...
        self.nrprefix = nrprefix # Use this prefix for image name

        # Build and send the HTTP request:
        request_headers = { 'User-Agent': self.USER_AGENT }
        if not re.match('^http://',self.url):
            self.url = 'http://' + self.url
        request = urllib2.Request(self.url, None, request_headers)  # Build the HTTP request
        self.stats.touch_request()
        try:
            urlfile = urllib2.urlopen(request)
        except urllib2.HTTPError, exc:
            if exc.code == 404:
                self.discardReason = "not found"  # Display a simplified message for HTTP Error 404.
            else:            
                self.discardReason = "HTTP request failed with error %d (%s)" % (exc.code, exc.msg)
            return    # Discard this image.      
            # TODO: display simplified error message for some other HTTP error codes ?
        except urllib2.URLError, exc:
            self._logDebug('urllib2 URLError: %s'%str(exc.reason))
            self.discardReason = str(exc.reason)
            return    # Discard this image.
        except Exception, exc:
            self._logDebug('urllib2: %s'%str(exc))
            self.discardReason = str(exc)
            return    # Discard this image.
        self.realurl = urlfile.geturl() #if there are redirects this url is different from url
        #TODO: catch HTTPError to catch Authentication requests ? (see urllib2 manual)
        # (URLs requesting authentication should be discarded.)

        # Check image size announced in HTTP response header.
        # (so that we can abort the download right now if the file is too big.)
        file_size = 0
        try:
            file_size = int( urlfile.info().getheader("Content-Length","0") )
        except ValueError: # Content-Length does not contains an integer
            urlfile.close()
            self.discardReason = "bogus data in Content-Length HTTP headers"
            return  # Discard this image.    
        # Note that Content-Length header can be missing. That's not a problem.
        if file_size > self.MAXIMUMIMAGESIZE:
            urlfile.close()
            self.discardReason = "too big"
            return  # Image too big !  Discard it.

        # If the returned Content-Type is not recognized, ignore the file.
        # ("image/jpeg", "image/gif", etc.)
        MIME_Type = re.sub(".*(image/.*?);.*","\\1",urlfile.info().getheader("Content-Type",""))
        if not self.ACCEPTED_MIME_TYPES.has_key(MIME_Type):
            self.discardReason = "not an image (%s)" % MIME_Type
            if re.match('text/html',MIME_Type):
                if not imageonly: #download not only images, also this HTML
                    try:
                        self.data = urlfile.read(self.MAXIMUMIMAGESIZE) #truncates webpage at MAXIMUMIMAGESIZE
                    except Exception, e:
                        self._logDebug("Discard: %s; %s"%(str(e.args), str(dir(e))))
                        self.discardReason = "error while downloading webpage: %s"%e
                        urlfile.close()
                        return  # Discard image if there was a problem downloading it.
                    self.stats.touch_html()
                    self.stats.touch_html_bytes(len(self.data))
                    self.downloaded = True
                self.isHTML = True
            urlfile.close()
            return 
            
        # Get the file extension corresponding to this MIME type
        # (eg. "imag/jpeg" --> ".jpg")
        self.file_extension = self.ACCEPTED_MIME_TYPES[MIME_Type]
        self.mime_type=self.file_extension[1:]

        # Then download the image:
        try:
            imagedata = urlfile.read(self.MAXIMUMIMAGESIZE)
        except Exception, e:
            self._logDebug("Discard: %s; %s"%(str(e.args), str(dir(e))))
            self.discardReason = "error while downloading image: %s"%e
            urlfile.close()
            return  # Discard image if there was a problem downloading it.
        urlfile.close()
        imagefile=StringIO.StringIO(imagedata) #write into pseudo file FIXME is this necessary
        try:
            self.origimagesha1 = sha.new(imagefile.getvalue()).hexdigest()
        except:
            self.discardReason = "Couldn't compute sha-hash."
            raise "Couldn't compute digest from imagedata: %s"%self.url
        self.stats.touch_img()
        self.stats.touch_img_bytes(len(imagefile.getvalue()))
        self.downloaded = True
        
        # Check image size (can be necessary if Content-Length was not returned in HTTP headers.)
        try:
            if len(imagefile.getvalue()) >= self.MAXIMUMIMAGESIZE:  # Too big, probably not an image.
                self.discardReason = "too big"
                return    # Discard the image.
        except TypeError:  # Happens sometimes on len(self.imagedata):  "TypeError: len() of unsized object"
            self.discardReason = "no data"
            return    # Discard the image.

        try: #read image with PIL
            self.image = Image.open(imagefile)
            if self.image.mode != 'RGB': #convert to RGB due to compatibility
                self.image=self.image.convert('RGB')
        except: # (IOError, ValueError,OverflowError):
            #raise RuntimeError, "This is not an image."
            self._logDebug("This is not an image (for PIL): %s"%self.url)
            return # Discard the image
        
        #imagefile.close()
        try:
            if (self.discardsize[0]>self.image.size[0]) or (self.discardsize[1]>self.image.size[1]):
                self.discardReason = "too small: ",self.image.size
                return # Discard this image
        except:
            print MIME_Type
            print self.discardsize
            print type(self.image)
            raise

        try:
            imagestring=self.image.tostring()
        except: # (IOError, ValueError,OverflowError):
            #raise RuntimeError, "This is not an image."
            self._logDebug("This is not an image (for PIL): %s"%self.url)
            self.discardReason = "PIL can't handle it"
            return # Discard the image
        try:
            self.imagesha1 = sha.new(imagestring).hexdigest()
        except IOError:
            raise "Couldn't compute digest from image: %s"%self.url
        self.info=mkdb_mod.imageDescr()
        self.info.addQueryInfo(('OriginalSHA',str(self.origimagesha1)))
        self.info.addQueryInfo(('OriginalSIZE','%dx%d'%(self.image.size[0],self.image.size[1])))
        self.info.addQueryInfo(('OriginalURL',str(self.realurl)))
        self.info.addQueryInfo(('BaseImageURL',str(self.url)))
        self.info.addQueryInfo(('mimetype',str(self.mime_type)))
        self.discardReason = ""
        self.isNotAnImage = False  # The image is ok.

    #def getImage(self):
    #    ''' Returns the image as a PIL Image object.
    #        Usefull for collectors to read image properties (size, etc.)
    #        Output: a PIL Image object.   None if the image cannot be understood.
    #    '''
    #    if self.isNotAnImage:
    #        return None
    #    try:
    #        image = Image.open(self.imagefile)
    #        print "image ok"
    #        return image
    #    except IOError, exc: 
    #        self.isNotAnImage= True
    #        raise RuntimeError, "This is not an image."
    #        return None
    #    #ImageFile.Parser() seems to have some problems with some images
    #    #imageparser = ImageFile.Parser()  # from the PIL module
    #    #image = None
    #    #try:
    #    #    imageparser.feed(self.imagedata)
    #    #    image = imageparser.close()   # Get the Image object.
    #    #    return image
    #    #except IOError:  # PIL cannot understand file content.
    #    #    self.isNotAnImage = True
    #    #    raise RuntimeError, "This is not an image."
    #    #    return None

    def saveToDisk(self, destinationDirectory, file_extension=None):
        """Save the image and the image info to disk.

        Filename will be automatically computed from file content (SHA1).
        This eliminates duplicates in the destination directory.
        Input: destinationDirectory (string): The destination directory.
                   Do not specify a filename (Filename is automatically computed).
        
        """
        if file_extension!=None and file_extension!="" and file_extension!=".":
            self.file_extension=file_extension
        if self.isHTML:
            self.filename = sha.new(self.data).hexdigest()
            open(os.path.join(destinationDirectory,self.filename+'.html'),'w').write(self.data); 
            return self.filename 

        if self.isNotAnImage: #check again before saving, it might have changed e.g. in resizeArea()
            self._logDebug('Tried to save non-image non html: %s'%self.url)
            return #Discard Image

        if self.isNotAnImage:
            raise RuntimeError, "This is not an image. Cannot compute filename"
        if self.nrprefix != None:
            self.filename = 'img_'+self.nrprefix+'_'+self.imagesha1 # SHA1 in hex + image extension
        else:
            self.filename = 'img_'+self.imagesha1 # SHA1 in hex + image extension
        file=os.path.join(destinationDirectory,self.filename)

        try:
            self.image.save(file+self.file_extension)
            #file = open(os.path.join(destinationDirectory,self.filename)+self.file_extension,'w+b')
            #file.write(self.imagefile.getvalue())
            #file.close()
        except IOError:
            self._logInfo("Couldn't save image: %s"%self.filename)
        else:
            self.info.saveToDisk(file)
        return self.filename

    def resizeArea(self, size=(640,480)):
        """Resize the image to an image with equivalent area by keeping the aspect ratio."""
        if self.isNotAnImage:
            raise RuntimeError, "This is not an image. Cannot resize."

        #keep area/number of pixels constant
        area = size[0]*size[1]
        #i = self.getImage()
        isize=self.image.size
        ratio=1.0*isize[0]/isize[1]
        size=(int(round(math.sqrt(area*ratio))),int(round(math.sqrt(area/ratio))))
        try:
            self.image.thumbnail(size,Image.ANTIALIAS)
        except:
            self._logException('Could not resize: %s'%self.url)
            self.isNotAnImage=True
            return
        #self.file_extension='.png'
        try:
            self.imagesha1 = sha.new(self.image.tostring()).hexdigest()
        except IOError:
            raise "Couldn't compute digest from image: %s"%self.realurl

        #see Imaging-1.1.5/libImaging/Pack.c or encode.c JpegEncode.c for details
        #if (!PyArg_ParseTuple(args, "ss|iiiiiii", &mode, &rawmode, &quality,
		#	  &progressive, &smooth, &optimize, &streamtype,
        #                  &xdpi, &ydpi))
        # self.mode is passed automaticcaly as &mode
        # have to fix a bug in "Image.py" increase value in #l, s, d = e.encode(65536)
        #self.imagedata=i.tostring("jpeg","RGB",90,0,0,1,0,0,0)
        
        ## tostring does not support png --> create a pseudo-file 
        #pngfile = StringIO.StringIO()
        #i.convert('RGB').save(pngfile,'png',optimize=1)
        ##self.imagedata = pngfile.getvalue()
        #self.imagefile.close()
        #self.imagefile=pngfile
        #self.file_extension='.png'
