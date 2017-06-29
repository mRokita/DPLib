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

"""
DPLogin - a module for managing DPLogin accounts.
"""
from hashlib import md5
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor
import re
from http.cookiejar import Cookie, CookieJar

PATTERN_USER_ID = re.compile("User ID: (\d+)")
PATTERN_CLANS = re.compile("/index.php\\?action=viewclan&clanid=(\d+)\\\">"
                           "(.*?) \\- (.*?)</a>")
PATTERN_PROFILE_DATA = re.compile("name=\\\"(.*?)\\\" .*?value=\\\"(.*?)\\\"")
PATTERN_PROFILE_BIO = re.compile("name=\\\"(bio)\\\" wrap=soft>"
                                 "(.*?)</textarea>", re.DOTALL)
PATTERN_MEMBERS = re.compile("(?:<b class=\\\"faqtitle\\\">"
                             "(Leaders|Former Members|Invited Players Pending"
                             "|Players Requesting Membership):"
                             "</b></td></tr>)?<tr><td><a href=\\\"/index\\.php"
                             "\\?action=viewmember&playerid=(\d+)\\\""
                             ">([^<>]+)</a></td><td>.*?</td></tr>")


def get_session_hash(pwhash, session_id):
    """
    Hash password again, use session_id as a seed.
    Used at log in when no plaintext password is specified
    :param pwhash:
    :param session_id:

    :return: Session hash
    :rtype str:
    """
    return hex_md5(pwhash+session_id)


def get_password_hash(password, user_id, session_id):
    """
    Hash plain password a few times.
    Used at log in when a plaintext password is specified.
    :param password:
    :param user_id:
    :param session_id:

    :return: Hashed password
    :rtype: str
    """
    return hex_md5(hex_md5(hex_md5(password + "DPLogin001") + user_id) +
                   session_id)


def get_new_password_hash(password, user_id):
    """
    Hash the password at password change.

    :param password:
    :param user_id:

    :return: Hashed password and user id
    :rtype: str
    """
    return hex_md5(hex_md5(password + "DPLogin001") + user_id)


def hex_md5(string):
    """
    Hash a string using md5

    :param string: String to hash

    :return: MD5 hash of string
    :rtype: str
    """
    return md5(string.encode('utf-8')).hexdigest()


class DPLogin:
    """
    A class that represents a  DPLogin session.

    :param username:
    :param password:
    :param pw_hash:
    :param pw_session_hash:
    :param session_id:
    :raises TypeError: Wrong password or hash
    """

    def __init__(self, username=None, password=None, pw_hash=None,
                 pw_session_hash=None, session_id=None):
        if not ((username and password) or session_id):
            raise TypeError("not enough parameters")
        self.__cj = CookieJar()
        self.__opener = build_opener(
            HTTPCookieProcessor(self.__cj))
        self.__opener.addheaders = [
            ('User-Agent',
             'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:46.0) Gecko/20100102'
             ' Firefox/46.0)')
        ]
        self.username = username
        self.password = password
        self.pw_hash = pw_hash
        self.pw_session_hash = pw_session_hash
        self.session_id = None
        if not username and not (password or pw_hash or
                                 pw_session_hash) and session_id:
            self.set_sessid(session_id)
            return

        response = self.__opener.open("http://dplogin.com/index.php",
                                      data=urlencode({"action": "weblogin1",
                                                      "username": username,
                                                      "pwhash": ""}).encode('utf-8')).read().decode('utf-8')
        try:
            self.user_id = PATTERN_USER_ID.findall(response)[0]
        except IndexError:
            raise TypeError("User {} doesn't exist.".format(username))

        self.session_id = None
        if not session_id:
            for cookie in self.__cj:
                if cookie.name == "PHPSESSID":
                    self.set_sessid(cookie.value)
        else:
            self.set_sessid(session_id)
        pwhash = None
        if password:
            pwhash = get_password_hash(password, self.user_id, self.session_id)
        elif pw_hash:
            pwhash = get_session_hash(pw_hash, session_id=session_id)
        elif pw_session_hash:
            pwhash = pw_session_hash
        response = self.__opener.open("http://dplogin.com/index.php",
                                      data=urlencode({"action": "weblogin2",
                                                      "username": username,
                                                      "pwhash": pwhash,
                                                      "password": ""}).encode('utf-8')).read().decode('utf-8')
        if "Invalid password" in response:
            raise TypeError("Wrong password.")

    def set_sessid(self, session_id):
        """
        Set session id to session_id.
        Used to "fake" session_id, pretty useful for hijacking ;)

        :param session_id: session id to set

        :return: None
        :rtype: NoneType
        """
        self.session_id = session_id
        self.__cj.set_cookie(Cookie(name="PHPSESSID", value=session_id,
                                    port=None, port_specified=False,
                                    domain='dplogin.com',
                                    domain_specified=False,
                                    domain_initial_dot=False, path='/',
                                    secure=False, expires=None, discard=True,
                                    comment=None, rest={'HttpOnly': None},
                                    rfc2109=False, comment_url=None,
                                    path_specified=False, version=0))

    def get_clans(self):
        """
        Get clans of the user.

        :return: A list of dicts with clan info
        :rtype: list
        """
        response = self.__opener.open("http://dplogin.com/index.php?"
                                      "action=main").read().decode('utf-8')
        data = PATTERN_CLANS.findall(response)
        has_active_clan = len(data) and ">Active Clan<" in response
        clans = []
        i = 0
        for clan in data:
            clans.append({"id": clan[0],
                          "name": clan[1],
                          "tag": [2],
                          "active": has_active_clan and not i})
            if not i:
                i = 1
        return clans

    def leave_current_clan(self):
        """
        Leave the current clan.

        :return: HTTP Response
        :rtype: str
        """
        for clan in self.get_clans():
            if clan["active"]:
                return self.leave_clan(clan["id"])

    def leave_clan(self, clan_id):
        """
        Leave clan with clan_id.
        :param clan_id: id of the clan to leave

        :return: HTTP Response
        :rtype: str
        """
        return self.__opener.open("http://dplogin.com/index.php?"
                                  "action=leaveclan&clanid={}"
                                  .format(clan_id)).read().decode('utf-8')

    def join_clan(self, clan_id=None, clan_name=None):
        """
        Join a clan.

        :param clan_id: id of a clan
        :param clan_name: name of a clan

        :return: HTTP Response
        :rtype: str
        """
        if not (clan_id or clan_name):
            raise TypeError("Not enough parameters")
        if clan_id:
            return self.__opener.open("http://dplogin.com/index.php?action="
                                      "joinclan&clanid={}".
                                      format(clan_id)).read().decode('utf-8')
        else:
            return self.__opener.open("http://dplogin.com/index.php",
                                      urlencode(
                                          {"action": "joinclan",
                                           "clanname": "clan_name"}).encode('utf-8')).read().decode('utf-8')

    def get_profile_data(self):
        """
        Get profile data.

        :return: dict({"field": "value"})
        :rtype: dict
        """
        response = self.__opener.open("http://dplogin.com/index.php?"
                                      "action=editprofile").read().decode('utf-8')
        data = PATTERN_PROFILE_DATA.findall(response)
        data.extend(PATTERN_PROFILE_BIO.findall(response))
        return dict([tuple(i) for i in data])

    def update_profile(self, newpassword=None, email=None, realname=None,
                       birthdate=None, location=None,
                       displayemail=None, forumname=None, aim=None, icq=None,
                       msn=None, yim=None, website=None, bio=None):
        """
        Update DPLogin profile.

        :param newpassword:
        :param email:
        :param realname:
        :param birthdate:
        :param location:
        :param displayemail:
        :param forumname:
        :param aim:
        :param icq:
        :param msn:
        :param yim:
        :param website:
        :param bio:

        :return: HTTP response
        :rtype: str
        """
        form_data = self.get_profile_data()
        if self.password:
            form_data["pwhash"] = get_password_hash(self.password,
                                                    self.user_id,
                                                    self.session_id)
        elif self.pw_hash:
            form_data["pwhash"] = get_session_hash(self.pw_hash,
                                                   self.session_id)
        elif self.pw_session_hash:
            form_data["pwhash"] = self.pw_session_hash
        else:
            raise TypeError("A hash/password is required to use this function")
        form_data["password"] = ""
        l = locals().copy()
        del l["form_data"]
        del l["self"]
        for var in l:
            if l[var]:
                form_data[var] = l[var]
        if newpassword:
            form_data["newpwhash"] = get_new_password_hash(newpassword,
                                                           self.user_id)
        form_data["newpassword"] = ""
        form_data["newpassword2"] = ""
        return self.__opener.open("http://dplogin.com/index.php",
                                  urlencode(form_data).encode('utf-8')).read().decode('utf-8')

    def del_name(self, name):
        """
        Delete a name from the account.

        :param name: name to be deleted

        :return: HTTP response
        :rtype: str
        """
        return self.__opener.open("http://dplogin.com/index.php?"
                                  "action=deletemyname&name={}"
                                  .format(name)).read().decode('utf-8')

    def add_name(self, name):
        """
        Add a name to the account.

        :param name: name to be deleted

        :return: HTTP response
        :rtype: str
        """
        return self.__opener.open("http://dplogin.com/index.php",
                                  urlencode({"action": "addnewname",
                                             "newname": name}).encode('utf-8')).read().decode('utf-8')

    def create_clan(self, name, tag):
        """
        Create a new clan.

        :param name: Name of the new clan
        :param tag: Tag of the new clan

        :return: HTTP response
        :rtype: str
        """
        return self.__opener.open("http://dplogin.com/index.php",
                                  urlencode({"action": "createclan2",
                                             "clanname": name,
                                             "clantag": tag}).encode('utf-8')).read().decode('utf-8')

    def invite_member(self, clanid, playerid=None, name=None):
        """
        Invite a member to a clan.

        :param clanid: id of the clan
        :param playerid: id of the player to invite
        :param name: name of the player to invite

        :return: HTTP response
        :rtype: str
        """
        if not (clanid or playerid):
            raise TypeError("Not enough parameters")
        if name:
            return self.__opener.open("http://dplogin.com/index.php",
                                      urlencode({"action": "inviteclanmember",
                                                 "clanid": clanid,
                                                 "playername": name}).encode('utf-8')).read().decode('utf-8')
        else:
            return self.__opener.open("http://dplogin.com/index.php?"
                                      "action=inviteclanmember"
                                      "&clanid={}&playerid={}"
                                      .format(clanid, playerid)).read()

    def cancel_join_request(self, clanid):
        """
        Cancel a clan join request.

        :param clanid: id of a clan

        :return: HTTP response
        :rtype: str
        """
        return self.__opener.open("http://dplogin.com/index.php?"
                                  "action=cancelclanjoinrequest&clanid={}"
                                  .format(clanid)).read().decode('utf-8')

    def reject_join_request(self, clanid, playerid):
        """
        Reject a clan join request.

        :param clanid: id of a clan
        :param playerid: id of a player

        :return: HTTP response
        :rtype: str
        """
        return self.__opener.open("http://dplogin.com/index.php?"
                                  "action=rejectclanjoinrequest"
                                  "&clanid={}&playerid={}"
                                  .format(clanid, playerid)).read().decode('utf-8')

    def make_leader(self, clanid, playerid):
        """
        Make player with id of playerid a leader of a clan with clanid.

        :param clanid: id of a clan
        :param playerid: id of a player

        :return: HTTP response
        :rtype: str
        """
        return self.__opener.open("http://dplogin.com/index.php?action="
                                  "makeclanleader&clanid={}&playerid={}"
                                  .format(clanid, playerid)).read().decode('utf-8')

    def kick_from_clan(self, clanid, playerid):
        """
        Kick a player with id of playerid from a clan with id of clanid.

        :param clanid: id of a clan
        :param playerid: id of a player

        :return: HTTP response
        :rtype: str
        """
        return self.__opener.open("http://dplogin.com/index.php?"
                                  "action=kickclanmember"
                                  "&clanid={}&playerid={}"
                                  .format(clanid, playerid)).read().decode('utf-8')

    def remove_clan_leader(self, clanid, playerid):
        """
        Remove a leader with id of playerid from a clan with id of clanid.

        :param clanid: id of a clan
        :param playerid: id of a player

        :return: HTTP response
        :rtype: str
        """
        return self.__opener.open("http://dplogin.com/index.php?"
                                  "action=removeclanleader"
                                  "&clanid={}&playerid={}"
                                  .format(clanid, playerid)).read().decode('utf-8')

    def cancel_invite(self, clanid, playerid):
        """
        Cancel invite to clan for some player.

        :param clanid: id of a clan
        :param playerid: id of a player

        :return: HTTP response
        :rtype: str
        """
        return self.__opener.open("http://dplogin.com/index.php?"
                                  "action=cancelinviteclanmember"
                                  "&clanid={}&playerid={}"
                                  .format(clanid, playerid)).read().decode('utf-8')

    def get_clan_members(self, clanid):
        """
        Get members of a clan with id of clanid.

        :param clanid: id of the clan

        :return: A list of dict objects with ids, names and ranks.
        :rtype: list
        """
        data = PATTERN_MEMBERS.findall(
            self.__opener.open("http://dplogin.com/index.php"
                               "?action=viewclan&clanid={}"
                               .format(clanid)).read().decode('utf-8'))
        members = {}
        current_key = ""
        for member in data:
            if member[0]:
                current_key = member[0]
                members[current_key] = list()
            members[current_key].append({"id": member[1],
                                         "name": member[2],
                                         "rank": current_key})
        return members