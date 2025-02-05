FROM python:latest

# Set the Chrome version
ENV CHROME_VERSION 131.0.6778.85
ENV CHROMEDRIVER_VERSION ${CHROME_VERSION}

# Install required tools and libraries
RUN apt-get -yqq update && \
    apt-get -yqq install --no-install-recommends \
    curl unzip gnupg wget libglib2.0-0 libx11-6 libnss3 \
    libgdk-pixbuf2.0-0 libx11-xcb1 libxcomposite1 libxrandr2 \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdrm2 \
    fonts-liberation libappindicator3-1 libnspr4 libnss3 libxss1 \
    libgbm1 && \
    rm -rf /var/lib/apt/lists/*

# Install Chrome WebDriver
RUN mkdir -p /opt/chromedriver-${CHROMEDRIVER_VERSION} && \
    curl -sS -o /tmp/chromedriver_linux64.zip https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip -qq /tmp/chromedriver_linux64.zip -d /opt/chromedriver-${CHROMEDRIVER_VERSION} && \
    rm /tmp/chromedriver_linux64.zip && \
    chmod +x /opt/chromedriver-${CHROMEDRIVER_VERSION}/chromedriver-linux64/chromedriver && \
    ln -fs /opt/chromedriver-${CHROMEDRIVER_VERSION}/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver

# Install Google Chrome version 131.0.6778.85
RUN curl -sS -o /tmp/chrome-linux64.zip https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip && \
    unzip -qq /tmp/chrome-linux64.zip -d /opt/google-chrome-${CHROME_VERSION} && \
    rm /tmp/chrome-linux64.zip && \
    ln -fs /opt/google-chrome-${CHROME_VERSION}/chrome-linux64/chrome /usr/local/bin/google-chrome-stable

# Set pip to use Tsinghua University mirror
RUN echo "[global]\nindex-url = https://pypi.tuna.tsinghua.edu.cn/simple" > /etc/pip.conf


# Set working directory
WORKDIR /app
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir selenium
RUN pip install playwright[chromium]

# Set container to idle on start (or modify to start your application)
CMD ["tail", "-f", "/dev/null"]