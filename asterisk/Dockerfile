FROM ubuntu:24.04 AS builder

ENV AST_VERSION=22

RUN set -ex; \
    apt-get update; \
    export DEBIAN_FRONTEND=noninteractive DEBCONF_NONINTERACTIVE_SEEN=true; \
    apt-get install -y --no-install-recommends \
        software-properties-common \
        build-essential pkg-config \
        wget subversion bzip2 patch \
        wget sox tzdata libedit2 libjansson4 libsqlite3-0 libuuid1 libxml2 uuid-runtime  jq curl liburiparser1 libgsm1 libcurl4 libcurl4-openssl-dev libssl-dev openssl libsrtp2-dev libsrtp2-1 \
        libedit-dev libjansson-dev libsqlite3-dev uuid-dev libxml2-dev  \
        build-essential git wget subversion   libjansson-dev libxml2-dev libncurses5-dev uuid-dev   libsqlite3-dev libedit-dev libssl-dev \
        liburiparser1 libgsm1 libcurl4-openssl-dev libssl-dev openssl libsrtp2-dev libsrtp2-1 git libncurses5-dev libxml2 libjansson4 libedit2 libcurl4; \
    cd /usr/src; \
    echo "check_certificate = off" >> ~/.wgetrc; \
    git clone --depth 1 https://github.com/asterisk/asterisk.git; \
    cd asterisk; \
    contrib/scripts/get_mp3_source.sh; \
    ./configure ; \
    make menuselect/menuselect menuselect-tree menuselect.makeopts; \
    menuselect/menuselect --enable format_mp3 menuselect.makeopts;  \
    make -j$(grep -c ^processor /proc/cpuinfo); \
    make install; \
    make samples; \
    make config; \
    ldconfig; \
    apt-get remove -y --purge --auto-remove build-essential software-properties-common lib*dev; \
    apt-get clean && rm -rf /var/lib/{apt,dpkg,cache,log}; \
    rm -rf /usr/src/${AST_VERSION}* && rm -rf /usr/src/asterisk*;




RUN sed -i 's/enabled = no/enabled = yes/' /etc/asterisk/manager.conf; \
    sed -i 's/rtpend=20000/rtpend=10050/' /etc/asterisk/rtp.conf; \
    sed -i 's/enabled = no/enabled = yes/' /etc/asterisk/prometheus.conf; \
    sed -i 's/;enabled=yes/enabled=yes/' /etc/asterisk/http.conf; \
    sed -i 's/bindaddr=127.0.0.1/bindaddr=0.0.0.0/' /etc/asterisk/http.conf;



ENV TZ=Europe/Rome
RUN set -ex; \
    echo $TZ > /etc/timezone; \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime;

# if need curl for Global Web
# RUN set -ex; \
#     apt-get install -y --no-install-recommends ca-certificates;

CMD [ "asterisk", "-f" ]