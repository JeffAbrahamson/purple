#!/usr/bin/python

"""
Choose a campaign at random.  Return the chosen line from the campaign file.
"""

from random import randint

def main():
    """Do what we do."""
    lines = []
    with open("campaigns.txt", "r") as f:
        for line in f:
            if len(line) != 1 and line[0] != '#':
                lines.append(line[:-1])
    print lines[randint(0, len(lines) - 1)]

if __name__ == '__main__':
    main()

