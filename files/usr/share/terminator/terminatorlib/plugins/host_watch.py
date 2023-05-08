#!/usr/bin/python
#
# HostWatch Terminator Plugin
# Copyright (C) 2015 GratefulTony & Philipp C. Heckel & Niklas Reisser
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import re
from collections import OrderedDict

import gi
from gi.repository import GObject, Vte

import terminatorlib.plugin as plugin
from terminatorlib.util import dbg
from terminatorlib.terminator import Terminator
from terminatorlib.terminal import Terminal
from terminatorlib.config import Config


# Every plugin you want Terminator to load *must* be listed in 'AVAILABLE'
# This is inside this try so we only make the plugin available if pynotify
#  is present on this computer.
AVAILABLE = ['HostWatch']

class HostWatch(plugin.Plugin):
    config : dict
    last_profiles : dict
    patterns : list
    profile_mappings : OrderedDict
    prompt_minlen : int
    watches : set
    fallback_profile = 'default'
    capabilities = ['host_watch']

    def __init__(self):
        dbg("loading HostWatch")
        self.config = Config().plugin_get_config(self.__class__.__name__)
        self.last_profiles = {}
        self.patterns = []
        self.profile_mappings = OrderedDict()
        self.prompt_minlen = int(self.get_prompt_minlen())
        self.watches = set()
        self.fallback_profile = self.get_fallback()
        self.load_patterns()
        self.load_profile_mappings()
        self.update_watches()


    def update_watches(self) -> None:
        """ (re)register for signals """
        new_watches = set()
        for terminal in Terminator().terminals:
            new_watches.add(terminal)
            if terminal not in self.watches:
                vte = terminal.get_vte()
                terminal.connect('focus-out', self.update_watches_delayed, None)
                vte.connect('focus-out-event', self.update_watches_delayed, None)
                vte.connect('contents-changed', self.on_contents_changed, terminal)
        self.watches = new_watches


    def update_watches_delayed(self, term, event, arg1 = None) -> bool:
        """ (re)register for signals, but later"""
        def add_watch(self):
            self.update_watches()
            return False
        GObject.idle_add(add_watch, self)
        return True


    def get_hostname(self, last_lines: str) -> str|None:
        """Check if a hostname is found in the last lines"""
        for prompt_pattern in self.patterns:
            match = prompt_pattern.match(last_lines)

            if not match:
              continue

            hostname = match.group(1)
            dbg(f"match search pattern : {prompt_pattern.pattern} ({last_lines}) -> {hostname}")
            return hostname
        return None


    def get_most_approbriate_profile(self, hostname: str) -> str:
        """Get a profile for a hostname"""
        # since dict is ordered, iterate regexp/mapping, then profiles
        for profile_pattern, profile in self.profile_mappings.items():
            # we create a pattern based on profile name
            if hostname == profile or profile_pattern.match(hostname):
                dbg(f"matching profile '{profile}' found for {hostname}:")
                return profile
        return self.fallback_profile


    def apply_profile(self, terminal : Terminal, profile: str) -> None:
        """Set a given profile"""
        # avoid re-applying profile if no change
        if terminal not in self.last_profiles or profile != self.last_profiles[terminal]:
            dbg(f"setting profile {profile}")
            terminal.set_profile(None, profile, False)
            self.last_profiles[terminal] = profile


    def on_contents_changed(self, vte : Vte, terminal : Terminal) -> bool:
        """ Called when the visible content in the terminal changes (which is often)"""
        self.update_watches()

        # Manage text wrapping and multiline prompts:
        # usecases :
        # - PS1 too long
        # - Component of PS1 forcing display on several lines (e.g working directory)
        # - Window resizing
        # - Multiline prompts
        # If current line too short, we assume prompt is wrapped
        # In this case, we add the previous line to the search an try again.
        # We repeat this for up to 10 lines, to make sure we never slow down the terminal
        for count in range(0,9):
            hostname = None
            profile = None
            last_lines = self.get_last_lines(vte, count)
            if last_lines:
                hostname = self.get_hostname(last_lines)
            if hostname:
                profile = self.get_most_approbriate_profile(hostname)
            if profile:
                self.apply_profile(terminal, profile)
                break
        return True


    def get_last_lines(self, vte : Vte, count):
        """Retrieve the last n lines of terminal output (contains 'user@hostname')"""
        cursor = vte.get_cursor_position()
        column_count = vte.get_column_count()
        row_position = cursor[1]

        start_row = row_position - count
        start_col = 0
        end_row = row_position
        end_col = column_count

        if start_row < 0:
            return None

        lines = vte.get_text_range(start_row, start_col, end_row, end_col, None)[0]

        if not lines or len(lines) < self.prompt_minlen:
            dbg(f"line below prompt min size of {self.prompt_minlen} chars")
            return None

        return lines


    def load_patterns(self) -> None:
        "Load pattern to match hostname or set default"
        if self.config and 'patterns' in self.config:
            if isinstance(self.config['patterns'], list):
                for pat in self.config['patterns']:
                    self.patterns.append(re.compile(pat))
            else:
                self.patterns.append(re.compile(self.config['patterns']))
        else:
            self.patterns.append(re.compile(r"[^@]+@([-\w]+)[^$#]*[$#]"))


    def get_prompt_minlen(self):
        """ minimal prompt length, below this value, we search for PS1 on previous line """
        if self.config and 'prompt_minlen' in self.config:
            return self.config['prompt_minlen']
        return 3


    def get_fallback(self):
        """ fallback profile, applies if profile not found. """
        if self.config and 'failback_profile' in self.config:
            return self.config['failback_profile']
        return 'default'


    def load_profile_mappings(self):
        """ get profile mapping as declared with profile_patterns config key
        and append profile names as patterns
        profiles are saved as compiled patterns in an ordered dictionary
        so patterns mappings are parsed prior to profiles
        """
        if self.config and 'profile_patterns' in self.config:
            # we have to parse and create dict since configuration doesnt allow this
            for pre in self.config['profile_patterns']:
                kv = pre.split(":")
                if len(kv) == 2:
                    # config recovered as ugly string with leading and trailing quotes removed, must remove ' and "
                    pattern = kv[0].replace("'", "").replace('"', '')
                    profile = kv[1].replace("'", "").replace('"', '')
                    dbg(f"Adding profile {profile} for pattern {pattern}")
                    self.profile_mappings[re.compile(pattern)] = profile

        # we load profile name as plain regex
        for profile in Terminator().config.list_profiles():
            dbg(f"Adding profile {profile} for literal matching")
            self.profile_mappings[re.compile(profile)] = profile
