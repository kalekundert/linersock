#!/usr/bin/env sh

function run_tests () {
    python$1 -c 'import sys; print("Testing linersock with python{}.{}".format(*sys.version_info))'
    python$1 -m coverage run --source linersock test_everything.py
    [ $? -ne 0 ] && exit
    python$1 -m coverage html -d htmlcov$1
}

run_tests 2; echo
run_tests 3
