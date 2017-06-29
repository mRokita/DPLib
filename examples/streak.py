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

import asyncio

from dplib.server import Server

s = Server(hostname='127.0.0.1', port=27910, logfile=r'C:\Games\Paintball2\pball\qconsole27910.log', rcon_password='hello')


@asyncio.coroutine
def streak(killer_nick):
    for i in range(1, 3):
        print(killer_nick, i)
        yield from s.wait_for_elim(killer_nick=killer_nick)


@s.event
def on_elim(killer_nick, killer_weapon, victim_nick, victim_weapon):
    try:
        yield from asyncio.wait_for(streak(killer_nick), timeout=20)
        s.say('{U}%s ZABUJCA!{U}' % killer_nick)
    except asyncio.TimeoutError:
        print('Timeout for '+ killer_nick)

s.run()