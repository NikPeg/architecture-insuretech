#!/usr/bin/env python3
import os
import socket
from flask import Flask, Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# Создаем метрику для подсчета запросов
http_requests_total = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])

@app.route('/')
def index():
    http_requests_total.labels(method='GET', endpoint='/').inc()
    hostname = socket.gethostname()
    pod_name = os.getenv('HOSTNAME', hostname)
    return f'Pod ID: {pod_name}\n'

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@app.route('/health')
def health():
    return 'OK\n'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
