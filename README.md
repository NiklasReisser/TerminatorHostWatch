# Terminator HostWatch Plugin
This plugin monitors the last line (PS1) of each terminator terminal, and applies a host-specific profile if the hostname is changed.

## How it works

### Prompt matching
The plugin simply parses the PS1-evaluated last line and matches it against a regex "[^@]+@(\w+)" ((e.g. user@host) to find hostname.

### Profile matching
Once an hostname is found, the plugin tries to match it against the profiles.

Profiles might be :
 - plain hostnames
 - or regex

The configuration allow to create matching rules for hostname pattern against profile.

### Prompt wrapping
PS1 might be displayed in more than one line, for instance if :
- very long path, wrapping over several lines
- terminal window too small
- PS1 set up for 2 lines

E.g. :
- geeky and informational PS1 :
[user@host very/long/path] /dev/pts/42
$

- unusually long PS1 due to full path display :
[user@host a/very/very/long/and/annoying/psychopathic/library/of/whatever/appl
lication/path/that/wraps]$

We search the first line of PS1 by searching back in
terminal history from current cursor position. If its not on the last line, we
add one more until we find the expected 'user@host' pattern or tried for 10 lines.
This is fairly robust, but also reacts to user@host simply typed on the terminal.

To avoid unecessary treatment, a minimal prompt length might be set.

Profile name is a plain name (the hostname), or a regexp.
The plugin checks for exact match between hostname and profile, or profile
pattern and hostname.
![Profiles](assets/terminator-hostwatch.png)

## Installation
Put the `host_watch.py` in `/usr/share/terminator/terminatorlib/plugins/` or `~/.config/terminator/plugins/`. This can be done using `install.sh`, which if run using sudo will default to installation at `/usr/share/terminator/terminatorlib/plugins/` or if run as user, will install to `~/.config/terminator/plugins/`.

Minimal configuration : create a profile in Terminator to match your hostname. If you have a server that displays `user@myserver ~ $`, for instance, create a profile called `myserver`.

Profiles names/regexp are evaluated in a non-predictable order, so be careful with your regexp and be as specific and restrictive as possible.


## Configuration
Plugins section in `.config/terminator/config` :
```
[plugins]
  [[HostWatch]]
    ...
```

### Configuration keys
Plugin section in .config/terminator/config :
[plugins]
  [[HostWatch]]
    # Matches PS1. The first regex group is treated as the hostname and used to match the
    # profile name or the profile_patterns.
    patterns = [^@]+@([-\d\w]+)

    # Matches a hostname regex to a Terminator profile, format: <pattern>:<profile>,...
    profile_patterns = ([\w\d]+-mysql-prd-\d+|swift-prod-\d+):prod

Configuration keys :
- prompt patterns : for prompt matching
  key : patterns
  value : a regex list. Default if not set : "[^@]+@([-\w]+)[^$#]*[$#]" (e.g. user@host$)
  E.g :
  patterns = "[^@]+@(\w+):([^#]+)#", "[^@]+@(\w+) .+ \$"

- profile patterns : searches profile against hostname pattern
  key : profile_patterns
  value : dict-like list, pattern:profile. Default if not set : None
  E.g :
  profile_patterns = "jenkins":"inf","^itg-*":"itg","^ip-10-1-*":"itg",
  "^ns[0-9]+":"ovh","^sd-[0-9]+":"ovh","aramis":"local"

  profiles are search in order, by profile patterns, then by profile name
  (that can also be a pattern, so be carefull with mixed-up config)

- minimal prompt length : triggers backward search (see wrapping above)
  Adapt this to your usual prompt length. If PS1 is a two lines prompt (see
  above), might be 2 chars (prompt char+space).
  key : prompt_minlen
  value : an int. Default if not set : 3

- failback profile : profile if no matching pattern/profile found
  key : failback_profile
  value : a string. Default if not set : 'default'

## Development
Development resources for the Python Terminator class and the 'libvte' Python
bindings can be found here:

For terminal.* methods, see:
  - http://bazaar.launchpad.net/~gnome-terminator/terminator/trunk/view/head:/terminatorlib/terminal.py
  - and: apt-get install libvte-dev; less /usr/include/vte-0.0/vte/vte.h

For terminal.get_vte().* methods, see:
  - https://lazka.github.io/pgi-docs/Vte-2.91/classes/Terminal.html
  - and: apt-get install libvte-dev; less /usr/share/pygtk/2.0/defs/vte.defs

## Debugging
To debug the plugin, start Terminator from another terminal emulator
like this:

    $ terminator --debug-classes=HostWatch

That should give you output like this:

    HostWatch::check_host: switching to profile EMEA0014, because line 'pheckel@EMEA0014 ~ $ ' matches pattern '[^@]+@(\w+)'
    HostWatch::check_host: switching to profile kartoffel, because line 'root@kartoffel:~# ' matches pattern '[^@]+@(\w+)'
    ...

## Authors
The plugin was developed by GratefulTony (https://github.com/GratefulTony/TerminatorHostWatch),
and extended by Philipp C. Heckel (https://github.com/binwiederhier/TerminatorHostWatch),
and reworked by Niklas Reisser (https://github.com/NiklasReisser/TerminatorHostWatch).

## License
The plugin is licensed as GPLv2 only.
