# Start from the CUDA base image
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8

# Set the locale to prevent issues with encoding
# Install git
# Clone the GitHub repository into the continual_rl directory in the container
RUN apt-get clean && apt-get update && \
    apt-get install -y git ffmpeg libsm6 libxext6 locales python3 python3-pip && \
    locale-gen en_US.UTF-8 && \
    git clone https://github.com/parthraut/continual_rl.git continual_rl

# Set the working directory to the continual_rl directory
WORKDIR /continual_rl

RUN pip3 install --upgrade pip && \
    pip3 install torch>=1.7.1 torchvision && \
    pip3 install -e .

# Environment variables
ENV OMP_NUM_THREADS=1 \
    CUDA_VISIBLE_DEVICES=0 \
    PYTHONUNBUFFERED=1

# Expose port 80
EXPOSE 80