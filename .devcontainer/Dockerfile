# pull image
FROM alpine:3.22.4

RUN apk update
RUN apk add uv git bash npm

RUN npm install -g @asyncapi/cli@4.1.1
RUN asyncapi config analytics --disable