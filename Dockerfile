FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    wget \
    subversion \
    bzip2 \
    patch \
    sox \
    tzdata \
    libedit2 python3 python3-pip

WORKDIR /app

COPY . .

RUN pip3 install -r requirements.txt --break-system-packages

# pass the arguments to the entrypoint
ENTRYPOINT [ "python3", "ast_ws_server_example.py" ]