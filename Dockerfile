# Start from the CUDA base image
FROM nvidia/cuda:11.6.2-devel-ubuntu20.04

ENV LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8 TZ=America/Detroit

# Set the locale to prevent issues with encoding
# Install git
# Clone the GitHub repository into the continual_rl directory in the container
RUN apt-get clean && apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    apt-get install -y git ffmpeg libsm6 libxext6 locales && \
    locale-gen en_US.UTF-8 && \
    apt-get install -y python3 python3-pip && \
    apt-get install wget && \
    apt-get install unzip

COPY . /continual_rl
# Set the working directory to the continual_rl directory
WORKDIR /continual_rl

# Install python packages
RUN pip3 install torch>=1.7.1 torchvision && \
    pip3 install -e . && \
    pip3 install ai2thor && \
    pip3 install ai2thor && \
    git clone https://github.com/etaoxing/crl_alfred --branch develop && \
    pip3 install -r crl_alfred/alfred/requirements.txt && \
    pip3 install -e crl_alfred/ && \
    wget -O cora_trajs.zip "https://onedrive.live.com/download?cid=601D311D0FC404D4&resid=601D311D0FC404D4%2155915&authkey=APSnA-AKY4Yw_vA" && \
    unzip cora_trajs.zip && \
    pip3 install procgen

# Environment variables
ENV OMP_NUM_THREADS=1 \
    CUDA_VISIBLE_DEVICES=0 \
    PYTHONUNBUFFERED=1

# Environment var - dependencies
ENV ALFRED_DATA_DIR=/continual_rl/cora_trajs

# Expose port 80
EXPOSE 80
