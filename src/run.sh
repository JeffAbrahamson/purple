#!/bin/bash

# Additional arguments are meant for flags like verbose and dryrun.
# For anything more complicated, just run purple.py by hand.

src/purple.py --src in --dst www --config config $*
