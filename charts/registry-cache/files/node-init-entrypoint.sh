#!/bin/bash
echo "Starting node init script."
pip install \
    tomli==2.0.1 \
    tomli-w==1.0.0 \
    kubernetes==30.1.0 && \
python3 /opt/vessl/node-init.py
echo "Finished node init script with exit code $?."
sleep infinity
