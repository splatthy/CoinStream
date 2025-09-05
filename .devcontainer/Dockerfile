# Development container for Crypto Trading Journal
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    vim \
    nano \
    htop \
    tree \
    jq \
    gcc \
    g++ \
    make \
    build-essential \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Set up Python environment
RUN pip install --upgrade pip setuptools wheel

# Install development dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Install additional development tools
RUN pip install \
    black \
    flake8 \
    mypy \
    isort \
    pytest \
    pytest-cov \
    pytest-mock \
    pre-commit \
    jupyter \
    ipython \
    debugpy

# Install Docker CLI for Docker-in-Docker
RUN curl -fsSL https://get.docker.com | sh

# Switch to non-root user
USER $USERNAME

# Set up shell environment
RUN echo 'alias ll="ls -la"' >> ~/.bashrc \
    && echo 'alias la="ls -la"' >> ~/.bashrc \
    && echo 'alias ..="cd .."' >> ~/.bashrc \
    && echo 'export PYTHONPATH=/workspace' >> ~/.bashrc

# Set working directory
WORKDIR /workspace

# Configure git (will be overridden by user's git config)
RUN git config --global init.defaultBranch main \
    && git config --global pull.rebase false

# Set up pre-commit hooks template
COPY .devcontainer/pre-commit-config.yaml /tmp/.pre-commit-config.yaml

# Default command
CMD ["bash"]