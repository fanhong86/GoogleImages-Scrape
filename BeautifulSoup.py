"""Beautiful Soup
Elixir and Tonic
"The Screen-Scraper's Friend"
v3.0.0
http://www.crummy.com/software/BeautifulSoup/

Beautiful Soup parses arbitrarily invalid XML- or HTML-like substance
into a tree representation. It provides methods and Pythonic idioms
that make it easy to search and modify the tree.

A well-formed XML/HTML document will yield a well-formed data
structure. An ill-formed XML/HTML document will yield a
correspondingly ill-formed data structure. If your document is only
locally well-formed, you can use this library to find and process the
well-formed part of it. The BeautifulSoup class has heuristics for
obtaining a sensible parse tree in the face of common HTML errors.

Beautiful Soup works with Python 2.2 and up. It has no external
dependencies, but you'll have more success at converting data to UTF-8
if you also install these three packages:

* chardet, for auto-detecting character encodings
  http://chardet.feedparser.org/
* cjkcodecs and iconv_codec, which add more encodings to the ones supported
  by stock Python.
  http://cjkpython.i18n.org/

Beautiful Soup defines classes for four different parsing strategies:

 * BeautifulStoneSoup, for parsing XML, SGML, or your domain-specific
   language that kind of looks like XML.

 * BeautifulSoup, for parsing run-of-the-mill HTML code, be it valid
   or invalid.

 * ICantBelieveItsBeautifulSoup, for parsing valid but bizarre HTML
   that trips up BeautifulSoup.

 * BeautifulSOAP, for making it easier to parse XML documents that use
   lots of subelements containing a single string, where you'd prefer
   they put that string into an attribute (such as SOAP messages).

You can subclass BeautifulStoneSoup or BeautifulSoup to create a
parsing strategy specific to an XML schema or a particular bizarre
HTML document. Typically your subclass would just override
SELF_CLOSING_TAGS and/or NESTABLE_TAGS.
"""
from __future__ import generators

__author__ = "Leonard Richardson (leonardr@segfault.org)"
__version__ = "2.1.1"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2004-2005 Leonard Richardson"
__license__ = "PSF"

from sgmllib import SGMLParser, SGMLParseError
import codecs
import types
import re
import sgmllib
from htmlentitydefs import name2codepoint

#This code makes Beautiful Soup able to parse XML with namespaces
sgmllib.tagfind = re.compile('[a-zA-Z][-_.:a-zA-Z0-9]*')

DEFAULT_OUTPUT_ENCODING = "utf-8"

# First, the classes that represent markup elements.

class PageElement(object):
    """Contains the navigational information for some part of the page
    (either a tag or a piece of text)"""

    def setup(self, parent=None, previous=None):
        """Sets up the initial relations between this element and
        other elements."""        
        self.parent = parent
        self.previous = previous
        self.next = None
        self.previousSibling = None
        self.nextSibling = None
        if self.parent and self.parent.contents:
            self.previousSibling = self.parent.contents[-1]
            self.previousSibling.nextSibling = self
        
    def extract(self):
        """Destructively rips this element out of the tree."""
        if self.parent:
            try:
                self.parent.contents.remove(self)
            except ValueError:
                pass

        #Find the two elements that would be next to each other if
        #this element (and any children) hadn't been parsed. Connect
        #the two.        
        lastChild = self
        while hasattr(lastChild, 'contents') and len(lastChild.contents)>0:
            lastChild = lastChild.contents[-1]
        nextElement = lastChild.next

        #FIXME: IndexError: list index out of range if self is accessed????, if len(lastChild.contents)==0
        if self.previous:
            self.previous.next = nextElement
        if nextElement:
            nextElement.previous = self.previous
        self.previous = None
        lastChild.next = None

        self.parent = None        
        if self.previousSibling:
            self.previousSibling.nextSibling = self.nextSibling
        if self.nextSibling:
            self.nextSibling.previousSibling = self.previousSibling
        self.previousSibling = self.nextSibling = None       

    def insert(self,stag):
        """Inserts a new tag before self"""
        #TODO: ability to insert tags #tag = Tag(self.parent.parserClass, stag, None, self.parent, self)
        tag = NavigableString(stag)
        for i in range(len(self.parent.contents)):
            if self.parent.contents[i] is self:
                self.parent.contents.insert(i,tag)
                break
        tag.parent = self.parent
        tag.nextSibling = self
        tag.next=self
        tag.previousSibling = self.previousSibling
        tag.previous=self.previous
        try:
            self.previous.next = tag
        except AttributeError:
            print 'Probably the first tag, dont know how to insert properly'
        if hasattr(self.previousSibling,'nextSibling'):
            self.previousSibling.nextSibling = tag
        self.previous = tag
        self.previousSibling = tag
        

    def findNext(self, name=None, attrs={}, text=None, **kwargs):
        """Returns the first item that matches the given criteria and
        appears after this Tag in the document."""
        return self._first(self.fetchNext, name, attrs, text, **kwargs)
    firstNext = findNext

    def fetchNext(self, name=None, attrs={}, text=None, limit=None, **kwargs):
        """Returns all items that match the given criteria and appear
        before after Tag in the document."""
        return self._fetch(name, attrs, text, limit, self.nextGenerator)

    def findNextSibling(self, name=None, attrs={}, text=None, **kwargs):
        """Returns the closest sibling to this Tag that matches the
        given criteria and appears after this Tag in the document."""
        return self._first(self.fetchNextSiblings, name, attrs, text,
                           **kwargs)
    firstNextSibling = findNextSibling

    def fetchNextSiblings(self, name=None, attrs={}, text=None, limit=None,
                          **kwargs):
        """Returns the siblings of this Tag that match the given
        criteria and appear after this Tag in the document."""
        return self._fetch(name, attrs, text, limit, self.nextSiblingGenerator,
                           **kwargs)

    def findPrevious(self, name=None, attrs={}, text=None, **kwargs):
        """Returns the first item that matches the given criteria and
        appears before this Tag in the document."""
        return self._first(self.fetchPrevious, name, attrs, text, **kwargs)

    def fetchPrevious(self, name=None, attrs={}, text=None, limit=None,
                      **kwargs):
        """Returns all items that match the given criteria and appear
        before this Tag in the document."""
        return self._fetch(name, attrs, text, limit, self.previousGenerator,
                           **kwargs)
    firstPrevious = findPrevious

    def findPreviousSibling(self, name=None, attrs={}, text=None, **kwargs):
        """Returns the closest sibling to this Tag that matches the
        given criteria and appears before this Tag in the document."""
        return self._first(self.fetchPreviousSiblings, name, attrs, text,
                           **kwargs)
    firstPreviousSibling = findPreviousSibling

    def fetchPreviousSiblings(self, name=None, attrs={}, text=None,
                              limit=None, **kwargs):
        """Returns the siblings of this Tag that match the given
        criteria and appear before this Tag in the document."""
        return self._fetch(name, attrs, text, limit,
                           self.previousSiblingGenerator, **kwargs)

    def findParent(self, name=None, attrs={}, **kwargs):
        """Returns the closest parent of this Tag that matches the given
        criteria."""
        # NOTE: We can't use _first because fetchParents takes a different
        # set of arguments.
        r = None
        l = self.fetchParents(name, attrs, 1)
        if l:
            r = l[0]
        return r
    firstParent = findParent

    def fetchParents(self, name=None, attrs={}, limit=None, **kwargs):
        """Returns the parents of this Tag that match the given
        criteria."""

        return self._fetch(name, attrs, None, limit, self.parentGenerator,
                           **kwargs)

    #These methods do the real heavy lifting.

    def _first(self, method, name, attrs, text, **kwargs):
        r = None
        l = method(name, attrs, text, 1, **kwargs)
        if l:
            r = l[0]
        return r
    
    def _fetch(self, name, attrs, text, limit, generator, **kwargs):
        "Iterates over a generator looking for things that match."

        if isinstance(name, SoupStrainer):
            strainer = name
        else:
            if not kwargs and not hasattr(attrs, 'items'):
                attrs = {'class' : attrs}
            # Build a SoupStrainer
            strainer = SoupStrainer(name, attrs, text, **kwargs)
        results = ResultSet(strainer)
        g = generator()
        while True:
            try:
                i = g.next()
            except StopIteration:
                break
            if i:
                found = strainer.search(i)
                if found:
                    results.append(found)
                    if limit and len(results) >= limit:
                        break
        return results

    #These Generators can be used to navigate starting from both
    #NavigableStrings and Tags.                
    def nextGenerator(self):
        i = self
        while i:
            i = i.next
            yield i

    def nextSiblingGenerator(self):
        i = self
        while i:
            i = i.nextSibling
            yield i

    def previousGenerator(self):
        i = self
        while i:
            i = i.previous
            yield i

    def previousSiblingGenerator(self):
        i = self
        while i:
            i = i.previousSibling
            yield i

    def parentGenerator(self):
        i = self
        while i:
            i = i.parent
            yield i

    # Utility methods
    def substituteEncoding(self, str, encoding=None):
        encoding = encoding or "utf-8"
        return str.replace("%SOUP-ENCODING%", encoding)    

    def toEncoding(self, s, encoding=None):
        """Encodes an object to a string in some encoding, or to Unicode.
        ."""
        try:
            if isinstance(s, unicode):
                if encoding:
                    s = s.encode(encoding)
            elif isinstance(s, str):
                if encoding:
                    s = s.encode(encoding)
                else:
                    s = unicode(s)
            else:
                if encoding:
                    s  = self.toEncoding(str(s), encoding)
                else:
                    s = unicode(s)
        except UnicodeDecodeError:
            print encoding
            print type(s)
            print s
            print "Ignore Decoding errors"
            s = unicode(s,'utf-8','ignore').encode(encoding)
            #raise
        return s

class NavigableString(unicode, PageElement):

    def __getattr__(self, attr):
        """text.string gives you text. This is for backwards
        compatibility for Navigable*String, but for CData* it lets you
        get the string without the CData wrapper."""
        if attr == 'string':
            return self
        else:
            raise AttributeError, "'%s' object has no attribute '%s'" % (self.__class__.__name__, attr)

    def __unicode__(self):
        return __str__(self, None)

    def __str__(self, encoding=DEFAULT_OUTPUT_ENCODING):
        if encoding:
            return self.encode(encoding)
        else:
            return self
        
class CData(NavigableString):

    def __str__(self, encoding=DEFAULT_OUTPUT_ENCODING):
        return "<![CDATA[%s]]>" % NavigableString.__str__(self, encoding)

class ProcessingInstruction(NavigableString):
    def __str__(self, encoding=DEFAULT_OUTPUT_ENCODING):
        output = self
        if "%SOUP-ENCODING%" in output:
            output = self.substituteEncoding(output, encoding)
        return "<?%s>" % self.toEncoding(output, encoding)

class Comment(NavigableString):
    def __str__(self, encoding=DEFAULT_OUTPUT_ENCODING):
        return "<!--%s-->" % NavigableString.__str__(self, encoding)    

class Declaration(NavigableString):
    def __str__(self, encoding=DEFAULT_OUTPUT_ENCODING):
        return "<!%s>" % NavigableString.__str__(self, encoding)        

class Tag(PageElement):

    """Represents a found HTML tag with its attributes and contents."""

    def __init__(self, parser, name, attrs=None, parent=None,
                 previous=None):
        "Basic constructor."

        # We don't actually store the parser object: that lets extracted
        # chunks be garbage-collected
        self.parserClass = parser.__class__
        self.name = name
        if attrs == None:
            attrs = []
        self.attrs = attrs
        self.contents = []
        self.setup(parent, previous)
        self.hidden = False
        self.containsSubstitutions = False

    def get(self, key, default=None):
        """Returns the value of the 'key' attribute for the tag, or
        the value given for 'default' if it doesn't have that
        attribute."""
        return self._getAttrMap().get(key, default)    

    def has_key(self, key):
        return self._getAttrMap().has_key(key)

    def __getitem__(self, key):
        """tag[key] returns the value of the 'key' attribute for the tag,
        and throws an exception if it's not there."""
        return self._getAttrMap()[key]

    def __iter__(self):
        "Iterating over a tag iterates over its contents."
        return iter(self.contents)

    def __len__(self):
        "The length of a tag is the length of its list of contents."
        return len(self.contents)

    def __contains__(self, x):
        return x in self.contents

    def __nonzero__(self):
        "A tag is non-None even if it has no contents."
        return True

    def __setitem__(self, key, value):        
        """Setting tag[key] sets the value of the 'key' attribute for the
        tag."""
        self._getAttrMap()
        self.attrMap[key] = value
        found = False
        for i in range(0, len(self.attrs)):
            if self.attrs[i][0] == key:
                self.attrs[i] = (key, value)
                found = True
        if not found:
            self.attrs.append((key, value))
        self._getAttrMap()[key] = value

    def __delitem__(self, key):
        "Deleting tag[key] deletes all 'key' attributes for the tag."
        for item in self.attrs:
            if item[0] == key:
                self.attrs.remove(item)
                #We don't break because bad HTML can define the same
                #attribute multiple times.
            self._getAttrMap()
            if self.attrMap.has_key(key):
                del self.attrMap[key]

    def __call__(self, *args, **kwargs):
        """Calling a tag like a function is the same as calling its
        fetch() method. Eg. tag('a') returns a list of all the A tags
        found within this tag."""
        return apply(self.fetch, args, kwargs)

    def __getattr__(self, tag):
        #print "Getattr %s.%s" % (self.__class__, tag)
        if len(tag) > 3 and tag.rfind('Tag') == len(tag)-3:
            return self.first(tag[:-3])
        elif tag.find('__') != 0:
            return self.first(tag)

    def __eq__(self, other):
        """Returns true iff this tag has the same name, the same attributes,
        and the same contents (recursively) as the given tag.

        NOTE: right now this will return false if two tags have the
        same attributes in a different order. Should this be fixed?"""
        if not hasattr(other, 'name') or not hasattr(other, 'attrs') or not hasattr(other, 'contents') or self.name != other.name or self.attrs != other.attrs or len(self) != len(other):
            return False
        for i in range(0, len(self.contents)):
            if self.contents[i] != other.contents[i]:
                return False
        return True

    def __ne__(self, other):
        """Returns true iff this tag is not identical to the other tag,
        as defined in __eq__."""
        return not self == other

    def __repr__(self, encoding=DEFAULT_OUTPUT_ENCODING):
        """Renders this tag as a string."""
        return self.__str__(encoding)

    def __unicode__(self):
        return self.__str__(None)

    def __str__(self, encoding=DEFAULT_OUTPUT_ENCODING,
                indent=None):
        """Returns a string or Unicode representation of this tag and
        its contents. To get Unicode, pass None for encoding.

        NOTE: since Python's HTML parser consumes whitespace, this
        method is not certain to reproduce the whitespace present in
        the original string."""

        encodedName = self.toEncoding(self.name, encoding)
        
        attrs = []
        if self.attrs:
            for key, val in self.attrs:
                fmt = '%s="%s"'
                if isString(val):
                    if self.containsSubstitutions and '%SOUP-ENCODING%' in val:
                        val = self.substituteEncoding(val, encoding)
                    if '"' in val:
                        fmt = "%s='%s'"
                        # This can't happen naturally, but it can happen
                        # if you modify an attribute value and print it out.
                        if "'" in val:
                            val = val.replace("'", "&squot;")
                attrs.append(fmt % (self.toEncoding(key, encoding),
                                    self.toEncoding(val, encoding)))
        close = ''
        closeTag = ''
        if self.isSelfClosing():
            close = ' /'
        else:
            closeTag = '</%s>' % encodedName
        indentTag, indentContents = None, None
        if indent == True and type(indent) == type(True):
            indent = 0
        if indent or (type(indent) == type(0)):
            indentTag = indent
            space = (' ' * (indentTag-1))
            indentContents = indentTag + 1
        contents = self.renderContents(encoding, indentContents)
        if self.hidden:
            s = contents
        else:
            s = []
            attributeString = ''
            if attrs:
                attributeString = ' ' + ' '.join(attrs)            
            if indent:
                s.append(space)
            s.append('<%s%s%s>' % (encodedName, attributeString, close))
            if indent:
                s.append("\n")
            s.append(contents)
            if indent:
                s.append("\n")
            if indent and closeTag:
                s.append(space)
            s.append(closeTag)
            if indent and closeTag and self.nextSibling:
                s.append("\n")
            s = ''.join(s)
        return s

    def prettify(self, encoding=DEFAULT_OUTPUT_ENCODING):
        return self.__str__(encoding, 0)

    def renderContents(self, encoding=DEFAULT_OUTPUT_ENCODING,
                       indent=None):
        """Renders the contents of this tag as a string in the given
        encoding. If encoding is None, returns a Unicode string.."""
        s=[]
        for c in self:
            text = None
            if isinstance(c, NavigableString):
                text = c.__str__(encoding)
            elif isinstance(c, Tag):
                s.append(c.__str__(encoding, indent))
            if text:
                if indent:
                    if text[-1] == '\n':
                        text = text[:-1]
                    s.append(" " * (indent-1))
                s.append(text)
        return ''.join(s)    

    #Soup methods

    def firstText(self, text, recursive=True):
        """Convenience method to retrieve the first piece of text matching the
        given criteria. 'text' can be a string, a regular expression object,
        a callable that takes a string and returns whether or not the
        string 'matches', etc."""
        return self.first(recursive=recursive, text=text)

    def fetchText(self, text, recursive=True, limit=None):
        """Convenience method to retrieve all pieces of text matching the
        given criteria. 'text' can be a string, a regular expression object,
        a callable that takes a string and returns whether or not the
        string 'matches', etc."""
        return self.fetch(recursive=recursive, text=text, limit=limit)

    def first(self, name=None, attrs={}, recursive=True, text=None,
              **kwargs):
        """Return only the first child of this
        Tag matching the given criteria."""
        r = None
        l = self.fetch(name, attrs, recursive, text, 1)
        if l:
            r = l[0]
        return r
    findChild = first

    def fetch(self, name=None, attrs={}, recursive=True, text=None,
              limit=None, **kwargs):
        """Extracts a list of Tag objects that match the given
        criteria.  You can specify the name of the Tag and any
        attributes you want the Tag to have.

        The value of a key-value pair in the 'attrs' map can be a
        string, a list of strings, a regular expression object, or a
        callable that takes a string and returns whether or not the
        string matches for some custom definition of 'matches'. The
        same is true of the tag name."""
        generator = self.recursiveChildGenerator
        if not recursive:
            generator = self.childGenerator
        return self._fetch(name, attrs, text, limit, generator, **kwargs)
    fetchChildren = fetch
    
    #Utility methods

    def isSelfClosing(self):
        """Returns true iff this is a self-closing tag as defined by the
        parser that created this tag."""        
        return self.name in self.parserClass.SELF_CLOSING_TAGS

    def append(self, tag):
        """Appends the given tag to the contents of this tag."""
        self.contents.append(tag)

    #Private methods

    def _getAttrMap(self):
        """Initializes a map representation of this tag's attributes,
        if not already initialized."""
        if not getattr(self, 'attrMap'):
            self.attrMap = {}
            for (key, value) in self.attrs:
                self.attrMap[key] = value 
        return self.attrMap

    #Generator methods
    def childGenerator(self):
        for i in range(0, len(self.contents)):
            yield self.contents[i]
        raise StopIteration
    
    def recursiveChildGenerator(self):
        stack = [(self, 0)]
        while stack:
            tag, start = stack.pop()
            if isinstance(tag, Tag):            
                for i in range(start, len(tag.contents)):
                    a = tag.contents[i]
                    yield a
                    if isinstance(a, Tag) and tag.contents:
                        if i < len(tag.contents) - 1:
                            stack.append((tag, i+1))
                        stack.append((a, 0))
                        break
        raise StopIteration

# Next, a couple classes to represent queries and their results.
class SoupStrainer(object):
    """Encapsulates a number of ways of matching a markup element (tag or
    text)."""

    class Any:
        """A simple counterpart to None. If you pass in Any for an attribute
        value, text, or tag, it will match any non-None value for that
        attribute, text, or tag name."""
        pass

    def __init__(self, tag=None, attrs={}, text=None, **kwargs):
        self.tag=tag
        self.attrs=attrs.copy()
        self.attrs.update(kwargs)
        self.text = text

    def __str__(self):
        if self.text:
            return self.text
        else:
            return "%s|%s" % (self.tag, self.attrs)
    
    def searchTag(self, markupName=None, markupAttrs={}):
        found = None
        markup = None
        if isinstance(markupName, Tag):
            markup = markupName
            markupAttrs = markup
        if (not self.tag) \
               or (markup and self._matches(markup, self.tag)) \
               or (not markup and self._matches(markupName, self.tag)):
            match = True
            markupAttrMap = None
            for attr, matchAgainst in self.attrs.items():
                if not markupAttrMap:
                    if hasattr(markupAttrs, 'get'):
                        markupAttrMap = markupAttrs
                    else:
                        markupAttrMap = {}
                        for k,v in markupAttrs:
                            markupAttrMap[k] = v
                attrValue = markupAttrMap.get(attr)
                if not self._matches(attrValue, matchAgainst):
                    match = False
                    break
            if match:
                if markup:
                    found = markup
                else:
                    found = markupName
        return found

    def search(self, markup):
        #print 'looking for %s in %s' % (self, markup)
        found = None
        # If given a list of items, scan it for a text element that
        # matches.        
        if isList(markup) and not isinstance(markup, Tag):
            for element in markup:
                if isinstance(element, NavigableString) \
                       and self.search(element):
                    found = element
                    break
        # If it's a Tag, make sure its name or attributes match.
        # Don't bother with Tags if we're searching for text.
        elif isinstance(markup, Tag):
            if not self.text:
                found = self.searchTag(markup)
        # If it's text, make sure the text matches.
        elif isinstance(markup, NavigableString):
            if self._matches(markup, self.text):
                found = markup
        else:
            raise Exception, "I don't know how to match against a %s" \
                  % markup.__class__
        return found
        
    def _matches(self, markup, matchAgainst):    
        #print "Matching %s against %s" % (markup, matchAgainst)
        result = False
        if matchAgainst == self.Any:
            result = markup != None
        elif callable(matchAgainst):
            result = matchAgainst(markup)
        else:
            #Custom match methods take the tag as an argument, but all
            #other ways of matching match the tag name as a string.
            if isinstance(markup, Tag):
                markup = markup.name
            if markup and not isString(markup):
                markup = unicode(markup)
            #Now we know that chunk is either a string, or None.
            if hasattr(matchAgainst, 'match'):
                # It's a regexp object.
                result = markup and matchAgainst.search(markup)
            elif isList(matchAgainst):
                result = markup in matchAgainst
            elif hasattr(matchAgainst, 'items'):
                result = markup.has_key(matchAgainst)
            elif matchAgainst and isString(markup):
                if isinstance(markup, unicode):
                    matchAgainst = unicode(matchAgainst)
                else:
                    matchAgainst = str(matchAgainst)

            if not result:
                result = matchAgainst == markup
        return result

class ResultSet(list):
    """A ResultSet is just a list that keeps track of the SoupStrainer
    that created it."""
    def __init__(self, source):
        list.__init__([])
        self.source = source

# Now, some helper functions.

def isList(l):
    """Convenience method that works with all 2.x versions of Python
    to determine whether or not something is listlike."""
    return hasattr(l, '__iter__') \
           or (type(l) in (types.ListType, types.TupleType))

def isString(s):
    """Convenience method that works with all 2.x versions of Python
    to determine whether or not something is stringlike."""
    try:
        return isinstance(s, unicode) or isintance(s, basestring) 
    except NameError:
        return isinstance(s, str)

def buildTagMap(default, *args):
    """Turns a list of maps, lists, or scalars into a single map.
    Used to build the SELF_CLOSING_TAGS and NESTABLE_TAGS maps out
    of lists and partial maps."""
    built = {}
    for portion in args:
        if hasattr(portion, 'items'):
            #It's a map. Merge it.
            for k,v in portion.items():
                built[k] = v
        elif isList(portion):
            #It's a list. Map each item to the default.
            for k in portion:
                built[k] = default
        else:
            #It's a scalar. Map it to the default.
            built[portion] = default
    return built

# Now, the parser classes.

class BeautifulStoneSoup(Tag, SGMLParser):

    """This class contains the basic parser and fetch code. It defines
    a parser that knows nothing about tag behavior except for the
    following:
   
      You can't close a tag without closing all the tags it encloses.
      That is, "<foo><bar></foo>" actually means
      "<foo><bar></bar></foo>".

    [Another possible explanation is "<foo><bar /></foo>", but since
    this class defines no SELF_CLOSING_TAGS, it will never use that
    explanation.]

    This class is useful for parsing XML or made-up markup languages,
    or when BeautifulSoup makes an assumption counter to what you were
    expecting."""

    XML_ENTITIES = {}
    for i in ["quot", "apos", "amp", "lt", "gt"]:
        XML_ENTITIES[i] = True 

    SELF_CLOSING_TAGS = {}
    NESTABLE_TAGS = {}
    RESET_NESTING_TAGS = {}
    QUOTE_TAGS = {}

    PARSER_MASSAGE = [(re.compile('(<[^<>]*)/>'),
                       lambda(x):x.group(1) + ' />'),
                      (re.compile('<!\s+([^<>]*)>'),
                       lambda(x):'<!' + x.group(1) + '>')
                      ]

    ROOT_TAG_NAME = '[document]'

    CONVERT_HTML_ENTITIES = "html"
    CONVERT_XML_ENTITIES = "xml"

    def __init__(self, markup="", parseOnlyThese=None, fromEncoding=None,
                 markupMassage=True, convertSmartQuotes=True,
                 convertEntities=None):
        """The Soup object is initialized as the 'root tag', and the
        provided markup (which can be a string or a file-like object)
        is fed into the underlying parser. 

        sgmllib will process most bad HTML, and the BeautifulSoup
        class has some tricks for dealing with some HTML that kills
        sgmllib, but Beautiful Soup can nonetheless choke or lose data
        if your data uses self-closing tags or declarations
        incorrectly.

        By default, Beautiful Soup uses regexes to sanitizes input,
        avoiding the vast majority of these problems. If the problems
        don't apply to you, feel free to pass in False to
        markupMassage, and you'll get better performance.

        The default parser massage techniques fix the two most common
        instances of invalid HTML that will choke sgmllib:

         <br/> (No space between name of closing tag and tag close)
         <! --Comment--> (Extraneous whitespace in declaration)

        You can pass in a custom list of (RE object, replace method)
        tuples to get Beautiful Soup to scrub your input the way you
        want."""
        
        SGMLParser.__init__(self)
        self.parseOnlyThese = parseOnlyThese
        self.fromEncoding = fromEncoding
        self.convertSmartQuotes = convertSmartQuotes
        self.convertEntities = convertEntities
        
        if hasattr(markup, 'read'):        # It's a file-type object.
            markup = markup.read()
        self.markup = markup
        self.markupMassage = markupMassage
        self._feed()
        self.markup = None                 # The markup can now be GCed
        
    def _feed(self, inDocumentEncoding=None):
        # Convert the document to Unicode.
        markup = self.markup
        if isinstance(markup, unicode):
            if not hasattr(self, 'originalEncoding'):
                self.originalEncoding = None
        else:
            dammit = UnicodeDammit\
                     (markup, [self.fromEncoding, inDocumentEncoding],
                      fixSmartQuotes=self.convertSmartQuotes)
            markup = dammit.unicode
            self.originalEncoding = dammit.originalEncoding
        if markup:
            if self.markupMassage:
                if not isList(self.markupMassage):
                    self.markupMassage = self.PARSER_MASSAGE            
                for fix, m in self.markupMassage:
                    markup = fix.sub(m, markup)
        self.reset()

        SGMLParser.feed(self, markup)
        # Close out any unfinished strings and close all the open tags.
        self.endData()
        while self.currentTag.name != self.ROOT_TAG_NAME:
            self.popTag()

    def __getattr__(self, methodName):
        """This method routes method call requests to either the SGMLParser
        superclass or the Tag superclass, depending on the method name."""
        if methodName.find('start_') == 0 or methodName.find('end_') == 0 \
               or methodName.find('do_') == 0:
            return SGMLParser.__getattr__(self, methodName)
        elif methodName.find('__') != 0:
            return Tag.__getattr__(self, methodName)
        else:
            raise AttributeError
            
    def reset(self):
        Tag.__init__(self, self, self.ROOT_TAG_NAME)
        self.hidden = 1
        SGMLParser.reset(self)
        self.currentData = []
        self.currentTag = None
        self.tagStack = []
        self.quoteStack = []
        self.pushTag(self)
    
    def popTag(self):
        tag = self.tagStack.pop()
        # Tags with just one string-owning child get the child as a
        # 'string' property, so that soup.tag.string is shorthand for
        # soup.tag.contents[0]
        if len(self.currentTag.contents) == 1 and \
           isinstance(self.currentTag.contents[0], NavigableString):
            self.currentTag.string = self.currentTag.contents[0]

        #print "Pop", tag.name
        if self.tagStack:
            self.currentTag = self.tagStack[-1]
        return self.currentTag

    def pushTag(self, tag):
        #print "Push", tag.name
        if self.currentTag:
            self.currentTag.append(tag)
        self.tagStack.append(tag)
        self.currentTag = self.tagStack[-1]

    def endData(self, containerClass=NavigableString):
        if self.currentData:
            currentData = ''.join(self.currentData)
            if not currentData.strip():
                if '\n' in currentData:
                    currentData = '\n'
                else:
                    currentData = ' '
            o = containerClass(currentData)
            o.setup(self.currentTag, self.previous)
            if self.previous:
                self.previous.next = o
            self.previous = o
            self.currentTag.contents.append(o)
            self.currentData = []        

    def _popToTag(self, name, inclusivePop=True):
        """Pops the tag stack up to and including the most recent
        instance of the given tag. If inclusivePop is false, pops the tag
        stack up to but *not* including the most recent instqance of
        the given tag."""
        if name == self.ROOT_TAG_NAME:
            return            

        numPops = 0
        mostRecentTag = None
        for i in range(len(self.tagStack)-1, 0, -1):
            if name == self.tagStack[i].name:
                numPops = len(self.tagStack)-i
                break
        if not inclusivePop:
            numPops = numPops - 1

        for i in range(0, numPops):
            mostRecentTag = self.popTag()
        return mostRecentTag    

    def _smartPop(self, name):

        """We need to pop up to the previous tag of this type, unless
        one of this tag's nesting reset triggers comes between this
        tag and the previous tag of this type, OR unless this tag is a
        generic nesting trigger and another generic nesting trigger
        comes between this tag and the previous tag of this type.

        Examples:
         <p>Foo<b>Bar<p> should pop to 'p', not 'b'.
         <p>Foo<table>Bar<p> should pop to 'table', not 'p'.
         <p>Foo<table><tr>Bar<p> should pop to 'tr', not 'p'.
         <p>Foo<b>Bar<p> should pop to 'p', not 'b'.

         <li><ul><li> *<li>* should pop to 'ul', not the first 'li'.
         <tr><table><tr> *<tr>* should pop to 'table', not the first 'tr'
         <td><tr><td> *<td>* should pop to 'tr', not the first 'td'
        """

        nestingResetTriggers = self.NESTABLE_TAGS.get(name)
        isNestable = nestingResetTriggers != None
        isResetNesting = self.RESET_NESTING_TAGS.has_key(name)
        popTo = None
        inclusive = True
        for i in range(len(self.tagStack)-1, 0, -1):
            p = self.tagStack[i]
            if (not p or p.name == name) and not isNestable:
                #Non-nestable tags get popped to the top or to their
                #last occurance.
                popTo = name
                break
            if (nestingResetTriggers != None
                and p.name in nestingResetTriggers) \
                or (nestingResetTriggers == None and isResetNesting
                    and self.RESET_NESTING_TAGS.has_key(p.name)):
                
                #If we encounter one of the nesting reset triggers
                #peculiar to this tag, or we encounter another tag
                #that causes nesting to reset, pop up to but not
                #including that tag.

                popTo = p.name
                inclusive = False
                break
            p = p.parent
        if popTo:
            self._popToTag(popTo, inclusive)

    def unknown_starttag(self, name, attrs, selfClosing=0):
        #print "Start tag %s" % name
        if self.quoteStack:
            #This is not a real tag.
            #print "<%s> is not real!" % name
            attrs = ''.join(map(lambda(x, y): ' %s="%s"' % (x, y), attrs))
            self.handle_data('<%s%s>' % (name, attrs))
            return        
        self.endData()

        if not name in self.SELF_CLOSING_TAGS and not selfClosing:
            self._smartPop(name)

        if self.parseOnlyThese and len(self.tagStack) <= 1 \
               and not self.parseOnlyThese.searchTag(name, attrs):
            return

        tag = Tag(self, name, attrs, self.currentTag, self.previous)
        if self.previous:
            self.previous.next = tag
        self.previous = tag
        self.pushTag(tag)
        if selfClosing or name in self.SELF_CLOSING_TAGS:
            self.popTag()                
        if name in self.QUOTE_TAGS:
            #print "Beginning quote (%s)" % name
            self.quoteStack.append(name)
            self.literal = 1
        return tag

    def unknown_endtag(self, name):
        if self.quoteStack and self.quoteStack[-1] != name:
            #This is not a real end tag.
            #print "</%s> is not real!" % name
            self.handle_data('</%s>' % name)
            return
        self.endData()
        self._popToTag(name)
        if self.quoteStack and self.quoteStack[-1] == name:
            self.quoteStack.pop()
            self.literal = (len(self.quoteStack) > 0)

    def handle_data(self, data):
        self.currentData.append(data)

    def _toStringSubclass(self, text, subclass):
        """Adds a certain piece of text to the tree as a NavigableString
        subclass."""
        self.endData()
        self.handle_data(text)
        self.endData(subclass)

    def handle_pi(self, text):
        """Handle a processing instruction as a ProcessingInstruction
        object, possibly one with a %SOUP-ENCODING% slot into which an
        encoding will be plugged later."""
        if text[:3] == "xml":
            text = "xml version='1.0' encoding='%SOUP-ENCODING%'"
        self._toStringSubclass(text, ProcessingInstruction)

    def handle_comment(self, text):
        "Handle comments as Comment objects."
        self._toStringSubclass(text, Comment)

    def handle_charref(self, ref):
        "Handle character references as data."
        if self.convertEntities in [self.CONVERT_HTML_ENTITIES,
                                    self.CONVERT_XML_ENTITIES]:
            data = unichr(int(ref))
        else:
            data = '&#%s;' % ref
        self.handle_data(data)

    def handle_entityref(self, ref):
        """Handle entity references as data, possibly converting known
        HTML entity references to the corresponding Unicode
        characters."""
        data = None
        if self.convertEntities == self.CONVERT_HTML_ENTITIES or \
               (self.convertEntities == self.CONVERT_XML_ENTITIES and \
                self.XML_ENTITIES.get(ref)):
            try:
                data = unichr(name2codepoint[ref])
            except KeyError:
                pass
        if not data:
            data = '&%s;' % ref
        self.handle_data(data)
        
    def handle_decl(self, data):
        "Handle DOCTYPEs and the like as Declaration objects."
        self._toStringSubclass(data, Declaration)

    def parse_declaration(self, i):
        """Treat a bogus SGML declaration as raw data. Treat a CDATA
        declaration as a CData object."""
        j = None
        if self.rawdata[i:i+9] == '<![CDATA[':
             k = self.rawdata.find(']]>', i)
             if k == -1:
                 k = len(self.rawdata)
             data = self.rawdata[i+9:k]
             j = k+3
             self._toStringSubclass(data, CData)
        else:
            try:
                j = SGMLParser.parse_declaration(self, i)
            except SGMLParseError:
                toHandle = self.rawdata[i:]
                self.handle_data(toHandle)
                j = i + len(toHandle)
        return j

class BeautifulSoup(BeautifulStoneSoup):

    """This parser knows the following facts about HTML:

    * Some tags have no closing tag and should be interpreted as being
      closed as soon as they are encountered.

    * The text inside some tags (ie. 'script') may contain tags which
      are not really part of the document and which should be parsed
      as text, not tags. If you want to parse the text as tags, you can
      always fetch it and parse it explicitly.

    * Tag nesting rules:

      Most tags can't be nested at all. For instance, the occurance of
      a <p> tag should implicitly close the previous <p> tag.

       <p>Para1<p>Para2
        should be transformed into:
       <p>Para1</p><p>Para2

      Some tags can be nested arbitrarily. For instance, the occurance
      of a <blockquote> tag should _not_ implicitly close the previous
      <blockquote> tag.

       Alice said: <blockquote>Bob said: <blockquote>Blah
        should NOT be transformed into:
       Alice said: <blockquote>Bob said: </blockquote><blockquote>Blah

      Some tags can be nested, but the nesting is reset by the
      interposition of other tags. For instance, a <tr> tag should
      implicitly close the previous <tr> tag within the same <table>,
      but not close a <tr> tag in another table.

       <table><tr>Blah<tr>Blah
        should be transformed into:
       <table><tr>Blah</tr><tr>Blah
        but,
       <tr>Blah<table><tr>Blah
        should NOT be transformed into
       <tr>Blah<table></tr><tr>Blah

    Differing assumptions about tag nesting rules are a major source
    of problems with the BeautifulSoup class. If BeautifulSoup is not
    treating as nestable a tag your page author treats as nestable,
    try ICantBelieveItsBeautifulSoup, MinimalSoup, or
    BeautifulStoneSoup before writing your own subclass."""

    SELF_CLOSING_TAGS = buildTagMap(None, ['br' , 'hr', 'input', 'img', 'meta',
                                           'spacer', 'link', 'frame', 'base'])

    QUOTE_TAGS = {'script': None}
    
    #According to the HTML standard, each of these inline tags can
    #contain another tag of the same type. Furthermore, it's common
    #to actually use these tags this way.
    NESTABLE_INLINE_TAGS = ['span', 'font', 'q', 'object', 'bdo', 'sub', 'sup',
                            'center']

    #According to the HTML standard, these block tags can contain
    #another tag of the same type. Furthermore, it's common
    #to actually use these tags this way.
    NESTABLE_BLOCK_TAGS = ['blockquote', 'div', 'fieldset', 'ins', 'del']

    #Lists can contain other lists, but there are restrictions.    
    NESTABLE_LIST_TAGS = { 'ol' : [],
                           'ul' : [],
                           'li' : ['ul', 'ol'],
                           'dl' : [],
                           'dd' : ['dl'],
                           'dt' : ['dl'] }

    #Tables can contain other tables, but there are restrictions.    
    NESTABLE_TABLE_TAGS = {'table' : [], 
                           'tr' : ['table', 'tbody', 'tfoot', 'thead'],
                           'td' : ['tr'],
                           'th' : ['tr'],
                           'thead' : ['table'],
                           'tbody' : ['table'],
                           'tfoot' : ['table'],
                           }

    NON_NESTABLE_BLOCK_TAGS = ['address', 'form', 'p', 'pre']

    #If one of these tags is encountered, all tags up to the next tag of
    #this type are popped.
    RESET_NESTING_TAGS = buildTagMap(None, NESTABLE_BLOCK_TAGS, 'noscript',
                                     NON_NESTABLE_BLOCK_TAGS,
                                     NESTABLE_LIST_TAGS,
                                     NESTABLE_TABLE_TAGS)

    NESTABLE_TAGS = buildTagMap([], NESTABLE_INLINE_TAGS, NESTABLE_BLOCK_TAGS,
                                NESTABLE_LIST_TAGS, NESTABLE_TABLE_TAGS)

    # Used to detect the charset in a META tag; see start_meta
    CHARSET_RE = re.compile("((^|;)\s*charset=)([^;]*)")

    def start_meta(self, attrs):
        """Beautiful Soup can detect a charset included in a META tag,
        try to convert the document to that charset, and re-parse the
        document from the beginning."""
        httpEquiv = None
        contentType = None
        contentTypeIndex = None
        didSecondPass = False
        tagNeedsEncodingSubstitution = False

        for i in range(0, len(attrs)):
            key, value = attrs[i]
            key = key.lower()
            if key == 'http-equiv':
                httpEquiv = value
            elif key == 'content':
                contentType = value
                contentTypeIndex = i

        if httpEquiv and contentType: # It's an interesting meta tag.
            match = self.CHARSET_RE.search(contentType)
            if match:
                if getattr(self, 'declaredHTMLEncoding'):
                    # This is our second pass through the document.
                    # Rewrite the meta tag.
                    newAttr = self.CHARSET_RE.sub\
                              (lambda(match):match.group(1) +
                               "%SOUP-ENCODING%", value)
                    attrs[contentTypeIndex] = (attrs[contentTypeIndex][0],
                                               newAttr)
                    tagNeedsEncodingSubstitution = True
                else:
                    # This is our first pass through the document.
                    # Go through it again with the new information.
                    newCharset = match.group(3)
                    if newCharset and newCharset != self.originalEncoding:
                        self.declaredHTMLEncoding = newCharset
                        self._feed(self.declaredHTMLEncoding)
                        didSecondPass = True
        if not didSecondPass:
            tag = self.unknown_starttag("meta", attrs)
            if tagNeedsEncodingSubstitution:
                tag.containsSubstitutions = True

class MinimalSoup(BeautifulSoup):
    """The MinimalSoup class"""

    RESET_NESTING_TAGS = buildTagMap('noscript')
    NESTABLE_TAGS = {}
    
class ICantBelieveItsBeautifulSoup(BeautifulSoup):

    """The BeautifulSoup class is oriented towards skipping over
    common HTML errors like unclosed tags. However, sometimes it makes
    errors of its own. For instance, consider this fragment:

     <b>Foo<b>Bar</b></b>

    This is perfectly valid (if bizarre) HTML. However, the
    BeautifulSoup class will implicitly close the first b tag when it
    encounters the second 'b'. It will think the author wrote
    "<b>Foo<b>Bar", and didn't close the first 'b' tag, because
    there's no real-world reason to bold something that's already
    bold. When it encounters '</b></b>' it will close two more 'b'
    tags, for a grand total of three tags closed instead of two. This
    can throw off the rest of your document structure. The same is
    true of a number of other tags, listed below.

    It's much more common for someone to forget to close (eg.) a 'b'
    tag than to actually use nested 'b' tags, and the BeautifulSoup
    class handles the common case. This class handles the
    not-co-common case: where you can't believe someone wrote what
    they did, but it's valid HTML and BeautifulSoup screwed up by
    assuming it wouldn't be.

    If this doesn't do what you need, try subclassing this class or
    BeautifulSoup, and providing your own list of NESTABLE_TAGS."""

    I_CANT_BELIEVE_THEYRE_NESTABLE_INLINE_TAGS = \
     ['em', 'big', 'i', 'small', 'tt', 'abbr', 'acronym', 'strong',
      'cite', 'code', 'dfn', 'kbd', 'samp', 'strong', 'var', 'b',
      'big']

    I_CANT_BELIEVE_THEYRE_NESTABLE_BLOCK_TAGS = ['noscript']

    NESTABLE_TAGS = buildTagMap([], BeautifulSoup.NESTABLE_TAGS,
                                I_CANT_BELIEVE_THEYRE_NESTABLE_BLOCK_TAGS,
                                I_CANT_BELIEVE_THEYRE_NESTABLE_INLINE_TAGS)

class MinimalSoup(BeautifulSoup):
    """The MinimalSoup class is for parsing HTML that contains
    pathologically bad markup: especially bad tables. It makes no
    assumptions about tag nesting, but it does know which tags are
    self-closing, that <script> tags contain Javascript and should not
    be parsed, that META tags may contain encoding information, and so
    on. This makes it better for parsing HTML than BeautifulStoneSoup."""
    
    RESET_NESTING_TAGS = buildTagMap('noscript')
    NESTABLE_TAGS = {}

class BeautifulSOAP(BeautifulStoneSoup):
    """This class will push a tag with only a single string child into
    the tag's parent as an attribute. The attribute's name is the tag
    name, and the value is the string child. An example should give
    the flavor of the change:

    <foo><bar>baz</bar></foo>
     =>
    <foo bar="baz"><bar>baz</bar></foo>

    You can then access fooTag['bar'] instead of fooTag.barTag.string.

    This is, of course, useful for scraping structures that tend to
    use subelements instead of attributes, such as SOAP messages. Note
    that it modifies its input, so don't print the modified version
    out.

    I'm not sure how many people really want to use this class; let me
    know if you do. Mainly I like the name."""

    def popTag(self):
        if len(self.tagStack) > 1:
            tag = self.tagStack[-1]
            parent = self.tagStack[-2]
            parent._getAttrMap()
            if (isinstance(tag, Tag) and len(tag.contents) == 1 and
                isinstance(tag.contents[0], NavigableString) and 
                not parent.attrMap.has_key(tag.name)):
                parent[tag.name] = tag.contents[0]
        BeautifulStoneSoup.popTag(self)

#Enterprise class names! It has come to our attention that some people
#think the names of the Beautiful Soup parser classes are too silly
#and "unprofessional" for use in enterprise screen-scraping. We feel
#your pain! For such-minded folk, the Beautiful Soup Consortium And
#All-Night Kosher Bakery recommends renaming this file to
#"RobustParser.py" (or, in cases of extreme enterprisitude,
#"RobustParserBeanInterface.class") and using the following
#enterprise-friendly class aliases:
class RobustXMLParser(BeautifulStoneSoup):
    pass
class RobustHTMLParser(BeautifulSoup):
    pass
class RobustWackAssHTMLParser(ICantBelieveItsBeautifulSoup):
    pass
class RobustInsanelyWackAssHTMLParser(MinimalSoup):
    pass
class SimplifyingSOAPParser(BeautifulSOAP):
    pass

######################################################
#
# Bonus library: Unicode, Dammit
#
# This class forces XML data into a standard format (usually to UTF-8
# or Unicode).  It is heavily based on code from Mark Pilgrim's
# Universal Feed Parser. It does not rewrite the XML or HTML to
# reflect a new encoding: that happens in BeautifulStoneSoup.handle_pi
# (XML) and BeautifulSoup.start_meta (HTML).

# Autodetects character encodings.
# Download from http://chardet.feedparser.org/
try:
    import chardet
#    import chardet.constants
#    chardet.constants._debug = 1
except:
    chardet = None
chardet = None

# cjkcodecs and iconv_codec make Python know about more character encodings.
# Both are available from http://cjkpython.i18n.org/
# They're built in if you use Python 2.4.
try:
    import cjkcodecs.aliases
except:
    pass
try:
    import iconv_codec
except:
    pass

class UnicodeDammit:
    """A class for detecting the encoding of a *ML document and
    converting it to a Unicode string. If the source encoding is
    windows-1252, can replace MS smart quotes with their HTML or ASCII
    equivalents."""

    # This dictionary maps commonly seen values for "charset" in HTML
    # meta tags to the corresponding Python codec names. It only covers
    # values that aren't in Python's aliases and can't be determined
    # by the heuristics in find_codec.
    CHARSET_ALIASES = { "macintosh" : "mac-roman",
                        "x-sjis" : "shift-jis" }
    
    def __init__(self, markup, overrideEncodings=[], fixSmartQuotes=True):
        self.markup, documentEncoding, sniffedEncoding = \
                     self._detectEncoding(markup)
        self.fixSmartQuotes = fixSmartQuotes
        self.triedEncodings = []
        if isinstance(markup, unicode):
            return markup

        u = None
        for proposedEncoding in overrideEncodings:
            u = self._convertFrom(proposedEncoding)
            if u: break
        if not u:
            for proposedEncoding in (documentEncoding, sniffedEncoding):
                u = self._convertFrom(proposedEncoding)
                if u: break
                
        # If no luck and we have auto-detection library, try that:
        if not u and chardet and not isinstance(self.markup, unicode):
            u = self._convertFrom(chardet.detect(self.markup)['encoding'])

        # As a last resort, try utf-8 and windows-1252:
        if not u:
            for proposed_encoding in ("utf-8", "windows-1252"):
                u = self._convertFrom(proposed_encoding)
                if u: break
        self.unicode = u
        if not u: self.originalEncoding = None

    def _convertFrom(self, proposed):        
        proposed = self.find_codec(proposed)
        if not proposed or proposed in self.triedEncodings:
            return None
        self.triedEncodings.append(proposed)
        markup = self.markup

        # Convert smart quotes to HTML if coming from an encoding
        # that might have one.
        if self.fixSmartQuotes and proposed in ("windows-1252",
                                                "ISO-8859-1", "ISO-8859-2"):
            markup = re.compile("([\x80-\x9f])").sub \
                     (lambda(x): self.MS_CHARS.get(x.group(1)), markup)

        try:
            # print "Trying to convert document to %s" % proposed
            u = self._toUnicode(markup, proposed)
            self.markup = u       
            self.originalEncoding = proposed
        except Exception, e:
            # print "That didn't work!"
            # print e
            return None        
        #print "Correct encoding: %s" % proposed
        return self.markup

    def _toUnicode(self, data, encoding):
        '''Given a string and its encoding, decodes the string into Unicode.
        %encoding is a string recognized by encodings.aliases'''

        # strip Byte Order Mark (if present)
        if (len(data) >= 4) and (data[:2] == '\xfe\xff') \
               and (data[2:4] != '\x00\x00'):
            encoding = 'utf-16be'
            data = data[2:]
        elif (len(data) >= 4) and (data[:2] == '\xff\xfe') \
                 and (data[2:4] != '\x00\x00'):
            encoding = 'utf-16le'
            data = data[2:]
        elif data[:3] == '\xef\xbb\xbf':
            encoding = 'utf-8'
            data = data[3:]
        elif data[:4] == '\x00\x00\xfe\xff':
            encoding = 'utf-32be'
            data = data[4:]
        elif data[:4] == '\xff\xfe\x00\x00':
            encoding = 'utf-32le'
            data = data[4:]
        newdata = unicode(data, encoding)
        return newdata
    
    def _detectEncoding(self, xml_data):
        """Given a document, tries to detect its XML encoding."""
        xml_encoding = sniffed_xml_encoding = None
        try:
            if xml_data[:4] == '\x4c\x6f\xa7\x94':
                # EBCDIC
                xml_data = self._ebcdic_to_ascii(xml_data)
            elif xml_data[:4] == '\x00\x3c\x00\x3f':
                # UTF-16BE
                sniffed_xml_encoding = 'utf-16be'
                xml_data = unicode(xml_data, 'utf-16be').encode('utf-8')
            elif (len(xml_data) >= 4) and (xml_data[:2] == '\xfe\xff') \
                     and (xml_data[2:4] != '\x00\x00'):
                # UTF-16BE with BOM
                sniffed_xml_encoding = 'utf-16be'
                xml_data = unicode(xml_data[2:], 'utf-16be').encode('utf-8')
            elif xml_data[:4] == '\x3c\x00\x3f\x00':
                # UTF-16LE
                sniffed_xml_encoding = 'utf-16le'
                xml_data = unicode(xml_data, 'utf-16le').encode('utf-8')
            elif (len(xml_data) >= 4) and (xml_data[:2] == '\xff\xfe') and \
                     (xml_data[2:4] != '\x00\x00'):
                # UTF-16LE with BOM
                sniffed_xml_encoding = 'utf-16le'
                xml_data = unicode(xml_data[2:], 'utf-16le').encode('utf-8')
            elif xml_data[:4] == '\x00\x00\x00\x3c':
                # UTF-32BE
                sniffed_xml_encoding = 'utf-32be'
                xml_data = unicode(xml_data, 'utf-32be').encode('utf-8')
            elif xml_data[:4] == '\x3c\x00\x00\x00':
                # UTF-32LE
                sniffed_xml_encoding = 'utf-32le'
                xml_data = unicode(xml_data, 'utf-32le').encode('utf-8')
            elif xml_data[:4] == '\x00\x00\xfe\xff':
                # UTF-32BE with BOM
                sniffed_xml_encoding = 'utf-32be'
                xml_data = unicode(xml_data[4:], 'utf-32be').encode('utf-8')
            elif xml_data[:4] == '\xff\xfe\x00\x00':
                # UTF-32LE with BOM
                sniffed_xml_encoding = 'utf-32le'
                xml_data = unicode(xml_data[4:], 'utf-32le').encode('utf-8')
            elif xml_data[:3] == '\xef\xbb\xbf':
                # UTF-8 with BOM
                sniffed_xml_encoding = 'utf-8'
                xml_data = unicode(xml_data[3:], 'utf-8').encode('utf-8')
            else:
                sniffed_xml_encoding = 'ascii'
                pass
            xml_encoding_match = re.compile \
                                 ('^<\?.*encoding=[\'"](.*?)[\'"].*\?>')\
                                 .match(xml_data)
        except:
            xml_encoding_match = None
        if xml_encoding_match:
            xml_encoding = xml_encoding_match.groups()[0].lower()
            if sniffed_xml_encoding and \
               (xml_encoding in ('iso-10646-ucs-2', 'ucs-2', 'csunicode',
                                 'iso-10646-ucs-4', 'ucs-4', 'csucs4',
                                 'utf-16', 'utf-32', 'utf_16', 'utf_32',
                                 'utf16', 'u16')):
                xml_encoding = sniffed_xml_encoding
        return xml_data, xml_encoding, sniffed_xml_encoding


    def find_codec(self, charset):
        return self._codec(self.CHARSET_ALIASES.get(charset, charset)) \
               or (charset and self._codec(charset.replace("-", ""))) \
               or (charset and self._codec(charset.replace("-", "_"))) \
               or charset

    def _codec(self, charset):
        if not charset: return charset 
        codec = None
        try:
            codecs.lookup(charset)
            codec = charset
        except LookupError:
            pass
        return codec

    EBCDIC_TO_ASCII_MAP = None
    def _ebcdic_to_ascii(self, s):
        c = self.__class__
        if not c.EBCDIC_TO_ASCII_MAP:
            emap = (0,1,2,3,156,9,134,127,151,141,142,11,12,13,14,15,
                    16,17,18,19,157,133,8,135,24,25,146,143,28,29,30,31,
                    128,129,130,131,132,10,23,27,136,137,138,139,140,5,6,7,
                    144,145,22,147,148,149,150,4,152,153,154,155,20,21,158,26,
                    32,160,161,162,163,164,165,166,167,168,91,46,60,40,43,33,
                    38,169,170,171,172,173,174,175,176,177,93,36,42,41,59,94,
                    45,47,178,179,180,181,182,183,184,185,124,44,37,95,62,63,
                    186,187,188,189,190,191,192,193,194,96,58,35,64,39,61,34,
                    195,97,98,99,100,101,102,103,104,105,196,197,198,199,200,
                    201,202,106,107,108,109,110,111,112,113,114,203,204,205,
                    206,207,208,209,126,115,116,117,118,119,120,121,122,210,
                    211,212,213,214,215,216,217,218,219,220,221,222,223,224,
                    225,226,227,228,229,230,231,123,65,66,67,68,69,70,71,72,
                    73,232,233,234,235,236,237,125,74,75,76,77,78,79,80,81,
                    82,238,239,240,241,242,243,92,159,83,84,85,86,87,88,89,
                    90,244,245,246,247,248,249,48,49,50,51,52,53,54,55,56,57,
                    250,251,252,253,254,255)
            import string
            c.EBCDIC_TO_ASCII_MAP = string.maketrans( \
            ''.join(map(chr, range(256))), ''.join(map(chr, emap)))
        return s.translate(c.EBCDIC_TO_ASCII_MAP)

    MS_CHARS = { '\x80' : '&euro;',
                 '\x81' : ' ',
                 '\x82' : '&sbquo;',
                 '\x83' : '&fnof;',
                 '\x84' : '&bdquo;',
                 '\x85' : '&hellip;',
                 '\x86' : '&dagger;',
                 '\x87' : '&Dagger;',
                 '\x88' : '&caret;',
                 '\x89' : '%',
                 '\x8A' : '&Scaron;',
                 '\x8B' : '&lt;',
                 '\x8C' : '&OElig;',
                 '\x8D' : '?',
                 '\x8E' : 'Z',
                 '\x8F' : '?',
                 '\x90' : '?',
                 '\x91' : '&lsquo;',
                 '\x92' : '&rsquo;',
                 '\x93' : '&ldquo;',
                 '\x94' : '&rdquo;',
                 '\x95' : '&bull;',
                 '\x96' : '&ndash;',
                 '\x97' : '&mdash;',
                 '\x98' : '&tilde;',
                 '\x99' : '&trade;',
                 '\x9a' : '&scaron;',
                 '\x9b' : '&gt;',
                 '\x9c' : '&oelig;',
                 '\x9d' : '?',
                 '\x9e' : 'z',
                 '\x9f' : '&Yuml;',}

#######################################################################


#By default, act as an HTML pretty-printer.
if __name__ == '__main__':
    import sys
    soup = BeautifulStoneSoup(sys.stdin.read())
    print soup.prettify()
