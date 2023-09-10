#!/usr/bin/env bash

# nm_rofi.sh
# Version: 0.0.1
# Author: Sean O'Connell <sean@sdoconnell.net>
# License: MIT
# Homepage: https://github.com/sdoconnell/nrrdmark
# About:
# This is a rofi[1] interface script to nrrdmark, derived heavily from
# the work done by Rasmus Steinke on buku_run[2]. This script is for
# demonstration purposes only, and is not a supported component of the
# nrrdmark application.

# [1] https://github.com/davatorium/rofi
# [2] https://github.com/carnager/buku_run

# Copyright © 2021 Sean O'Connell
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.


_rofi () {
    rofi -dmenu -i -no-levenshtein-sort -width 1000 "$@"
}

_all_bookmarks () {
    nrrdmark query any -l alias,title,url,tags | tr -d "['" | tr -d "']" | sed "s/', '//g" | column -t -s $'\t'
}

_all_tags () {
    nrrdmark list tags | awk '{print $1}' | grep -v "^$" | tail -n +2
}

# display settings
display_type=1
max_str_width=80

# keybindings
switch_view="Alt+Tab"
new_bookmark="Alt+n"
actions="Alt+a"

# colors
help_color="#fabd2f"

main () {
    HELP="<span size='small' foreground='#7c6f64'><span color='${help_color}'>${new_bookmark}</span>:new  <span color='${help_color}'>${switch_view}</span>:view</span>"

    if [[ $mode == "bookmarks" ]]; then

        menu=$(_all_bookmarks | _rofi -p 'bookmark' -filter "${filter}" -mesg "${HELP}" -kb-custom-1 "${new_bookmark}" -kb-custom-2 "${switch_view}")

    elif [[ $mode == "tags" ]]; then

        menu=$(_all_tags | _rofi -p 'bookmark' -mesg "${HELP}" -kb-custom-1 "${new_bookmark}" -kb-custom-2 "${switch_view}")

    fi

    val=$?
    if [[ $val -eq 1 ]]; then
        exit
    elif [[ $val -eq 10 ]]; then
        _add_bookmark
    elif [[ $val -eq 11 ]]; then
        if [[ $mode == "bookmarks" ]]; then
            export mode="tags"
            mode=tags main
        elif [[ $mode == "tags" ]]; then
            export mode="bookmarks"
            filter="${menu}" mode=bookmarks main
        fi
    elif [[ $val -eq 0 ]]; then
        if [[ $mode == "bookmarks" ]]; then
            alias=$(echo "$menu" | awk '{print $1}')
            nrrdmark open $alias
        elif [[ $mode == "tags" ]]; then
            filter="${menu}" mode="bookmarks" main
        fi
    fi
}

_add_bookmark () {
    inserturl=$(echo -e "$(xclip -o)" | _rofi -p 'bookmark' -mesg "<span size='small' foreground='#7c6f64'>Use URL below or type manually</span>")
    val=$?
    if [[ $val -eq 1 ]]; then
        exit
    elif [[ $val -eq 0 ]]; then
        _add_tags
    fi
}

_add_tags () {
    inserttags=$(_all_tags | _rofi -p 'bookmark' -mesg "Add some tags. Separate tags with ','")
    val=$?
    if [[ $val -eq 1 ]]; then
        exit
    elif [[ $val -eq 0 ]]; then
        if [[ $(echo "${inserttags}" | wc -l) -gt 1 ]]; then
            taglist=$(echo "${inserttags}" | tr '\n' ',')
            tags=()
            for tag in $taglist; do
                tags+=("$tag")
            done
        else
            tags=${inserttags}
        fi
        
        nrrdmark new "${inserturl}" --tags "${tags}"
    fi
}

mode=bookmarks main
