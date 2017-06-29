from dplib.server import Server

s = Server(hostname='127.0.0.1', port=27910, logfile=r'C:\Games\Paintball2\pball\qconsole27910.log', rcon_password='hello')


@s.event
def on_team_switched(nick, old_team, new_team):
    print('Team switched. Nick: {0}, Old team: {1}, New team: {2}'.format(nick, old_team, new_team))


@s.event
def on_round_started():
    e = yield from s.wait_for_entrance(nick='mRokita')
    print(e)
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


s.run()