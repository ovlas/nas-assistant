ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache util-linux e2fsprogs exfatprogs ntfs-3g

WORKDIR /opt/nas_assistant
COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

COPY app app
COPY web web
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
