#!/usr/bin/env bash

# https://www.gnu.org/software/bash/manual/bash.html#The-Set-Builtin
# -e  Exit immediately if a command exits with a non-zero status.
# -x Print commands and their arguments as they are executed.
set -e

REPORTS_FOLDER_PATH=tests-reports

coverage erase
coverage run --source='.' manage.py test
coverage combine
coverage report
coverage html -d $REPORTS_FOLDER_PATH/html
coverage xml -o $REPORTS_FOLDER_PATH/coverage.xml