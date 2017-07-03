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

from dplib.server import Server

s = Server(hostname='127.0.0.1', port=27910, logfile=r'C:\Games\Paintball2\pball\qconsole27910.log', rcon_password='hello')


@s.event
def on_chat(nick, message):
    print('Chat message. Nick: {0}, Message: {1}'.format(nick, message))


@s.event
def on_team_switched(nick, old_team, new_team):
    print('Team switched. Nick: {0}, Old team: {1}, New team: {2}'.format(nick, old_team, new_team))


@s.event
def on_round_started():
    print('Round started...')


@s.event
def on_elim(killer_nick, killer_weapon, victim_nick, victim_weapon):
    print('Elimination. Killer\'s nick: {0}, Killer\'s weapon: {1}, Victim\'s nick: {2}, Victim\'s weapon: {3}'
        .format(
        killer_nick, killer_weapon, victim_nick, victim_weapon
    ))


@s.event
def on_respawn(team, nick):
    print('Respawn. Nick: {0}, Team: {1}'.format(nick, team))


@s.event
def on_entrance(nick, build, addr):
    print('Entrance. Nick: {0}, Build: {1}, Address: {2}'.format(
        nick, build, addr
    ))


@s.event
def on_elim_teams_flag(team, nick, points):
    print('Points for posession of eliminated teams flag. Team: {0}, Nick: {1}, Points: {2}'.format(
        team, nick, points
    ))


@s.event
def on_flag_captured(team, nick, flag):
    print('Flag captured. Team: {0}, Nick: {1}, Flag: {2}'.format(team, nick, flag))

@s.event
def on_game_end(score_blue, score_red, score_yellow, score_purple):
    print('Game ended. Blue:{} Red:{} Yellow:{} Purple:{}'.format(
        score_blue, score_red, score_yellow, score_purple
    ))

print(s.get_status())
s.run()