#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# The exit status of the last command that threw a non-zero exit code is returned
set -o pipefail

docker run -it --ipc=host --gpus "device=all" --net=host -e DISPLAY=:15 -v /tmp/.X11-unix/:/tmp/.X11-unix cora-pip:latest


# Display cookie: sled-snowbird.eecs.umich.edu/unix:3  MIT-MAGIC-COOKIE-1  c159484a7d9262bba1a233b87258f608
# sled-whistler/unix:15  MIT-MAGIC-COOKIE-1  6df1e06796c8724d64de6f841958bad2

