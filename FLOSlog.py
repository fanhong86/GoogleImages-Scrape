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

"""

import logging

__author__ = "Florian Schroff <schroff@robots.ox.ac.uk>"
__version__ = "Version 0.1"
__date__ = "2007"
__copyright__ = "Copyright (c) 2007. All Rights Reserved."

class myLog(object):
    """Encapsulates the logging functionality provided by the 'logging' module."""
    def _logDebug    (self,message): logging.getLogger(self.__class__.__name__).debug    (message)
    def _logInfo     (self,message): logging.getLogger(self.__class__.__name__).info     (message)
    def _logWarning  (self,message): logging.getLogger(self.__class__.__name__).warning  (message)
    def _logError    (self,message): logging.getLogger(self.__class__.__name__).error    (message)
    def _logCritical (self,message): logging.getLogger(self.__class__.__name__).critical (message)
    def _logException(self,message): logging.getLogger(self.__class__.__name__).exception(message)

    def __init__(self):
        # Set up the default log:
        # Attach a handler to this log:
        handler_stdout = logging.StreamHandler()
        handler_stdout.setLevel(logging.INFO)  # By default, only display informative messages and fatal errors.
        handler_stdout.setFormatter(logging.Formatter('%(message)s'))
        #handler_stdout.setFormatter(logging.Formatter('%(name)s: %(message)s'))  # Change format of messages.
        logging.getLogger().addHandler(handler_stdout)
        logging.getLogger().setLevel(logging.DEBUG)

    def debugFile(filename):
        # log everything to a file:
        handler = logging.FileHandler(filename) # Log to a file.
        handler.setLevel(logging.DEBUG)  # And switch to DEBUG view (=view all messages)
        handler.setFormatter(logging.Formatter('%(name)s: %(message)s'))
        logging.getLogger().addHandler(handler) 
