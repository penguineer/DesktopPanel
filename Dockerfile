FROM mrtux/kivy-rpi-headless:2.1-bullseye

RUN mkdir -p /root/.kivy \
    && echo "[graphics]\nshow_cursor = 0"  > /root/.kivy/config.ini


RUN mkdir /app \
    && mkdir /app/assets \
    && touch /app/desktop-panel-config.json \
    && touch /app/issuelist.json


COPY requirements.txt /
RUN python3 -m pip install -r requirements.txt


COPY . /app/


WORKDIR /app


CMD ["python3", "-u", "app.py"]
