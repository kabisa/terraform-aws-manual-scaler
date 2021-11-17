#!/usr/bin/env bash
# https://dev.to/fferegrino/creating-an-aws-lambda-using-pipenv-2h4a
# This script expects you have a virtual env with all libs installed already
# it will extract the versions you've got installed and adds those to the
# lambda zip.
set -e
mkdir -p build
pip freeze > ./build/requirements.txt
cp *.py build
docker run --rm -v ${PWD}/build:/var/task \
    -u 0 lambci/lambda\:build-python3.8 \
    python3.8 -m pip install -t /var/task/ -r /var/task/requirements.txt
cd build && zip -r ../lambda.zip *