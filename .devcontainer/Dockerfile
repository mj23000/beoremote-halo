# pull image
FROM debian:13.7-slim

RUN apt update && apt upgrade -y
RUN apt install git npm curl shellcheck -y

# Install uv for all users
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh

# Install AsyncAPI generator
RUN npm install -g @asyncapi/cli@6.2.2

# Run as a regular user rather than root, so files created in the workspace are owned by the host user.
# On Linux, the Dev Containers extension changes the user's UID and GID to match the host user's
ARG USERNAME=vscode
RUN groupadd --gid 1000 $USERNAME && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash $USERNAME
USER $USERNAME

RUN asyncapi config analytics --disable
