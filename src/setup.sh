#!/bin/bash
virtualenv --python=python3 venv
. venv/bin/activate
pip install -r requirements.txt
