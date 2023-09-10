#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nrrdmark
Version:  0.0.2
Author:   Sean O'Connell <sean@sdoconnell.net>
License:  MIT
Homepage: https://github.com/sdoconnell/nrrdmark
About:
A terminal-based bookmark management tool with local file-based storage.

usage: nrrdmark [-h] [-c <file>] for more help: nrrdmark <command> -h ...

Terminal-based bookmark management for nerds.

commands:
  (for more help: nrrdmark <command> -h)
    archive             archive a bookmark
    delete (rm)         delete a bookmark file
    edit                edit a bookmark file (uses $EDITOR)
    info                show info about a bookmark
    list (ls)           list bookmarks
    modify (mod)        modify a bookmark
    new                 create a new bookmark
    open                open a bookmark
    query               search bookmarks with structured text output
    search              search bookmarks
    shell               interactive shell
    unset               clear a field from a specified bookmark
    version             show version info

optional arguments:
  -h, --help            show this help message and exit
  -c <file>, --config <file>
                        config file


Copyright © 2021 Sean O'Connell

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""
import argparse
import configparser
import json
import os
import random
import shutil
import string
import subprocess
import sys
import uuid
import webbrowser
from cmd import Cmd
from datetime import datetime

import requests
import tzlocal
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from rich import box
from rich.color import ColorParseError
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.style import Style
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

APP_NAME = "nrrdmark"
APP_VERS = "0.0.2"
APP_COPYRIGHT = "Copyright © 2021 Sean O'Connell."
APP_LICENSE = "Released under MIT license."
DEFAULT_DATA_DIR = f"$HOME/.local/share/{APP_NAME}"
DEFAULT_CONFIG_FILE = f"$HOME/.config/{APP_NAME}/config"
DEFAULT_CONFIG = (
    "[main]\n"
    f"data_dir = {DEFAULT_DATA_DIR}\n"
    "# browser command used to open bookmarks (default is the\n"
    "# system default browser. The command should include a %u\n"
    "# placeholder for the url to open.\n"
    "#browser_cmd = firefox --new-tab %u &\n"
    "# always open bookmarks in a new window.\n"
    "# default is to open in a new tab, if possible.\n"
    "# note: this overridden by browser_cmd.\n"
    "#always_new_window = false\n"
    "\n"
    "[colors]\n"
    "disable_colors = false\n"
    "disable_bold = false\n"
    "# set to 'true' if your terminal pager supports color\n"
    "# output and you would like color output when using\n"
    "# the '--pager' ('-p') option\n"
    "color_pager = false\n"
    "# custom colors\n"
    "#alias = bright_black\n"
    "#table_title = blue\n"
    "#bookmark_title = green\n"
    "#url = yellow\n"
    "#description = default\n"
    "#tags = cyan\n"
    "#label = white\n"
)


class Bookmarks():
    """Performs bookmark operations.

    Attributes:
        config_file (str):  application config file.
        data_dir (str):     directory containing bookmark files.
        dflt_config (str):  the default config if none is present.

    """
    def __init__(
            self,
            config_file,
            data_dir,
            dflt_config):
        """Initializes a Bookmarks() object."""
        self.config_file = config_file
        self.data_dir = data_dir
        self.config_dir = os.path.dirname(self.config_file)
        self.dflt_config = dflt_config
        self.interactive = False

        # default colors
        self.color_table_title = "bright_blue"
        self.color_bookmark_title = "green"
        self.color_url = "yellow"
        self.color_description = "default"
        self.color_alias = "bright_black"
        self.color_tags = "cyan"
        self.color_label = "white"
        self.color_bold = True
        self.color_pager = False

        # editor (required for some functions)
        self.editor = os.environ.get("EDITOR")

        # defaults
        self.ltz = tzlocal.get_localzone()
        self.all_tags = None
        self.always_new_window = False
        self.browser_cmd = None

        # initial style definitions, these are updated after the config
        # file is parsed for custom colors
        self.style_table_title = None
        self.style_bookmark_title = None
        self.style_url = None
        self.style_description = None
        self.style_alias = None
        self.style_tags = None
        self.style_label = None

        self._default_config()
        self._parse_config()
        self._verify_data_dir()
        self._parse_files()

    def _alias_not_found(self, alias):
        """Report an invalid alias and exit or pass appropriately.

        Args:
            alias (str):    the invalid alias.

        """
        self._handle_error(f"Alias '{alias}' not found")

    def _datetime_or_none(self, timestr):
        """Verify a datetime object or a datetime string in ISO format
        and return a datetime object or None.

        Args:
            timestr (str): a datetime formatted string.

        Returns:
            timeobj (datetime): a valid datetime object or None.

        """
        if isinstance(timestr, datetime):
            timeobj = timestr.astimezone(tz=self.ltz)
        else:
            try:
                timeobj = dtparser.parse(timestr).astimezone(tz=self.ltz)
            except (TypeError, ValueError, dtparser.ParserError):
                timeobj = None
        return timeobj

    def _default_config(self):
        """Create a default configuration directory and file if they
        do not already exist.
        """
        if not os.path.exists(self.config_file):
            try:
                os.makedirs(self.config_dir, exist_ok=True)
                with open(self.config_file, "w",
                          encoding="utf-8") as config_file:
                    config_file.write(self.dflt_config)
            except IOError:
                self._error_exit(
                    "Config file doesn't exist "
                    "and can't be created.")

    @staticmethod
    def _error_exit(errormsg):
        """Print an error message and exit with a status of 1

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')
        sys.exit(1)

    @staticmethod
    def _error_pass(errormsg):
        """Print an error message but don't exit.

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')

    def _format_bookmark(self, bookmark):
        """Formats output for a given bookmark.

        Args:
            bookmark (dict):   the bookmark data to format.

        Returns:
            output (str):   the formatted output.

        """
        alias = bookmark['alias']
        description = bookmark['description']
        tags = bookmark['tags']
        title = bookmark['title']
        url = bookmark['url']

        # mainline
        aliastxt = Text(f"({alias})")
        aliastxt.stylize(self.style_alias)
        titletxt = Text(title)
        titletxt.stylize(self.style_bookmark_title)
        mainline = Text.assemble(aliastxt, " ", titletxt)

        # urlline
        if url:
            urllabel = Text("url:")
            urllabel.stylize(self.style_label)
            urltxt = Text(url)
            urltxt.stylize(self.style_url)
            urlline = Text.assemble(
                "\n   + ", urllabel, " ", urltxt)
        else:
            urlline = ""

        # descriptionline
        if description:
            descriptionlabel = Text("description:")
            descriptionlabel.stylize(self.style_label)
            descriptiontxt = Text(description)
            descriptiontxt.stylize(self.style_description)
            descriptionline = Text.assemble(
                "\n   + ", descriptionlabel, " ", descriptiontxt)
        else:
            descriptionline = ""

        # tagsline
        if tags:
            tagslabel = Text("tags:")
            tagslabel.stylize(self.style_label)
            tagstxt = Text(','.join(tags))
            tagstxt.stylize(self.style_tags)
            tagsline = Text.assemble(
                "\n   + ", tagslabel, " ", tagstxt)
        else:
            tagsline = ""

        # assemble lines into bookmark block
        output = Text.assemble(
            "- ",
            mainline,
            urlline,
            descriptionline,
            tagsline)

        return output

    @staticmethod
    def _format_timestamp(timeobj, pretty=False):
        """Convert a datetime obj to a string.

        Args:
            timeobj (datetime): a datetime object.
            pretty (bool):      return a pretty formatted string.

        Returns:
            timestamp (str): "%Y-%m-%d %H:%M:%S" or "%Y-%m-%d[ %H:%M]".

        """
        if pretty:
            if timeobj.strftime("%H:%M") == "00:00":
                timestamp = timeobj.strftime("%Y-%m-%d")
            else:
                timestamp = timeobj.strftime("%Y-%m-%d %H:%M")
        else:
            timestamp = timeobj.strftime("%Y-%m-%d %H:%M:%S")
        return timestamp

    def _gen_alias(self):
        """Generates a new alias and check for collisions.

        Returns:
            alias (str):    a randomly-generated alias.

        """
        aliases = self._get_aliases()
        chars = string.ascii_lowercase + string.digits
        while True:
            alias = ''.join(random.choice(chars) for x in range(4))
            if alias not in aliases:
                break
        return alias

    def _get_aliases(self):
        """Generates a list of all bookmark aliases.

        Returns:
            aliases (list): the list of all bookmark aliases.

        """
        aliases = []
        for bookmark in self.bookmarks:
            alias = self.bookmarks[bookmark].get('alias')
            if alias:
                aliases.append(alias.lower())
        return aliases

    @staticmethod
    def _get_url_info(requrl):
        """Reads a website and returns url, title, and description.

        Args:
            requrl (str):  the URL for which to get info.

        Returns:
            info (dict): information about the URL.

        """
        try:
            page = requests.get(requrl, timeout=5)
        except requests.exceptions.RequestException:
            title = "No title"
            description = None
        else:
            html = BeautifulSoup(page.text, features="lxml")
            if html.title:
                if html.title.string:
                    title = str(html.title.string)
                else:
                    title = "No title"
            else:
                title = "No title"

            description = None
            # try to find a description from meta tags
            for tag in html.find_all("meta"):
                if tag.get("name") == "description":
                    description = tag.get("content")
                elif tag.get("property") == "og:description":
                    description = tag.get("content")
        # cleanup
        title = " ".join(title.replace('\n', ' ').split())
        if description:
            description = " ".join(description.replace('\n', ' ').split())
        info = {}
        info['url'] = requrl
        info['title'] = title
        info['description'] = description

        return info

    def _handle_error(self, msg):
        """Reports an error message and conditionally handles error exit
        or notification.

        Args:
            msg (str):  the error message.

        """
        if self.interactive:
            self._error_pass(msg)
        else:
            self._error_exit(msg)

    def _make_all_tags(self):
        """Create an index of tags and bookmarks in self.all_tags."""
        self.all_tags = {}
        for uid in self.bookmarks:
            tags = self.bookmarks[uid].get('tags')
            if tags:
                if not isinstance(tags, list):
                    tags = list(tags)
                for tag in tags:
                    if tag in self.all_tags.keys():
                        if uid not in self.all_tags[tag]:
                            self.all_tags[tag].append(uid)
                    else:
                        self.all_tags[tag] = [uid]
        self.all_tags = dict(sorted(self.all_tags.items()))

    def _parse_bookmark(self, uid):
        """Parse a bookmark and return values for bookmark parameters.

        Args:
            uid (str):  the UID of the bookmark to parse.

        Returns:
            bookmark (dict): the bookmark parameters.

        """
        bookmark = {}
        bookmark['uid'] = self.bookmarks[uid].get('uid')
        bookmark['created'] = self.bookmarks[uid].get('created')
        if bookmark['created']:
            bookmark['created'] = self._datetime_or_none(bookmark['created'])

        bookmark['updated'] = self.bookmarks[uid].get('updated')
        if bookmark['updated']:
            bookmark['updated'] = self._datetime_or_none(bookmark['updated'])

        bookmark['alias'] = self.bookmarks[uid].get('alias')
        if bookmark['alias']:
            bookmark['alias'] = bookmark['alias'].lower()

        bookmark['title'] = self.bookmarks[uid].get('title')
        bookmark['url'] = self.bookmarks[uid].get('url')
        bookmark['description'] = self.bookmarks[uid].get('description')
        bookmark['tags'] = self.bookmarks[uid].get('tags')

        return bookmark

    def _parse_config(self):
        """Read and parse the configuration file."""
        config = configparser.ConfigParser()
        if os.path.isfile(self.config_file):
            try:
                config.read(self.config_file)
            except configparser.Error:
                self._error_exit("Error reading config file")

            if "main" in config:
                if config["main"].get("data_dir"):
                    self.data_dir = os.path.expandvars(
                        os.path.expanduser(
                            config["main"].get("data_dir")))

                if config["main"].get("always_new_window"):
                    try:
                        self.always_new_window = (config["main"]
                                                  .getboolean(
                                                    "always_new_window",
                                                    False))
                    except ValueError:
                        self.always_new_window = False
                self.browser_cmd = config["main"].get(
                        "browser_cmd", raw=True)

            def _apply_colors():
                """Try to apply custom colors and catch exceptions for
                invalid color names.
                """
                try:
                    self.style_table_title = Style(
                        color=self.color_table_title,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_bookmark_title = Style(
                        color=self.color_bookmark_title,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_description = Style(
                        color=self.color_description)
                except ColorParseError:
                    pass
                try:
                    self.style_url = Style(
                        color=self.color_url)
                except ColorParseError:
                    pass
                try:
                    self.style_alias = Style(
                        color=self.color_alias)
                except ColorParseError:
                    pass
                try:
                    self.style_tags = Style(
                        color=self.color_tags)
                except ColorParseError:
                    pass
                try:
                    self.style_label = Style(
                        color=self.color_label)
                except ColorParseError:
                    pass

            # apply default colors
            _apply_colors()

            if "colors" in config:
                # custom colors with fallback to defaults
                self.color_table_title = (
                    config["colors"].get(
                        "table_title", "bright_blue"))
                self.color_bookmark_title = (
                    config["colors"].get(
                        "bookmark_title", "green"))
                self.color_description = (
                    config["colors"].get(
                        "description", "default"))
                self.color_url = (
                    config["colors"].get(
                        "url", "yellow"))
                self.color_alias = (
                    config["colors"].get(
                        "alias", "bright_black"))
                self.color_tags = (
                    config["colors"].get(
                        "tags", "cyan"))
                self.color_label = (
                    config["colors"].get(
                        "label", "white"))

                # color paging (disabled by default)
                self.color_pager = config["colors"].getboolean(
                    "color_pager", "False")

                # disable colors
                if bool(config["colors"].getboolean("disable_colors")):
                    self.color_table_title = "default"
                    self.color_bookmark_title = "default"
                    self.color_description = "default"
                    self.color_url = "default"
                    self.color_alias = "default"
                    self.color_tags = "default"
                    self.color_label = "default"

                # disable bold
                if bool(config["colors"].getboolean("disable_bold")):
                    self.color_bold = False

                # try to apply requested custom colors
                _apply_colors()
        else:
            self._error_exit("Config file not found")

    def _parse_files(self):
        """ Read bookmark files from `data_dir` and parse bookmark
        data into`bookmarks`.

        Returns:
            bookmarks (dict):    parsed data from each bookmark file

        """
        this_bookmark_files = {}
        this_bookmarks = {}
        aliases = {}

        with os.scandir(self.data_dir) as entries:
            for entry in entries:
                if entry.name.endswith('.yml') and entry.is_file():
                    fullpath = entry.path
                    data = None
                    try:
                        with open(fullpath, "r",
                                  encoding="utf-8") as entry_file:
                            data = yaml.safe_load(entry_file)
                    except (OSError, IOError, yaml.YAMLError):
                        self._error_pass(
                            f"failure reading or parsing {fullpath} "
                            "- SKIPPING")
                    if data:
                        uid = None
                        bookmark = data.get("bookmark")
                        if bookmark:
                            uid = bookmark.get("uid")
                            alias = bookmark.get("alias")
                            add_bookmark = True
                            if uid:
                                # duplicate UID detection
                                dupid = this_bookmark_files.get(uid)
                                if dupid:
                                    self._error_pass(
                                        "duplicate UID detected:\n"
                                        f"  {uid}\n"
                                        f"  {dupid}\n"
                                        f"  {fullpath}\n"
                                        f"SKIPPING {fullpath}")
                                    add_bookmark = False
                            if alias:
                                # duplicate alias detection
                                dupalias = aliases.get(alias)
                                if dupalias:
                                    self._error_pass(
                                        "duplicate alias detected:\n"
                                        f"  {alias}\n"
                                        f"  {dupalias}\n"
                                        f"  {fullpath}\n"
                                        f"SKIPPING {fullpath}")
                                    add_bookmark = False
                            if add_bookmark:
                                if alias and uid:
                                    this_bookmarks[uid] = bookmark
                                    this_bookmark_files[uid] = fullpath
                                    aliases[alias] = fullpath
                                else:
                                    self._error_pass(
                                        "no uid and/or alias param "
                                        f"in {fullpath} - SKIPPING")
                        else:
                            self._error_pass(
                                f"no data in {fullpath} - SKIPPING")
        self.bookmark_files = this_bookmark_files.copy()
        self.bookmarks = this_bookmarks.copy()
        self._make_all_tags()

    def _perform_search(self, term):
        """Parses a search term and returns a list of matching bookmarks.
        A 'term' can consist of two parts: 'search' and 'exclude'. The
        operator '%' separates the two parts. The 'exclude' part is
        optional.
        The 'search' and 'exclude' terms use the same syntax but differ
        in one noteable way:
          - 'search' is parsed as AND. All parameters must match to
        return a bookmark record. Note that within a parameter the '+'
        operator is still an OR.
          - 'exclude' is parsed as OR. Any parameters that match will
        exclude a bookmark record.

        Args:
            term (str):     the search term to parse.

        Returns:
            this_bookmarks (list): the bookmarks matching the search criteria.

        """
        # if the exclusion operator is in the provided search term then
        # split the term into two components: search and exclude
        # otherwise, treat it as just a search term alone.
        if "%" in term:
            term = term.split("%")
            searchterm = str(term[0]).lower()
            excludeterm = str(term[1]).lower()
        else:
            searchterm = str(term).lower()
            excludeterm = None

        valid_criteria = [
            "uid=",
            "title=",
            "description=",
            "url=",
            "alias=",
            "tags="
        ]
        # parse the search term into a dict
        simple_search = False
        if searchterm:
            if searchterm == 'any':
                search = None
            elif not any(x in searchterm for x in valid_criteria):
                # treat this as a simple url/title/description search
                simple_search = True
                search = {}
                search['url'] = searchterm.strip()
                search['title'] = searchterm.strip()
                search['description'] = searchterm.strip()
            else:
                try:
                    search = dict((k.strip(), v.strip())
                                  for k, v in (item.split('=')
                                  for item in searchterm.split(',')))
                except ValueError:
                    msg = "invalid search expression"
                    if not self.interactive:
                        self._error_exit(msg)
                    else:
                        self._error_pass(msg)
                        return
        else:
            search = None
        # parse the exclude term into a dict
        if excludeterm:
            if not any(x in excludeterm for x in valid_criteria):
                # treat this as a simple url/title/description exclusion
                exclude = {}
                exclude['url'] = excludeterm.strip()
                exclude['title'] = excludeterm.strip()
                exclude['description'] = excludeterm.strip()
            else:
                try:
                    exclude = dict((k.strip(), v.strip())
                                   for k, v in (item.split('=')
                                   for item in excludeterm.split(',')))
                except ValueError:
                    msg = "invalid exclude expression"
                    if not self.interactive:
                        self._error_exit(msg)
                    else:
                        self._error_pass(msg)
                        return
        else:
            exclude = None

        this_bookmarks = []
        for uid in self.bookmarks:
            this_bookmarks.append(uid)
        exclude_list = []

        if exclude:
            x_uid = exclude.get('uid')
            x_alias = exclude.get('alias')
            x_title = exclude.get('title')
            x_description = exclude.get('description')
            x_url = exclude.get('url')
            x_tags = exclude.get('tags')
            if x_tags:
                x_tags = x_tags.split('+')

            for uid in this_bookmarks:
                bookmark = self._parse_bookmark(uid)
                remove = False
                if x_uid:
                    if bookmark['uid']:
                        if x_uid == bookmark['uid']:
                            remove = True
                if x_alias:
                    if bookmark['alias']:
                        if x_alias == bookmark['alias']:
                            remove = True
                if x_title:
                    if bookmark['title']:
                        if x_title in bookmark['title']:
                            remove = True
                if x_description:
                    if bookmark['description']:
                        if x_description in bookmark['description']:
                            remove = True
                if x_url:
                    if bookmark['url']:
                        if x_url in bookmark['url']:
                            remove = True
                if x_tags:
                    if bookmark['tags']:
                        for tag in x_tags:
                            if tag in bookmark['tags']:
                                remove = True
                if remove:
                    exclude_list.append(uid)

        # remove excluded bookmarks
        for uid in exclude_list:
            this_bookmarks.remove(uid)

        not_match = []

        if search:
            s_uid = search.get('uid')
            s_alias = search.get('alias')
            s_title = search.get('title')
            s_description = search.get('description')
            s_url = search.get('url')
            s_tags = search.get('tags')
            if s_tags:
                s_tags = s_tags.split('+')

            for uid in this_bookmarks:
                bookmark = self._parse_bookmark(uid)
                remove = False
                if s_uid:
                    if bookmark['uid']:
                        if not s_uid == bookmark['uid']:
                            remove = True
                if s_alias:
                    if bookmark['alias']:
                        if not s_alias == bookmark['alias']:
                            remove = True
                    else:
                        remove = True
                if not simple_search:
                    if s_title:
                        if bookmark['title']:
                            if (s_title not in
                                    bookmark['title'].lower()):
                                remove = True
                        else:
                            remove = True
                    if s_description:
                        if bookmark['description']:
                            if (s_description not in
                                    bookmark['description'].lower()):
                                remove = True
                        else:
                            remove = True
                    if s_url:
                        if bookmark['url']:
                            if (s_url not in
                                    bookmark['url'].lower()):
                                remove = True
                        else:
                            remove = True
                else:
                    if bookmark['title']:
                        if (s_title not in
                                bookmark['title'].lower()):
                            title_match = False
                        else:
                            title_match = True
                    else:
                        title_match = False

                    if bookmark['description']:
                        if (s_description not in
                                bookmark['description'].lower()):
                            description_match = False
                        else:
                            description_match = True
                    else:
                        description_match = False

                    if bookmark['url']:
                        if (s_url not in
                                bookmark['url'].lower()):
                            url_match = False
                        else:
                            url_match = True
                    else:
                        url_match = False
                    if not any([title_match, description_match, url_match]):
                        remove = True
                if s_tags:
                    keep = False
                    if bookmark['tags']:
                        # searching for tags allows use of the '+' OR
                        # operator, so if we match any tag in the list
                        # then keep the entry
                        for tag in s_tags:
                            if tag in bookmark['tags']:
                                keep = True
                    if not keep:
                        remove = True
                if remove:
                    not_match.append(uid)

        # remove the bookmarks that didn't match search criteria
        for uid in not_match:
            this_bookmarks.remove(uid)

        return this_bookmarks

    def _print_bookmark_list(
            self,
            bookmarks,
            view,
            pager=False):
        """Print the formatted bookmarks list.

        Args:
            bookmarks (list):   the list of bookmarks (dicts) to be printed in
        a formatted manner.
            view (str):     the view to display (e.g., bookmark, tag, etc.)
            pager (bool):   whether or not to page output (default no).

        """
        console = Console()
        title = f"Bookmarks - {view}"
        # table
        bookmarks_table = Table(
            title=title,
            title_style=self.style_table_title,
            title_justify="left",
            box=box.SIMPLE,
            show_header=False,
            show_lines=False,
            pad_edge=False,
            min_width=40,
            collapse_padding=False,
            padding=(0, 0, 0, 0))
        # single column
        bookmarks_table.add_column(
                "column1", no_wrap=True, overflow='ellipsis')
        # bookmark list
        if bookmarks:
            for uid in bookmarks:
                bookmark = self._parse_bookmark(uid)
                fbookmark = self._format_bookmark(bookmark)
                bookmarks_table.add_row(fbookmark)
                if bookmark != bookmarks[-1]:
                    bookmarks_table.add_row("")
        else:
            bookmarks_table.add_row("None")
        # single-column layout
        layout = Table.grid()
        layout.add_column("single")
        layout.add_row("")
        layout.add_row(bookmarks_table)

        # render the output with a pager if -p
        if pager:
            if self.color_pager:
                with console.pager(styles=True):
                    console.print(layout)
            else:
                with console.pager():
                    console.print(layout)
        else:
            console.print(layout)

    def _print_tag_list(self, pager=False):
        """Print the list of all tags and the number of bookmarks in each.

        Args:
            pager (bool):   page output.

        """
        console = Console()
        # table
        tags_table = Table(
            title="All tags",
            title_style=self.style_table_title,
            title_justify="left",
            box=box.SIMPLE,
            show_header=False,
            show_lines=False,
            pad_edge=False,
            min_width=10,
            collapse_padding=False,
            padding=(0, 0, 0, 0))
        # two columns
        tags_table.add_column("tag", no_wrap=True, overflow='ellipsis')
        tags_table.add_column("count")
        if self.all_tags:
            for tag in self.all_tags:
                tags_table.add_row(tag, f"({len(self.all_tags[tag])})")
        else:
            tags_table.add_row("None")
        # single-column layout
        layout = Table.grid()
        layout.add_column("single")
        layout.add_row("")
        layout.add_row(tags_table)

        # render the output with a pager if -p
        if pager:
            if self.color_pager:
                with console.pager(styles=True):
                    console.print(layout)
            else:
                with console.pager():
                    console.print(layout)
        else:
            console.print(layout)

    def _sort_bookmarks(self, bookmarks, reverse=False):
        """Sort a list of bookmarks by title and return a sorted dict.

        Args:

            bookmarks (list):   the bookmarks to sort.
            reverse (bool): sort in reverse (optional).

        Returns:
            uids (dict):    a sorted dict of bookmarks.

        """
        fifouids = {}
        for uid in bookmarks:
            sort = self.bookmarks[uid].get('title')
            fifouids[uid] = sort
        sortlist = sorted(
            fifouids.items(), key=lambda x: x[1], reverse=reverse
        )
        uids = dict(sortlist)
        return uids

    def _uid_from_alias(self, alias):
        """Get the uid for a valid alias.

        Args:
            alias (str):    The alias of the bookmark for which to find uid.

        Returns:
            uid (str or None): The uid that matches the submitted alias.

        """
        alias = alias.lower()
        uid = None
        for bookmark in self.bookmarks:
            this_alias = self.bookmarks[bookmark].get("alias")
            if this_alias:
                if this_alias == alias:
                    uid = bookmark
        return uid

    def _verify_data_dir(self):
        """Create the bookmarks data directory if it doesn't exist."""
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir)
            except IOError:
                self._error_exit(
                    f"{self.data_dir} doesn't exist "
                    "and can't be created")
        elif not os.path.isdir(self.data_dir):
            self._error_exit(f"{self.data_dir} is not a directory")
        elif not os.access(self.data_dir,
                           os.R_OK | os.W_OK | os.X_OK):
            self._error_exit(
                "You don't have read/write/execute permissions to "
                f"{self.data_dir}")

    @staticmethod
    def _write_bookmark_file(data, filename):
        """Write YAML data to a bookmark file.

        Args:
            data (dict):    the structured data to write.
            filename (str): the location to write the data.

        """
        with open(filename, "w",
                  encoding="utf-8") as out_file:
            yaml.dump(
                data,
                out_file,
                default_flow_style=False,
                sort_keys=False)

    def archive(self, alias, force=False):
        """Archive an bookmark identified by alias. Move the bookmark to
        the {data_dir}/archive directory.

        Args:
            alias (str):    The alias of the bookmark to be archived.
            force (bool):   Don't ask for confirmation before archiving.

        """
        archive_dir = os.path.join(self.data_dir, "archive")
        if not os.path.exists(archive_dir):
            try:
                os.makedirs(archive_dir)
            except OSError:
                msg = (
                    f"{archive_dir} doesn't exist and can't be created"
                )
                if not self.interactive:
                    self._error_exit(msg)
                else:
                    self._error_pass(msg)
                    return

        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            if force:
                confirm = "yes"
            else:
                confirm = input(f"Archive {alias}? [N/y]: ").lower()
            if confirm in ['yes', 'y']:
                filename = self.bookmark_files.get(uid)
                if filename:
                    archive_file = os.path.join(
                        archive_dir, os.path.basename(filename))
                    try:
                        shutil.move(filename, archive_file)
                    except (IOError, OSError):
                        self._handle_error(f"failure moving {filename}")
                    else:
                        print(f"Archived bookmark: {alias}")
                else:
                    self._handle_error(f"failed to find file for {alias}")
            else:
                print("Cancelled.")

    def delete(self, alias, force=False):
        """Delete a bookmark identified by alias.

        Args:
            alias (str):    The alias of the bookmark to be deleted.

        """
        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            filename = self.bookmark_files.get(uid)
            if filename:
                if force:
                    confirm = "yes"
                else:
                    confirm = input(f"Delete '{alias}'? [yes/no]: ").lower()
                if confirm in ['yes', 'y']:
                    try:
                        os.remove(filename)
                    except OSError:
                        self._handle_error(f"failure deleting {filename}")
                    else:
                        print(f"Deleted bookmark: {alias}")
                else:
                    print("Cancelled")
            else:
                self._handle_error(f"failed to find file for {alias}")

    def edit(self, alias):
        """Edit a bookmark identified by alias (using $EDITOR).

        Args:
            alias (str):    The alias of the bookmark to be edited.

        """
        if self.editor:
            alias = alias.lower()
            uid = self._uid_from_alias(alias)
            if not uid:
                self._alias_not_found(alias)
            else:
                filename = self.bookmark_files.get(uid)
                if filename:
                    try:
                        subprocess.run([self.editor, filename], check=True)
                    except subprocess.SubprocessError:
                        self._handle_error(
                            f"failure editing file {filename}")
                else:
                    self._handle_error(f"failed to find file for {alias}")
        else:
            self._handle_error("$EDITOR is required and not set")

    def edit_config(self):
        """Edit the config file (using $EDITOR) and then reload config."""
        if self.editor:
            try:
                subprocess.run(
                    [self.editor, self.config_file], check=True)
            except subprocess.SubprocessError:
                self._handle_error("failure editing config file")
            else:
                if self.interactive:
                    self._parse_config()
                    self.refresh()
        else:
            self._handle_error("$EDITOR is required and not set")

    def info(self, alias, pager=False):
        """Display information for a bookmark identified by alias.

        Args:
            alias (str):    The alias of the bookmark to be diplayed.
            pager (bool):   Pipe output through console.pager.

        """
        console = Console()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            bookmark = self._parse_bookmark(uid)

            info_table = Table(
                title=f"Bookmark info - {alias}",
                title_style=self.style_table_title,
                title_justify="left",
                box=box.SIMPLE,
                show_header=False,
                show_lines=False,
                pad_edge=False,
                collapse_padding=False,
                min_width=40,
                padding=(0, 0, 0, 0))
            info_table.add_column("label", style=self.style_label)
            info_table.add_column("data")

            info_table.add_row("title:", bookmark['title'])
            info_table.add_row("description:", bookmark['description'])
            info_table.add_row("url:", bookmark['url'])
            if bookmark['tags']:
                tags = ','.join(bookmark['tags'])
                info_table.add_row("tags:", tags)
            info_table.add_row("uid:", bookmark['uid'])
            if bookmark['created']:
                created = self._format_timestamp(bookmark['created'])
                info_table.add_row("created:", created)
            if bookmark['updated']:
                updated = self._format_timestamp(bookmark['updated'])
                info_table.add_row("updated:", updated)
            info_table.add_row("file:", self.bookmark_files[uid])
            layout = Table.grid()
            layout.add_column("single")
            layout.add_row("")
            layout.add_row(info_table)
            # render the output with a pager if --pager or -p
            if pager:
                if self.color_pager:
                    with console.pager(styles=True):
                        console.print(layout)
                else:
                    with console.pager():
                        console.print(layout)
            else:
                console.print(layout)

    def list(
            self,
            view,
            pager=None):
        """Prints a list of bookmarks.

        Args:
            view (str): a bookmark alias, a tag, 'tags', or 'all'
            pager (bool): paginate the output.

        """
        if view.lower() == 'all':
            selected_bookmarks = []
            for uid in self.bookmarks:
                selected_bookmarks.append(uid)
            self._print_bookmark_list(selected_bookmarks, 'all', pager=pager)
        elif view.lower() == 'tags':
            self._print_tag_list(pager=pager)
        elif view.lower() in self._get_aliases():
            uid = self._uid_from_alias(view.lower())
            if uid:
                selected_bookmarks = [uid]
                self._print_bookmark_list(
                        selected_bookmarks, view, pager=pager)
            else:
                self._handle_error(f"cannot find URL for: {view}")
        elif view.lower() in self.all_tags.keys():
            selected_bookmarks = []
            for uid in self.all_tags[view]:
                selected_bookmarks.append(uid)
            self._print_bookmark_list(selected_bookmarks, view, pager=pager)
        else:
            self._handle_error(f"no such bookmark, tag, or view: {view}")

    def modify(
            self,
            alias,
            new_alias=None,
            new_title=None,
            new_description=None,
            new_url=None,
            new_tags=None):
        """Modify a bookmark's metadata using provided parameters.

        Args:
            alias(str):             the bookmark alias being updated.
            new_alias (str):        new bookmark alias.
            new_title (str):        new bookmark title.
            new_description (str):  new bookmark description.
            new_url (str):          new bookmark url.
            new_tags (str):         new bookmark tags.

        """
        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            filename = self.bookmark_files.get(uid)
            aliases = self._get_aliases()
            bookmark = self._parse_bookmark(uid)

            if filename:
                created = bookmark['created']
                u_updated = datetime.now(tz=self.ltz)
                if new_alias:
                    new_alias = new_alias.lower()
                    # duplicate alias check
                    aliases = self._get_aliases()
                    msg = f"alias '{alias}' already exists"
                    if new_alias in aliases and self.interactive:
                        self._error_pass(msg)
                        return
                    elif new_alias in aliases:
                        self._error_exit(msg)
                    else:
                        u_alias = new_alias
                else:
                    u_alias = alias
                u_title = new_title or bookmark['title']
                u_description = new_description or bookmark['description']
                u_url = new_url or bookmark['url']
                if new_tags:
                    new_tags = new_tags.lower()
                    if new_tags.startswith('+'):
                        new_tags = new_tags[1:]
                        new_tags = new_tags.split(',')
                        if not bookmark['tags']:
                            tags = []
                        else:
                            tags = bookmark['tags'].copy()
                        for new_tag in new_tags:
                            if new_tag not in tags:
                                tags.append(new_tag)
                        if tags:
                            tags.sort()
                            u_tags = tags
                        else:
                            u_tags = None
                    elif new_tags.startswith('~'):
                        new_tags = new_tags[1:]
                        new_tags = new_tags.split(',')
                        if bookmark['tags']:
                            tags = bookmark['tags'].copy()
                            for new_tag in new_tags:
                                if new_tag in tags:
                                    tags.remove(new_tag)
                            if tags:
                                tags.sort()
                                u_tags = tags
                            else:
                                u_tags = None
                        else:
                            u_tags = None
                    else:
                        u_tags = new_tags.split(',')
                        u_tags.sort()
                else:
                    u_tags = bookmark['tags']
                data = {
                    "bookmark": {
                        "uid": uid,
                        "created": created,
                        "updated": u_updated,
                        "alias": u_alias,
                        "title": u_title,
                        "description": u_description,
                        "url": u_url,
                        "tags": u_tags
                    }
                }
                # write the updated file
                self._write_bookmark_file(data, filename)

    def new(
            self,
            title=None,
            description=None,
            url=None,
            tags=None):
        """Create a new bookmark.

        Args:
            title (str):        bookmark title.
            description (str):  bookmark description.
            url (str):          bookmark url.
            tags (str):         tags assigned to the bookmark.

        """
        uid = str(uuid.uuid4())
        alias = self._gen_alias()
        now = datetime.now(tz=self.ltz)
        if not title or not description:
            info = self._get_url_info(url)
            found_title = info['title']
            found_description = info['description']
        else:
            found_title = "No title"
            found_description = None
        title = title or found_title
        description = description or found_description
        if tags:
            tags = tags.lower()
            tags = tags.split(',')
            tags.sort()
        filename = os.path.join(self.data_dir, f"{uid}.yml")
        data = {
            "bookmark": {
                "uid": uid,
                "created": now,
                "updated": now,
                "alias": alias,
                "title": title,
                "description": description,
                "url": url,
                "tags": tags
            }
        }
        self._write_bookmark_file(data, filename)
        print(f"Added bookmark: {alias}")

    def new_bookmark_wizard(self):
        """Prompt the user for bookmark parameters and then call new()."""
        url = input("URL [none]: ") or None
        if url:
            info = self._get_url_info(url)
        else:
            self._error_pass("URL is required")
            return
        found_title = info['title']
        found_description = info['description']
        if found_title == "No title":
            title = input("Title [No title]: ") or "No title"
        else:
            title = found_title
        if not found_description:
            description = input("Description [none]: ") or None
        else:
            description = found_description
        tags = input("Tags [none]: ") or None
        self.new(
            title=title,
            description=description,
            url=url,
            tags=tags)

    def open(
            self,
            alias,
            new_window=False):
        """Open a bookmark in the user's browser.

        Args:
            alias (str):    the bookmark to open.
            new_window (bool): open the bookmark in a new window.

        """
        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            bookmark = self._parse_bookmark(uid)
            url = bookmark['url']
            if url:
                if self.browser_cmd:
                    open_cmd = self.browser_cmd.split()
                    open_cmd = [url if item == '%u'
                                else item for item in open_cmd]
                    open_cmd = ' '.join(open_cmd)
                    try:
                        subprocess.run(
                            open_cmd,
                            check=True,
                            shell=True)
                    except subprocess.CalledProcessError:
                        self._handle_error(
                                "unable to open {alias} in browser")
                else:
                    try:
                        if new_window or self.always_new_window:
                            webbrowser.open(url, new=1)
                        else:
                            webbrowser.open(url, new=2)
                    except webbrowser.Error:
                        self._handle_error(
                                f"unable to open {alias} in browser")
            else:
                self._handle_error(f"{alias} has no URL")

    def query(self, term, limit=None, json_output=False):
        """Perform a search for bookmarks that match a given criteria and
        print the results in plain, tab-delimited text or JSON.

        Args:
            term (str):     the criteria for which to search.
            limit (str):    filter output to specific fields (TSV only).
            json_output (bool): output in JSON format.

        """
        result_bookmarks = self._perform_search(term)
        if limit:
            limit = limit.split(',')
        bookmarks_out = {}
        bookmarks_out['bookmarks'] = []
        text_out = ""
        if len(result_bookmarks) > 0:
            for uid in result_bookmarks:
                this_bookmark = {}
                bookmark = self._parse_bookmark(uid)
                title = bookmark["title"] or ""
                description = bookmark["description"] or ""
                url = bookmark["url"] or ""
                alias = bookmark["alias"] or ""
                tags = bookmark["tags"] or []
                created = bookmark['created']
                updated = bookmark['updated']
                if created:
                    created = self._format_timestamp(created)
                if updated:
                    updated = self._format_timestamp(updated)

                if limit:
                    output = ""
                    if "uid" in limit:
                        output += f"{uid}\t"
                    if "alias" in limit:
                        output += f"{alias}\t"
                    if "title" in limit:
                        output += f"{title}\t"
                    if "description" in limit:
                        output += f"{description}\t"
                    if "url" in limit:
                        output += f"{url}\t"
                    if "tags" in limit:
                        output += f"{tags}\t"
                    if output.endswith('\t'):
                        output = output.rstrip(output[-1])
                    output = f"{output}\n"
                else:
                    output = (
                        f"{uid}\t"
                        f"{alias}\t"
                        f"{title}\t"
                        f"{description}\t"
                        f"{url}\t"
                        f"{tags}\n"
                    )
                this_bookmark['uid'] = uid
                this_bookmark['created'] = created
                this_bookmark['updated'] = updated
                this_bookmark['alias'] = alias
                this_bookmark['title'] = title
                this_bookmark['description'] = description
                this_bookmark['url'] = url
                this_bookmark['tags'] = tags
                bookmarks_out['bookmarks'].append(this_bookmark)
                text_out += f"{output}"
        if json_output:
            json_out = json.dumps(bookmarks_out, indent=4)
            print(json_out)
        else:
            if text_out != "":
                print(text_out, end="")
            else:
                print("No results.")

    def refresh(self):
        """Public method to refresh data."""
        self._parse_files()

    def search(self, term, pager=False):
        """Perform a search for bookmarks that match a given term and
        print the results in formatted text.

        Args:
            term (str):     the criteria for which to search.
            pager (bool):   whether to page output.

        """
        this_bookmarks = self._perform_search(term)
        self._print_bookmark_list(
                this_bookmarks,
                'search results',
                pager=pager)

    def unset(self, alias, field):
        """Clear a specified field for a given alias.

        Args:
            alias (str):    the bookmark alias.
            field (str):    the field to clear.

        """
        alias = alias.lower()
        field = field.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            allowed_fields = [
                'description',
                'tags'
            ]
            if field in allowed_fields:
                if self.bookmarks[uid][field]:
                    self.bookmarks[uid][field] = None
                    bookmark = self._parse_bookmark(uid)
                    filename = self.bookmark_files.get(uid)
                    if bookmark and filename:
                        data = {
                            "bookmark": {
                                "uid": bookmark['uid'],
                                "created": bookmark['created'],
                                "updated": bookmark['updated'],
                                "alias": bookmark['alias'],
                                "title": bookmark['title'],
                                "description": bookmark['description'],
                                "url": bookmark['url'],
                                "tags": bookmark['tags']
                            }
                        }
                        # write the updated file
                        self._write_bookmark_file(data, filename)
            else:
                self._handle_error(f"cannot clear field '{field}'")


class FSHandler(FileSystemEventHandler):
    """Handler to watch for file changes and refresh data from files.

    Attributes:
        shell (obj):    the calling shell object.

    """
    def __init__(self, shell):
        """Initializes an FSHandler() object."""
        self.shell = shell

    def on_any_event(self, event):
        """Refresh data in memory on data file changes.
        Args:
            event (obj):    file system event.
        """
        if event.event_type in [
                'created', 'modified', 'deleted', 'moved']:
            self.shell.do_refresh("silent")


class BookmarksShell(Cmd):
    """Provides methods for interactive shell use.

    Attributes:
        bookmarks (obj):     an instance of Bookmarks().

    """
    def __init__(
            self,
            bookmarks,
            completekey='tab',
            stdin=None,
            stdout=None):
        """Initializes a BookmarksShell() object."""
        super().__init__()
        self.bookmarks = bookmarks

        # start watchdog for data_dir changes
        # and perform refresh() on changes
        observer = Observer()
        handler = FSHandler(self)
        observer.schedule(
                handler,
                self.bookmarks.data_dir,
                recursive=True)
        observer.start()

        # class overrides for Cmd
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.completekey = completekey
        self.doc_header = (
            "Commands (for more info type: help):"
        )
        self.ruler = "―"

        self._set_prompt()

        self.nohelp = (
            "\nNo help for %s\n"
        )
        self.do_clear(None)

        print(
            f"{APP_NAME} {APP_VERS}\n\n"
            f"Enter command (or 'help')\n"
        )

    # class method overrides
    def default(self, args):
        """Handle command aliases and unknown commands.

        Args:
            args (str): the command arguments.

        """
        if args == "quit":
            self.do_exit("")
        elif args == "lsa":
            self.do_list("all")
        elif args == "lsa |":
            self.do_list("all |")
        elif args == "lst":
            self.do_list("tags")
        elif args == "lst |":
            self.do_list("tags |")
        elif args.startswith("ls"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_list(newargs[1])
            else:
                self.do_list("")
        elif args.startswith("rm"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_delete(newargs[1])
            else:
                self.do_delete("")
        elif args.startswith("mod"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_modify(newargs[1])
            else:
                self.do_modify("")
        else:
            print("\nNo such command. See 'help'.\n")

    def emptyline(self):
        """Ignore empty line entry."""

    def _set_prompt(self):
        """Set the prompt string."""
        if self.bookmarks.color_bold:
            self.prompt = "\033[1mbookmarks\033[0m> "
        else:
            self.prompt = "bookmarks> "

    def _uid_from_alias(self, alias):
        """Get the uid for a valid alias.

        Args:
            alias (str):    The alias of the bookmark for which to find
        uid.

        Returns:
            uid (str or None): The uid that matches the submitted alias.

        """
        alias = alias.lower()
        uid = None
        for bookmark in self.bookmarks.bookmarks:
            this_alias = self.bookmarks.bookmarks[bookmark].get("alias")
            if this_alias:
                if this_alias == alias:
                    uid = bookmark
        return uid

    def do_archive(self, args):
        """Archive a bookmark.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.bookmarks.archive(str(commands[0]).lower())
        else:
            self.help_archive()

    @staticmethod
    def do_clear(args):
        """Clear the terminal.

        Args:
            args (str): the command arguments, ignored.

        """
        os.system("cls" if os.name == "nt" else "clear")

    def do_config(self, args):
        """Edit the config file and reload the configuration.

        Args:
            args (str): the command arguments, ignored.

        """
        self.bookmarks.edit_config()

    def do_delete(self, args):
        """Delete a bookmark.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.bookmarks.delete(str(commands[0]).lower())
        else:
            self.help_delete()

    def do_edit(self, args):
        """Edit a bookmark via $EDITOR.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.bookmarks.edit(str(commands[0]).lower())
        else:
            self.help_edit()

    @staticmethod
    def do_exit(args):
        """Exit the bookmarks shell.

        Args:
            args (str): the command arguments, ignored.

        """
        sys.exit(0)

    def do_info(self, args):
        """Output info about a bookmark.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            alias = str(commands[0]).lower()
            page = False
            if len(commands) > 1:
                if str(commands[1]) == "|":
                    page = True
            self.bookmarks.info(alias, page)
        else:
            self.help_info()

    def do_list(self, args):
        """Output a list of bookmarks.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            view = str(args).strip()
            if view.endswith('|'):
                view = view[:-1].strip()
                page = True
            else:
                page = False
            self.bookmarks.list(view, page)
        else:
            self.help_list()

    def do_modify(self, args):
        """Modify a bookmark.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            alias = str(commands[0]).lower()
            uid = self._uid_from_alias(alias)
            if not uid:
                print(f"Alias '{alias}' not found")
            else:
                subshell = ModShell(self.bookmarks, uid, alias)
                subshell.cmdloop()
        else:
            self.help_modify()

    def do_new(self, args):
        """Evoke the new bookmark wizard.

        Args:
            args (str): the command arguments, ignored.

        """
        try:
            self.bookmarks.new_bookmark_wizard()
        except KeyboardInterrupt:
            print("\nCancelled.")

    def do_open(self, args):
        """Open a bookmark in the browser.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.bookmarks.open(str(commands[0]).lower())
        else:
            self.help_open()

    def do_refresh(self, args):
        """Refresh bookmark information if files changed on disk.

        Args:
            args (str): the command arguments, ignored.

        """
        self.bookmarks.refresh()
        if args != 'silent':
            print("Data refreshed.")

    def do_search(self, args):
        """Search for bookmarks that meet certain criteria.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            term = str(args).strip()
            if term.endswith('|'):
                term = term[:-1].strip()
                page = True
            else:
                page = False
            self.bookmarks.search(term, page)
        else:
            self.help_search()

    def help_archive(self):
        """Output help for 'archive' command."""
        print(
            '\narchive <alias>:\n'
            f'    Archive a bookmark file to {self.bookmarks.data_dir}'
            '/archive.\n'
        )

    @staticmethod
    def help_clear():
        """Output help for 'clear' command."""
        print(
            '\nclear:\n'
            '    Clear the terminal window.\n'
        )

    @staticmethod
    def help_config():
        """Output help for 'config' command."""
        print(
            '\nconfig:\n'
            '    Edit the config file with $EDITOR and then reload '
            'the configuration and refresh data files.\n'
        )

    @staticmethod
    def help_delete():
        """Output help for 'delete' command."""
        print(
            '\ndelete (rm) <alias>:\n'
            '    Delete a bookmark file.\n'
        )

    @staticmethod
    def help_edit():
        """Output help for 'edit' command."""
        print(
            '\nedit <alias>:\n'
            '    Edit a bookmark file with $EDITOR.\n'
        )

    @staticmethod
    def help_exit():
        """Output help for 'exit' command."""
        print(
            '\nexit:\n'
            '    Exit the bookmarks shell.\n'
        )

    @staticmethod
    def help_info():
        """Output help for 'info' command."""
        print(
            '\ninfo <alias>:\n'
            '    Show info about a bookmark.\n'
        )

    @staticmethod
    def help_list():
        """Output help for 'list' command."""
        print(
            '\nlist (ls) <view> [|]:\n'
            '    List bookmarks using one of the views \'all\', '
            '\'tags\', \'<alias>\', or \'<tag>\'. '
            'Add \'|\' as a second argument to page the output.\n\n'
            '    The following command shortcuts are available:\n\n'
            '      lsa  : list all\n'
            '      lst  : list tags\n'
        )

    @staticmethod
    def help_modify():
        """Output help for 'modify' command."""
        print(
            '\nmodify <alias>:\n'
            '    Modify a bookmark.\n'
        )

    @staticmethod
    def help_new():
        """Output help for 'new' command."""
        print(
            '\nnew:\n'
            '    Create new bookmark interactively.\n'
        )

    @staticmethod
    def help_open():
        """Output help for 'open' command."""
        print(
            '\nopen <alias>:\n'
            '    Open a bookmark in your browser.\n'
        )

    @staticmethod
    def help_refresh():
        """Output help for 'refresh' command."""
        print(
            '\nrefresh:\n'
            '    Refresh the bookmark information from files on disk. '
            'This is useful if changes were made to files outside of '
            'the program shell (e.g. sync\'d from another computer).\n'
        )

    @staticmethod
    def help_search():
        """Output help for 'search' command."""
        print(
            '\nsearch <term>:\n'
            '    Search for one or more bookmarks that meet some specified '
            'criteria.\n'
        )


class ModShell(Cmd):
    """Subshell for modifying a bookmark.

    Attributes:
        bookmarks (obj):    an instance of Bookmarks().
        uid (str):          the uid of the bookmark being modified.
        alias (str):        the alias of the bookmark being modified.

    """
    def __init__(
            self,
            bookmarks,
            uid,
            alias,
            completekey='tab',
            stdin=None,
            stdout=None):
        """Initializes a ModShell() object."""
        super().__init__()
        self.bookmarks = bookmarks
        self.uid = uid
        self.alias = alias

        # class overrides for Cmd
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.completekey = completekey
        self.doc_header = (
            "Commands (for more info type: help):"
        )
        self.ruler = "―"

        self._set_prompt()

        self.nohelp = (
            "\nNo help for %s\n"
        )

    # class method overrides
    def default(self, args):
        """Handle command aliases and unknown commands.

        Args:
            args (str): the command arguments.

        """
        if args.startswith("quit") or args.startswith("exit"):
            return True
        else:
            print("\nNo such command. See 'help'.\n")

    @staticmethod
    def emptyline():
        """Ignore empty line entry."""

    def _get_aliases(self):
        """Generates a list of all bookmark aliases.

        Returns:
            aliases (list): the list of all bookmark aliases.

        """
        aliases = []
        for bookmark in self.bookmarks.bookmarks:
            alias = self.bookmarks.bookmarks[bookmark].get('alias')
            if alias:
                aliases.append(alias.lower())
        return aliases

    def _set_prompt(self):
        """Set the prompt string."""
        if self.bookmarks.color_bold:
            self.prompt = f"\033[1mmodify ({self.alias})\033[0m> "
        else:
            self.prompt = f"modify ({self.alias})> "

    def do_alias(self, args):
        """Change the alias of a bookmark.

        Args:
            args (str): the command arguments.

        """
        commands = args.split()
        if len(commands) > 0:
            aliases = self._get_aliases()
            newalias = str(commands[0]).lower()
            if newalias in aliases:
                self._error_pass(
                        f"alias '{newalias}' already in use")
            else:
                self.bookmarks.modify(
                    alias=self.alias,
                    new_alias=newalias)
                self.alias = newalias
                self._set_prompt()
        else:
            self.help_alias()

    @staticmethod
    def do_clear(args):
        """Clear the terminal.

        Args:
            args (str): the command arguments, ignored.

        """
        os.system("cls" if os.name == "nt" else "clear")

    def do_description(self, args):
        """Modify the description on a bookmark.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            description = str(args)
            self.bookmarks.modify(
                alias=self.alias,
                new_description=description)
        else:
            self.help_description()

    @staticmethod
    def do_done(args):
        """Exit the modify subshell.

        Args:
            args (str): the command arguments, ignored.

        """
        return True

    def do_info(self, args):
        """Display full details for the selected bookmark.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            if str(commands[0]) == "|":
                self.bookmarks.info(self.alias, True)
            else:
                self.bookmarks.info(self.alias)
        else:
            self.bookmarks.info(self.alias)

    def do_tags(self, args):
        """Modify the tags on a bookmark.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            tags = str(commands[0])
            self.bookmarks.modify(
                alias=self.alias,
                new_tags=tags)
        else:
            self.help_tags()

    def do_title(self, args):
        """Modify the title on a bookmark.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            title = str(args)
            self.bookmarks.modify(
                alias=self.alias,
                new_title=title)
        else:
            self.help_title()

    def do_unset(self, args):
        """Clear a field on the bookmark.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            if len(commands) > 2:
                self.help_unset()
            else:
                field = str(commands[0]).lower()
                allowed_fields = [
                        'tags',
                        'description'
                ]
                if field in allowed_fields:
                    self.bookmarks.unset(self.alias, field)
                else:
                    self.help_unset()
        else:
            self.help_unset()

    def do_url(self, args):
        """Modify the url on a bookmark.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            url = str(args)
            self.bookmarks.modify(
                alias=self.alias,
                new_url=url)
        else:
            self.help_url()

    @staticmethod
    def help_alias():
        """Output help for 'alias' command."""
        print(
            '\nalias <alias>:\n'
            '    Modify the alias of this bookmark.\n'
        )

    @staticmethod
    def help_clear():
        """Output help for 'clear' command."""
        print(
            '\nclear:\n'
            '    Clear the terminal window.\n'
        )

    @staticmethod
    def help_description():
        """Output help for 'description' command."""
        print(
            '\ndescription <description>:\n'
            '    Modify the description of this bookmark.\n'
        )

    @staticmethod
    def help_done():
        """Output help for 'done' command."""
        print(
            '\ndone:\n'
            '    Finish modifying the bookmark.\n'
        )

    @staticmethod
    def help_info():
        """Output help for 'info' command."""
        print(
            '\ninfo [|]:\n'
            '    Display details for the bookmark. Add "|" as an'
            'argument to page the output.\n'
        )

    @staticmethod
    def help_tags():
        """Output help for 'tags' command."""
        print(
            '\ntags <tag>[,tag]:\n'
            '    Modify the tags on this bookmark. A comma-delimted '
            'list or you may use the + and ~ notations to add or delete '
            'a tag from the existing tags.\n'
        )

    @staticmethod
    def help_title():
        """Output help for 'title' command."""
        print(
            '\ntitle <title>:\n'
            '    Modify the title of this bookmark.\n'
        )

    @staticmethod
    def help_unset():
        """Output help for 'unset' command."""
        print(
            '\nunset <alias> <field>:\n'
            '    Clear a specified field of the bookmark. The field may '
            'be one of the following: tags or description.\n'
        )

    @staticmethod
    def help_url():
        """Output help for 'url' command."""
        print(
            '\nurl <url>:\n'
            '    Modify the url of this bookmark.\n'
        )


def parse_args():
    """Parse command line arguments.

    Returns:
        args (dict):    the command line arguments provided.

    """
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description='Terminal-based bookmark management for nerds.')
    parser._positionals.title = 'commands'
    parser.set_defaults(command=None)
    subparsers = parser.add_subparsers(
        metavar=f'(for more help: {APP_NAME} <command> -h)')
    pager = subparsers.add_parser('pager', add_help=False)
    pager.add_argument(
        '-p',
        '--page',
        dest='page',
        action='store_true',
        help="page output")
    archive = subparsers.add_parser(
        'archive',
        help='archive a bookmark')
    archive.add_argument(
        'alias',
        help='bookmark alias')
    archive.add_argument(
        '-f',
        '--force',
        dest='force',
        action='store_true',
        help="archive without confirmation")
    archive.set_defaults(command='archive')
    config = subparsers.add_parser(
        'config',
        help='edit configuration file')
    config.set_defaults(command='config')
    delete = subparsers.add_parser(
        'delete',
        aliases=['rm'],
        help='delete a bookmark file')
    delete.add_argument(
        'alias',
        help='bookmark alias')
    delete.add_argument(
        '-f',
        '--force',
        dest='force',
        action='store_true',
        help="delete without confirmation")
    delete.set_defaults(command='delete')
    edit = subparsers.add_parser(
        'edit',
        help='edit a bookmark file (uses $EDITOR)')
    edit.add_argument(
        'alias',
        help='bookmark alias')
    edit.set_defaults(command='edit')
    info = subparsers.add_parser(
        'info',
        parents=[pager],
        help='show info about a bookmark')
    info.add_argument(
        'alias',
        help='the bookmark to view')
    info.set_defaults(command='info')
    listcmd = subparsers.add_parser(
        'list',
        aliases=['ls'],
        parents=[pager],
        help='list bookmarks')
    listcmd.add_argument(
        'view',
        help='list view (\'all\', alias, or tag)')
    listcmd.set_defaults(command='list')
    # list shortcuts
    lsa = subparsers.add_parser('lsa', parents=[pager])
    lsa.set_defaults(command='lsa')
    lst = subparsers.add_parser('lst', parents=[pager])
    lst.set_defaults(command='lst')
    modify = subparsers.add_parser(
        'modify',
        aliases=['mod'],
        help='modify a bookmark')
    modify.add_argument(
        'alias',
        help='the bookmark to modify')
    modify.add_argument(
        '--description',
        metavar='<description>',
        help='bookmark description')
    modify.add_argument(
        '--new-alias',
        metavar='<alias>',
        dest='new_alias',
        help='new bookmark alias')
    modify.add_argument(
        '--tags',
        metavar='<tag>[,tag]',
        help='bookmark tag(s)')
    modify.add_argument(
        '--title',
        metavar='<title>',
        help='bookmark description')
    modify.add_argument(
        '--url',
        metavar='<url>',
        help='bookmarks location')
    modify.set_defaults(command='modify')
    new = subparsers.add_parser(
        'new',
        help='create a new bookmark')
    new.add_argument(
        'url',
        help='bookmark URL')
    new.add_argument(
        '--description',
        metavar='<description>',
        help='bookmark description')
    new.add_argument(
        '--tags',
        metavar='<tag>[,tag]',
        help='bookmark tag(s)')
    new.add_argument(
        '--title',
        metavar='<title>',
        help='bookmark description')
    new.set_defaults(command='new')
    opencmd = subparsers.add_parser(
        'open',
        help='open a bookmark')
    opencmd.add_argument(
        'alias',
        help='the bookmark to open')
    opencmd.add_argument(
        '-n',
        '--new-window',
        dest='new_window',
        action='store_true',
        help='open bookmark in a new browser window')
    opencmd.set_defaults(command='open')
    query = subparsers.add_parser(
        'query',
        help='search bookmarks with structured text output')
    query.add_argument(
        'term',
        help='search term')
    query.add_argument(
        '-j',
        '--json',
        dest='json',
        action='store_true',
        help="output as JSON rather than TSV")
    query.add_argument(
        '-l',
        '--limit',
        dest='limit',
        help='limit output to specific field(s)')
    query.set_defaults(command='query')
    search = subparsers.add_parser(
        'search',
        parents=[pager],
        help='search bookmarks')
    search.add_argument(
        'term',
        help='search term')
    search.set_defaults(command='search')
    shell = subparsers.add_parser(
        'shell',
        help='interactive shell')
    shell.set_defaults(command='shell')
    unset = subparsers.add_parser(
        'unset',
        help='clear a field from a specified bookmark')
    unset.add_argument(
        'alias',
        help='bookmark alias')
    unset.add_argument(
        'field',
        help='field to clear')
    unset.set_defaults(command='unset')
    version = subparsers.add_parser(
        'version',
        help='show version info')
    version.set_defaults(command='version')
    parser.add_argument(
        '-c',
        '--config',
        dest='config',
        metavar='<file>',
        help='config file')
    args = parser.parse_args()
    return parser, args


def main():
    """Entry point. Parses arguments, creates Bookmarks() object, calls
    requested method and parameters.
    """
    if os.environ.get("XDG_CONFIG_HOME"):
        config_file = os.path.join(
            os.path.expandvars(os.path.expanduser(
                os.environ["XDG_CONFIG_HOME"])), APP_NAME, "config")
    else:
        config_file = os.path.expandvars(
            os.path.expanduser(DEFAULT_CONFIG_FILE))

    if os.environ.get("XDG_DATA_HOME"):
        data_dir = os.path.join(
            os.path.expandvars(os.path.expanduser(
                os.environ["XDG_DATA_HOME"])), APP_NAME)
    else:
        data_dir = os.path.expandvars(
            os.path.expanduser(DEFAULT_DATA_DIR))

    parser, args = parse_args()

    if args.config:
        config_file = os.path.expandvars(
            os.path.expanduser(args.config))

    bookmarks = Bookmarks(
        config_file,
        data_dir,
        DEFAULT_CONFIG)

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)
    elif args.command == "config":
        bookmarks.edit_config()
    elif args.command == "list":
        bookmarks.list(args.view, pager=args.page)
    elif args.command == "lsa":
        bookmarks.list('all', pager=args.page)
    elif args.command == "lst":
        bookmarks.list('tags', pager=args.page)
    elif args.command == "modify":
        bookmarks.modify(
            alias=args.alias,
            new_alias=args.new_alias,
            new_title=args.title,
            new_description=args.description,
            new_url=args.url,
            new_tags=args.tags)
    elif args.command == "new":
        bookmarks.new(
            url=args.url,
            title=args.title,
            description=args.description,
            tags=args.tags)
    elif args.command == "delete":
        bookmarks.delete(args.alias, args.force)
    elif args.command == "edit":
        bookmarks.edit(args.alias)
    elif args.command == "info":
        bookmarks.info(args.alias, args.page)
    elif args.command == "open":
        bookmarks.open(args.alias, new_window=args.new_window)
    elif args.command == "archive":
        bookmarks.archive(args.alias, args.force)
    elif args.command == "search":
        bookmarks.search(args.term, args.page)
    elif args.command == "query":
        bookmarks.query(
            args.term,
            limit=args.limit,
            json_output=args.json)
    elif args.command == "unset":
        bookmarks.unset(args.alias, args.field)
    elif args.command == "shell":
        bookmarks.interactive = True
        shell = BookmarksShell(bookmarks)
        shell.cmdloop()
    elif args.command == "version":
        print(f"{APP_NAME} {APP_VERS}")
        print(APP_COPYRIGHT)
        print(APP_LICENSE)
    else:
        sys.exit(1)


# entry point
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
