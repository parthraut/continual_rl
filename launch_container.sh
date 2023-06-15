#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# The exit status of the last command that threw a non-zero exit code is returned
set -o pipefail

docker run -it --gpus "device=1" --net=host -e DISPLAY=:<4> -v /tmp/.X11-unix/:/tmp/.X11-unix  <REPOSITORY:TAG>
