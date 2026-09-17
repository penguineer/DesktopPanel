FROM mrtux/kivy-rpi-headless:2.1-bookworm-1

RUN mkdir -p /root/.kivy \
    && echo "[graphics]\nshow_cursor = 0"  > /root/.kivy/config.ini


RUN mkdir /app \
    && mkdir /app/assets \
    && mkdir /app/configuration \
    && mkdir /app/screenshots \
    && touch /app/configuration/desktop-panel-config.json \
    && touch /app/configuration/issuelist.json


COPY requirements.txt /
RUN python3 -m pip install -r requirements.txt


COPY . /app/


WORKDIR /app


CMD ["python3", "-u", "app.py"]
