#/usr/bin/env bash
# bash completion for nrrdmark

shopt -s progcomp
_nrrdmark() {
    local cur prev firstword complete_options
    
    cur=$2
    prev=$3
	firstword=$(__get_firstword)

	GLOBAL_OPTIONS="\
        archive\
        config\
        delete\
        edit\
        info\
        list\
        modify\
        new\
        open\
        query\
        search\
        shell\
        unset\
        version\
        --config\
        --help"

    ARCHIVE_OPTIONS="--help --force"
    CONFIG_OPTIONS="--help"
    DELETE_OPTIONS="--help --force"
    EDIT_OPTIONS="--help"
    INFO_OPTIONS="--help --page"
    LIST_OPTIONS="--help --page"
    MODIFY_OPTIONS="--help"
    MOFIFY_OPTIONS_WA="\
        --description\
        --new-alias\
        --tags\
        --title\
        --url"
    NEW_OPTIONS="--help"
    NEW_OPTIONS_WA="\
        --description\
        --tags\
        --title"
    OPEN_OPTIONS="--help --new-window"
    QUERY_OPTIONS="--help --json"
    QUERY_OPTIONS_WA="--limit"
    SEARCH_OPTIONS="--help --page"
    SHELL_OPTIONS="--help"
    UNSET_OPTIONS="--help"
    VERSION_OPTIONS="--help"

	case "${firstword}" in
	archive)
		complete_options="$ARCHIVE_OPTIONS"
		complete_options_wa=""
		;;
	config)
		complete_options="$CONFIG_OPTIONS"
		complete_options_wa=""
		;;
	delete)
		complete_options="$DELETE_OPTIONS"
		complete_options_wa=""
		;;
	edit)
		complete_options="$EDIT_OPTIONS"
		complete_options_wa=""
		;;
	info)
		complete_options="$INFO_OPTIONS"
		complete_options_wa=""
		;;
	list)
		complete_options="$LIST_OPTIONS"
		complete_options_wa=""
		;;
	modify)
		complete_options="$MODIFY_OPTIONS"
		complete_options_wa="$MODIFY_OPTIONS_WA"
		;;
	new)
		complete_options="$NEW_OPTIONS"
		complete_options_wa="$NEW_OPTIONS_WA"
		;;
	open)
		complete_options="$OPEN_OPTIONS"
		complete_options_wa=""
		;;
	query)
		complete_options="$QUERY_OPTIONS"
		complete_options_wa="$QUERY_OPTIONS_WA"
		;;
	search)
		complete_options="$SEARCH_OPTIONS"
		complete_options_wa=""
		;;
 	shell)
		complete_options="$SHELL_OPTIONS"
		complete_options_wa=""
		;;
	unset)
		complete_options="$UNSET_OPTIONS"
		complete_options_wa=""
		;;
	version)
		complete_options="$VERSION_OPTIONS"
		complete_options_wa=""
		;;

	*)
        complete_options="$GLOBAL_OPTIONS"
        complete_options_wa=""
		;;
	esac


    for opt in "${complete_options_wa}"; do
        [[ $opt == $prev ]] && return 1 
    done

    all_options="$complete_options $complete_options_wa"
    COMPREPLY=( $( compgen -W "$all_options" -- $cur ))
	return 0
}

__get_firstword() {
	local firstword i
 
	firstword=
	for ((i = 1; i < ${#COMP_WORDS[@]}; ++i)); do
		if [[ ${COMP_WORDS[i]} != -* ]]; then
			firstword=${COMP_WORDS[i]}
			break
		fi
	done
 
	echo $firstword
}
 
complete -F _nrrdmark nrrdmark
