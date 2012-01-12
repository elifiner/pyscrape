#!/usr/bin/env python
# Copyright (C) 2011 Eli Golovinsky <eli.golovinsky@gmail.com>.
#
# This file is part of Pyscrape.
#
# Pyscrape is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3, or (at your option) any later
# version.
#
# Pyscrape is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public
# License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Pyscrape.  If not, see <http://www.gnu.org/licenses/>.

from distutils.core import setup

DESCRIPTION = """
Automate and scrape web sites using a friendly pythonic interface. Relies heavily 
on BeautifulSoup and provides an abstration layer on top of urllib2. Runs equally
well using urllib2 and on Google App Engine using Google's urlfetch API.
"""

setup(
    name='pyscrape',
    version='0.1.1',
    description='A pythonic web scraping library.',
    long_description=DESCRIPTION,
    author='Eli Golovinsky',
    license='MIT',
    author_email='eli.golovinsky@gmail.com',
    url='https://github.com/gooli/pyscrape',
    package_dir={'pyscrape':'.'},
    packages=['pyscrape'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP'
    ],
    install_requires=["BeautifulSoup>=3.2.0"],
)

