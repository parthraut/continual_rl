# Start from the CUDA base image
FROM nvidia/cuda:12.1.1-base-ubuntu20.04

# Set the working directory to /app in the container
WORKDIR /app

# Set the locale to prevent issues with encoding
RUN apt-get clean && apt-get update && apt-get install -y locales
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8

# Install Python, pip, and venv
RUN apt-get install -y python3 python3-pip python3-venv

# Copy the current directory (i.e. your project) into the container
COPY . /app

# Create a Python virtual environment and activate it
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Upgrade pip and install the project requirements
RUN pip install --upgrade pip
RUN pip install torch>=1.7.1 torchvision
RUN pip install -e .

# Set environment variables as per the instructions in the repository
ENV OMP_NUM_THREADS=1
ENV CUDA_VISIBLE_DEVICES=0
ENV PYTHONUNBUFFERED=1

EXPOSE 80

# Run the command to start the training for the project
CMD ["python", "main.py", "--config-file", "configs/atari/clear_atari.json", "--output-dir", "tmp"]