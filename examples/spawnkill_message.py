from dplib.server import Server

s = Server(hostname='127.0.0.1', port=27910, logfile=r'C:\Games\Paintball2\pball\qconsole27910.log', rcon_password='hello')

@s.event
def on_respawn(team, nick):
    kill = yield from s.wait_for_elim(victim_nick=nick, timeout=2)
    if kill:
        print(s.get_ingame_info(kill['killer_nick']).dplogin)
        s.say('{C}9%s, {C}A{U}STOP SPAWNKILLING{U}' % kill['killer_nick'])

s.run()