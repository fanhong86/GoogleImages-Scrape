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

Module to provide basic functionality needed to create ImageDatabases.

Contains classes to:
    - download images from the internet and save it with a unique filename (class: downloader)
    - add relevant information to a text-file connected to the image (class: imageDescr)

    - some helper classes and methods

"""

__author__ = "Florian Schroff <schroff@robots.ox.ac.uk>"
__version__ = "Version 0.1"
__date__ = "2007"
__copyright__ = "Copyright (c) 2007. All Rights Reserved."

import Image
import ImageFile
ImageFile.MAXBLOCK = 1000000 # default is 64k
import os
import sys
import errno
import ConfigParser
import StringIO
import logging
#import numpy
#import scipy
import gzip
import re
import copy
import shutil
import math
from downloader import internetFile
import downloader
from FLOSlog import myLog

########## Global Variables and Methods that are used for configuration ##########

annotateImages_cgi=""

def compute_serverdir(directory):
    """ This method should return the directory of the data as seen by the server, given the directory that is given as argument to this script"""
    serverdir=directory
    serverdir=re.sub('.*/','',serverdir)
    serverdir=re.sub('.*ImageDatabases/','',serverdir)
    if re.match('.*mkdb_annotate.*',serverdir):
        serverdir=re.sub('.*/mkdb_annotate','',serverdir)
        return ''+serverdir
    if re.match('.*dbs.*',serverdir):
        serverdir=re.sub('.*/dbs','',serverdir)
        return ''+serverdir


########## Global Methods #########

def stripTags(s):
    """Strips html tags, and substitutes each tag by a single space."""

    # this list is neccesarry because chk() would otherwise not know
    # that intag in stripTags() is ment, and not a new intag variable in chk().
    intag = [False]
    
    def chk(c):
        if intag[0]:
            intag[0] = (c != '>')
            return ''  #remove tag and content
        elif c == '<':
            intag[0] = True
            return ' ' #substitute tag with space
        return c #return the character as is
    
    return ''.join(chk(c) for c in s)

def strip2Alphanum(s):
    """strips all non alphanumerical characters, and reduces all spaces to one space"""
    return re.sub(' +',' ',re.sub('[^a-zA-Z0-9 ]',' ',s))

########## Classes ##########
#test_text = "Keep this Text <remove><me /> KEEP </remove> 123"
#import HTMLParser
#class MLStripper(HTMLParser.HTMLParser):
#    def __init__(self):
#        self.reset()
#        self.fed = []
#    def handle_data(self, d):
#        self.fed.append(d)
#    def get_fed_data(self):
#        return ''.join(self.fed)
#
#x = MLStripper()
#x.feed(test_text)
#x.get_fed_data()

class myConfigParser(ConfigParser.SafeConfigParser):
    """Write the config-file in alphabetical order."""
    def write(self,file):
        sections=self.sections()
        sections.sort()
        for section in sections:
            items=self.items(section,raw=True)
            file.write(u'[%s]\n'%section)
            items.sort()
            for i in items:
                try:
                    attrpair=u"%s = %s\n"%(i[0],i[1])
                except UnicodeDecodeError:
                    attrpair=u"%s = %s\n"%(i[0],unicode(i[1],'utf-8','ignore'))
                #escape % otherwise the configparser throughs exception when reading
                attrpair=re.sub('%+','%%',attrpair)
                file.write(attrpair)
            file.write(u"\n")

class endProgram(RuntimeError):
    pass

class imageDescr(myLog):
    """Class to handle the image description containing:
    - Image URL
    - Original size
    - Retrieval query
    - Tags or surrounding part from web page
    
    """

    #TODO change init or overload it so that __init__(filename) works as well
    def __init__(self,filename=None):
        self.filename = filename
        self.imageinfo = [] # tuplelist (name,value); CHANGED to dictionary {name:value}
        self.annotation= [] # tuplelist (name,value); CHANGED to dictionary {name:value}
        self.queryinfo = [{}] # list of directories(tuplelists); each query corresponds to one tuplelist/dictionary; CHANGED to dictionary {name:value}
        self.readOrigFile=False

    def addImageInfo(self,infotuple):
        if isinstance(infotuple,tuple):
            infotuple={infotuple[0]:infotuple[1]}
        self.imageinfo.update(infotuple)

    def addQueryInfo(self,querytuplelist):
        '''Add the dictionary(tuples) to the last query in queryinfo'''
        if isinstance(querytuplelist,tuple):
            querytuplelist={querytuplelist[0]:querytuplelist[1]}
            self.queryinfo[-1].update(querytuplelist)
        elif isinstance(querytuplelist,dict):
            self.queryinfo[-1].update(querytuplelist)
        else:
            raise RuntimeError, "passed argument is of wrong type"

    def __newQuery(self):
        '''adds an empty list to query info, such that all calls of addQueryInfo add dictionaries to that list'''
        self.queryinfo.append({})

    def iterateQueries(self):
        for q in xrange(len(self.queryinfo)):
            yield self.queryinfo[q]

    def read(self):
        cp = myConfigParser()
        cp.read(self.filename) #ignores non-existent files
        for s in cp.sections(): 
            if re.match('Query',s): #read all query sections and add them
                if self.queryinfo[0]!={}:
                    self.__newQuery()
                self.addQueryInfo(dict(cp.items(s)))
            if re.match('Annotation',s):
                self.annotation=dict(cp.items(s)) #only these annotations are preserved
            if re.match('ImageInformation',s):
                self.imageinfo=dict(cp.items(s))
        self.readOrigFile=True

    def saveToDisk(self, destination=None):
        """Outputs the data in .INI file-format.

        Read the original file, if it wasn't read by call of imgDesc.read(). This way it automatically appends to existing files,
        but allows to update the original file as well (read() -> change -> saveToDisk).
        
        """
        #FIXME: maybe check if exact same queryinfo already exists and don't add it again
        if destination!=None:
            self.filename=destination+'.txt'
        if not self.readOrigFile:
            self.read()
        else:
            if os.path.isfile(self.filename) and destination!=None:
                raise "Not allowed to write imgDescr to a different file than the one you read from!!!"
        cp = myConfigParser() #discard old info
        #check for query info's that exist in that exact same version twice
        for q1 in xrange(len(self.queryinfo)):
            occursagain=False
            for q2 in xrange(q1+1,len(self.queryinfo)):
                occurence=0
                for k,v in self.queryinfo[q1].iteritems():
                    if v==self.queryinfo[q2].get(k):
                        occurence+=1
                if occurence==len(self.queryinfo[q1]) and len(self.queryinfo[q1])==len(self.queryinfo[q2]): #they are the same
                    occursagain=True
            if not occursagain:
                if not isinstance(self.queryinfo[q1],dict):
                    raise "Arghhhhhhhhhhhhhhh!"
                if len(self.queryinfo[q1])>0:
                    query='Query'+str(q1)
                    cp.add_section(query)
                    for k,v in self.queryinfo[q1].iteritems():
                        cp.set(query,k,v)
        self.queryinfo=[[]]
            
        if len(self.annotation)>0:
            cp.add_section('Annotation')
            for k,v in self.annotation.iteritems():
                cp.set('Annotation',k,v)
            self.annotation=[]
        if len(self.imageinfo)>0:
            cp.add_section('ImageInformation')
            for k,v in self.imageinfo.iteritems():
                cp.set('ImageInformation',k,v)
            self.imageinfo=[]

        # ConfigParser can only write to a file --> create a pseudo-file (inifile)
        inifile = StringIO.StringIO()
        cp.write(inifile)
        data = inifile.getvalue()
        inifile.close()
        open(self.filename,'w').write(data.encode('utf-8'))

    def add(self,filename):
        '''Add this info file to the current infofile'''
        cp = myConfigParser()
        cp.read(filename)
        for s in cp.sections():
            if re.match('Query',s): #only add query sections #TODO: extend for others maybe
                self.addQueryInfo(dict(cp.items(s)))
                self.__newQuery()
