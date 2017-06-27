from dplib.server import Server

s = Server(hostname='127.0.0.1', port=27910, logfile=r'C:\Games\Paintball2\pball\qconsole27910.log', rcon_password='hello')

@s.event
def on_chat(nick, message):
    if message == '!map elim':
        maps = ['beta/wobluda_fix', 'beta/daylight_b1', 'airtime']
        s.say('{C}AType \'!elim <mapname>\' to eliminate a map.')
        while len(maps) > 1:
            s.say('{C}9Available maps: ' + ', '.join(maps))
            msg = yield from s.wait_for_message(check=lambda n, m: m.startswith('!elim '))
            mapname = msg['message'].split('!elim ')[1]
            if mapname not in maps:
                s.say('{C}9Invalid map.')
                s.say('{C}9Available maps: ' + ', '.join(maps))
            else:
                maps.remove(mapname)
        s.rcon('map '+maps[0])

s.run()