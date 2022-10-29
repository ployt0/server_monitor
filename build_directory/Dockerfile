FROM debian:bullseye-20221004-slim

ENV newusername=testrunner

RUN apt-get update && apt-get install -y \
    nginx openssh-server sudo python3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# For development we'd add vim procps iproute2 to the above.


RUN adduser --disabled-password --gecos "" $newusername && \
    echo "$newusername ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$newusername && \
    mkdir /home/$newusername/.ssh && \
    chown -R $newusername:$newusername /home/$newusername/.ssh && \
    chmod 700 /home/$newusername/.ssh

COPY rsa_key.pub /home/$newusername/.ssh/authorized_keys
COPY dhparam.pem /etc/nginx/dhparam.pem
COPY nginx-ssl-params.conf /etc/nginx/snippets/ssl-params.conf

EXPOSE 22 80 443

CMD service ssh start && nginx -g 'daemon off;'
