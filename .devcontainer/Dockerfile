# pull image
FROM debian:13.5-slim

RUN apt update && apt upgrade -y
RUN apt install git npm curl -y

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install AsyncAPI generator
RUN npm install -g @asyncapi/cli@4.1.1
RUN asyncapi config analytics --disable