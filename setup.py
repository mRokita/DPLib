#!/usr/bin/env python
# DPLib - Asynchronous bot framework for Digital Paint: Paintball 2 servers
# Copyright (C) 2017  Michał Rokita
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from distutils.core import setup

setup(name='DPLib',
      version='1.5',
      description='Asynchronous bot framework for Digital Paint: Paintball 2 serversPython Distribution Utilities',
      author='Michał Rokita',
      author_email='mrokita@mrokita.pl',
      url='https://mrokita.github.io/DPLib/',
      packages=['dplib'],
      keywords=['digital', 'paint', 'paintball 2', 'jitspoe', 'dp2', 'DP:PB2'],
      download_url = 'https://github.com/mRokita/DPLib/tarball/1.5',
      classifiers=[
            'Programming Language :: Python :: 3',
            'Intended Audience :: Developers',
            'Topic :: Utilities',
      ]
     )