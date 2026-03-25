# Full-Stack IoT Thermal Telemetry Platform

## Overview
This project is an end-to-end Internet of Things (IoT) platform designed to capture, stream, and visualize real-time thermal data from edge devices. Built to demonstrate a complete hardware-to-software pipeline, the system securely manages ESP32 microcontrollers, processes high-frequency MQTT telemetry, and renders live data on an authenticated web dashboard. 

It bridges the gap between low-level embedded systems and modern web architecture, showcasing a deep understanding of data flow, network protocols, and full-stack security.

## Key Features
* **Real-Time Edge Telemetry:** Interfaces with ESP32 hardware using C++ and the MQTT protocol to stream continuous 64-point thermal arrays and thermistor readings with sub-second latency.
* **Custom Authentication & Security:** Implements a from-scratch secure access system featuring bcrypt password hashing, UUID-based session management, and HTTP-only cookies to protect API endpoints and restrict dashboard access.
* **Live Heatmap Visualization:** Utilizes the HTML5 Canvas API and Vanilla JavaScript to instantly parse complex JSON payloads and render dynamic, color-mapped thermal visualizations directly in the browser.
* **Relational Data Architecture:** Employs a containerized MySQL database with strict foreign-key relationships to seamlessly link thousands of individual telemetry readings to unique hardware MAC addresses and authenticated user sessions.
* **Containerized Microservices:** Fully orchestrated using Docker and Docker Compose, ensuring consistent, reproducible builds across the database and ASGI web server environments.

## Tech Stack
* **Hardware & Firmware:** ESP32, C++, PlatformIO, Sensor Integration
* **Backend:** Python 3.13, FastAPI, Paho-MQTT, bcrypt, Uvicorn
* **Database:** MySQL 8.0, Relational Data Modeling
* **Frontend:** HTML5, CSS3, Vanilla JavaScript, WebSockets
* **DevOps:** Docker, Docker Compose

Demo Video
https://youtu.be/wYtXRtdW10Q
