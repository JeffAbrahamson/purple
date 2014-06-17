#!/bin/bash

present_index() {
    cp www/index-default.html www/index.html
}

present_cause() {
    cause=$(./select-cause.py)
    label=$(echo $cause | awk -F'|' '{print $1}')
    page=$(echo $cause | awk -F'|' '{print $2}')
    sed -e "s/Sponsored link:/Support purple causes/; s|advertise.html|causes/$page|; s/This is you/$label/;" \
	< templates/index.html > www/index.html
}

present_ad() {
    today=$(date '+%Y-%m-%d')
    label=$(egrep ^$today ads.txt | awk -F'\t' '{print $2}')
    if [ "X$label" = X ]; then
	return 1
    fi
    redirect=$(echo $label | tr ' ' '-').html
    url=$(egrep ^$today ads.txt | awk -F'\t' '{print $3}')
    sed -e "s|advertise.html|redirect/$redirect|; s/This is you/$label/;" < templates/index.html > www/index.html
    sed -e "s|go-here.html|$url|;" < templates/redirect.html > www/redirect/$redirect
    return 0
}

main() {
    if present_ad; then
	return
    fi
    if [ $(($RANDOM % 10)) = 0 ]; then
	present_cause
	return
    fi
    present_index
}

main
