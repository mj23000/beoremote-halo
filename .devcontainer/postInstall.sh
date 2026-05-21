#!/bin/bash

# Install development dependencies
apk add shellcheck

# Install Python dependencies
uv sync --dev