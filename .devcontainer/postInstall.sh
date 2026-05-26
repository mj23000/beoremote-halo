#!/bin/bash

# Install development dependencies
apt install shellcheck -y

# Install Python dependencies
uv sync --dev