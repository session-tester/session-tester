FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y python3.13 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.13 1 && \
    apt-get install -y python3-pip && \
    pip install --upgrade pip && \
    pip install session-tester==0.1.0.dev16
