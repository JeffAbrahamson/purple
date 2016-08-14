#!/bin/bash

PATH=/usr/bin:/bin

# Test purple.py by running against test_in/ and confirming that we
# get what we expect (the contents of test_out_golden/ ).

if [ ! -e purple.py ]; then
    echo "Can't find purple.py.  Is this the right directory?"
    exit 1
fi

if [ -e test_out ]; then
    if [ ! -d test_out ]; then
	echo The file test_out is not a directory.  Aborting.
	exit 1
    fi
    echo Start with a clean slate: removing test_out.
    rm -rf test_out
fi
mkdir test_out

./purple.py --config test_in/config --src test_in/src --dst test_out
diff --recursive test_out test_out_golden
status=$?
if [ $status != 0 ]; then
    echo "== Failed =="
else
    echo "== Success =="
fi
exit $status
