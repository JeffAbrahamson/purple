#!/bin/bash

## Insert an ad on the root purple page if an ad is scheduled to be run.
## If not, and if any causes are availble, consider inserting a cause.
## Otherwise, make sure the default page displays.
##
## This script assumes it is being run from the immediate parent
## directory of www/.

log_file=$HOME/index.log

present_index() {
    cp templates/index-default.html www/index.html
}

present_cause() {
    cause=$(./select-cause.py)
    label=$(echo $cause | awk -F'|' '{print $1}')
    page=$(echo $cause | awk -F'|' '{print $2}')
    sed -e "s/Sponsored link:/Support purple causes/; s|advertise.html|causes/$page|; s/This is you/$label/;" \
	< templates/index.html > www/index.html
}

offer_tshirt() {
    cp templates/index-tshirt.html www/index.html
}

present_ad() {
    today=$(date '+%Y-%m-%d')
    label=$(egrep ^$today ads.txt | awk -F'\t' '{print $2}')
    if [ "X$label" = X ]; then
	return 1
    fi
    echo $(date +%F) ad: "$label" >> $log_file
    redirect=$(echo $label | tr ' ' '-').html
    url=$(egrep ^$today ads.txt | awk -F'\t' '{print $3}')
    if [ -r "www/imageads/$label" ]; then
	sed -e "s|advertise.html|redirect/$redirect|; s/this-is-you.png/$label/;" < templates/index-imagead.html > www/index.html
	sed -e "s|go-here.html|$url|;" < templates/redirect.html > www/redirect/$redirect
    else
	sed -e "s|advertise.html|redirect/$redirect|; s/This is you/$label/;" < templates/index-textad.html > www/index.html
	sed -e "s|go-here.html|$url|;" < templates/redirect.html > www/redirect/$redirect
    fi
    return 0
}

main() {
    if present_ad; then
	return
    fi
    if [ $(($RANDOM % 10)) = 0 ]; then
	offer_tshirt
	echo $(date +%F) t-shirt >> $log_file
	return
    fi
#    if [ $(($RANDOM % 10)) = 0 ]; then
#	present_cause
#	echo $(date +%F) cause >> $log_file
#	return
#    fi
    present_index
    echo $(date +%F) index >> $log_file
}

main
