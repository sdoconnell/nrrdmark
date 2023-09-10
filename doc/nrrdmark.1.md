---
title: NRRDMARK
section: 1
header: User Manual
footer: nrrdmark 0.0.2
date: January 3, 2022
---
# NAME
nrrdmark - Terminal-based bookmark management for nerds.

# SYNOPSIS
**nrrdmark** *command* [*OPTION*]...

# DESCRIPTION
**nrrdmark** is a terminal-based bookmark management program with advanced search options, and data stored in local text files. It can be run in either of two modes: command-line or interactive shell.

# OPTIONS
**-h**, **--help**
: Display help information.

**-c**, **--config** *file*
: Use a non-default configuration file.

# COMMANDS
**nrrdmark** provides the following commands.

**archive** *alias* [*OPTION*]
: Move a bookmark to the archive directory of your data directory (by default, $HOME/.local/share/nrrdmark/archive). The user will be prompted for confirmation. Archiving a bookmark removes it from all lists, and is designed as a method to save old bookmarks while removing them from **list** output.

    *OPTIONS*

    **-f**, **--force**
    : Force the archive operation, do not prompt for confirmation.

**config**
: Edit the **nrrdmark** configuration file.

**delete (rm)** *alias* [*OPTION*]
: Delete a bookmark file. The user will be prompted for confirmation.

    *OPTIONS*

    **-f**, **--force**
    : Force deletion, do not prompt for confirmation.

**edit** *alias*
: Edit or view a bookmark file (opens in $EDITOR). If $EDITOR is not defined, an error message will report that.

**info** *alias* [*OPTION*]
: Show the full metadata about a bookmark.

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.

**list (ls)** *view* [*OPTION*]
: List bookmarks matching one of the following views:

    - *all* (*lsa*) : All bookmarks.
    - *tags* (*lst*) : A list of tags, with a count of matching bookmarks.
    - \<*tag*\> : All bookmarks with a specific tag.
    - \<*alias*\> : A specific bookmark alias.

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.

**modify (mod)** *alias* [*OPTION*]...
: Modify the metadata for a bookmark.

    *OPTIONS*

    **--description** *description*
    : The bookmark description.

    **--new-alias** *alias*
    : Change the alias for a bookmark.

    **--tags** *tag*[,*tag*]
    : Tags assigned to the bookmark. This can be a single tag or multiple tags in a comma-delimited list. Normally with this option, any existing tags assigned to the bookmark will be replaced. However, this option also supports two special operators: **+** (add a tag to the existing tags) and **~** (remove a tag from the existing tags). For example, *--tags +documentation* will add the *documentation* tag to the existing tags on a bookmark, and *--tags ~testing,experimental* will remove both the *testing* and *experimental* tags from a bookmark.

    **--title** *title*
    : The bookmark title.

    **--url** *url*
    : The bookmark url.

**new** *url* [*OPTION*]...
: Create a new bookmark. If *description* and/or *title* are not provided, **nrrdmark** will attempt to access the URL and read title and description information from the website.

    *OPTIONS*

    **--description**
    : The bookmark description.

    **--tags**
    : Tags assigned to the bookmark. See the **--tags** option of **modify**.

    **--title**
    : The bookmark title.

**open** *alias* [*OPTION*]
: Open a bookmark in a web browser (either defined by the *browser_cmd* command config option, or the detected system default web browser).

    *OPTIONS*

    **-n**, **--new-window**
    : Try to open the bookmark in a new browser window, rather than a new tab in the existing window.

**query** *searchterm* [*OPTION*]...
: Search for one or more bookmarks and produce plain text output (by default, tab-delimited text).

    *OPTIONS*

    **-l**, **--limit**
    : Limit the output to one or more specific fields (provided as a comma-delimited list).

    **-j**, **--json**
    : Output in JSON format rather than the default tab-delimited format.

**search** *searchterm* [*OPTION*]
: Search for one or more bookmarks and output a tabular list (same format as **list**). 

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.


**shell**
: Launch the **nrrdmark** interactive shell.

**version**
: Show the application version information.

# NOTES

## Archiving a bookmark
Use the **archive** subcommand to move the bookmark file to the subdirectory archive in the the bookmarks data directory. Confirmation will be required for this operation unless the *--force* option is also used.

Archived bookmarks will no longer appear in lists of bookmarks. This can be useful for retaining old bookmarks without resulting in endlessly growing bookmark lists. To review archived bookmarks, create an alterate config file with a *data_dir* pointing to the archive folder, and an alias such as:

    alias nrrdmark-archive="nrrdmark -c $HOME/.config/nrrdmark/config.archive"

## Search and query
There are two command-line methods for filtering the presented list of bookmarks: **search** and **query**. These two similar-sounding functions perform very different roles.

Search results are output in the same tabular, human-readable format as that of **list**. Query results are presented in the form of tab-delimited text (by default) or JSON (if using the *-j* or *--json* option) and are primarily intended for use by other programs that are able to consume structured text output.

**search** and **query** use the same filter syntax. The most basic form of filtering is to simply search for a keyword or string in the bookmark title, description, and/or url:

    nrrdmark search <search_term>

**NOTE:** search terms are case-insensitive.

If the search term is present in either the bookmark *title*, *description*, or *url*, the bookmark will be displayed.

Optionally, a search type may be specified. The search type may be one of *uid*, *alias*, *description*, *tags*, *title*, or *url*. If an invalid search type is provided, the search will ignore it. To specify a search type, use the format:

    nrrdmark search [search_type=]<search_term>

You may combine search types in a comma-delimited structure. All search criteria must be met to return a result.

The tags search type may also use the optional **+** operator to search for more than one tag. Any matched tag will return a result.

The special search term *any* can be used to match all bookmarks, but is only useful in combination with an exclusion to match all records except those excluded.

## Exclusion
In addition to the search term, an exclusion term may be provided. Any match in the exclusion term will negate a match in the search term. An exclusion term is formatted in the same manner as the search term, must follow the search term, and must be denoted using the **%** operator:

    nrrdmark search [search_type=]<search_term>%[exclusion_type=]<exclusion_term>

## Search examples
Search for any bookmark with "projectx" in the title, description, or URL:

    nrrdmark search projectx

Search for any bookmark with "projectx" specifically in the title:

    nrrdmark search title=projectx

Search for all bookmarks tagged "development" or "testing" with a title containing "projectx", except for those that have 'domain.tld' in the URL:

    nrrdmark search title=projectx,tags=development+testing%url=domain.tld

## Query and limit
The query function uses the same syntax as search but will output information in a form that may be read by other programs. The standard fields returned by query for tab-delimited output are:

    - uid (string)
    - alias (string)
    - title (string)
    - url (string)
    - tags (list)

List fields are returned in standard Python format: ['item 1', 'item 2', ...]. Empty lists are returned as []. Empty string fields will appear as multiple tabs.

JSON output returns all fields for a record, including fields not provided in tab-delimited output.

The query function may also use the **--limit** (**-l**) option. This is a comma-separated list of fields to return. The **--limit** option does not have an effect on JSON output.

## Paging
Output from **list** and **search** can get long and run past your terminal buffer. You may use the **-p** or **--page** option in conjunction with **search**, **info**, or **list** to page output.

# FILES
**~/.config/nrrdmark/config**
: Default configuration file

**~/.local/share/nrrdmark**
: Default data directory

# AUTHORS
Written by Sean O'Connell <https://sdoconnell.net>.

# BUGS
Submit bug reports at: <https://github.com/sdoconnell/nrrdmark/issues>

# SEE ALSO
Further documentation and sources at: <https://github.com/sdoconnell/nrrdmark>
