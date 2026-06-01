# Hugging Face Spaces — Docker deployment
#
# This repo (road_model_inputs_interface) is the HF Space.
# leap_road_model is cloned from GitHub during the build.
# Override LEAP_ROAD_MODEL_REPO via HF Space build args if the URL ever changes.

FROM python:3.12-slim

# git is needed to clone leap_road_model; libgomp1 is needed by numpy/scipy
RUN apt-get update \
    && apt-get install -y --no-install-recommends git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Dependencies (cached layer, rebuilt only when requirements change) ---
COPY requirements.txt ./interface-requirements.txt

ARG LEAP_ROAD_MODEL_REPO=https://github.com/asia-pacific-energy-research-centre/leap_road_model
# LEAP_ROAD_MODEL_VERSION pins the clone to a specific commit so the cache is
# busted automatically when leap_road_model changes. Update this to the latest
# commit SHA after pushing new data or code to leap_road_model.
ARG LEAP_ROAD_MODEL_VERSION=4a66c55
RUN git clone ${LEAP_ROAD_MODEL_REPO} /app/leap_road_model \
    && cd /app/leap_road_model && git checkout ${LEAP_ROAD_MODEL_VERSION}

RUN pip install --no-cache-dir \
    -r interface-requirements.txt \
    -r /app/leap_road_model/requirements.txt

# --- Application source ---
COPY . /app/

# Pre-create output directories
RUN mkdir -p \
    /app/leap_road_model/results \
    /app/leap_road_model/input_data/module1_defaults

# --- Runtime environment ---
ENV MPLBACKEND=Agg
ENV PORT=7860
ENV RELOAD=false
ENV LEAP_ROAD_MODEL_DIR=/app/leap_road_model
ENV ROAD_MODEL_ESTO_CSV=/app/leap_road_model/input_data/esto_transport_2000_2022.csv
ENV ROAD_MODEL_MACRO_CSV=/app/leap_road_model/input_data/9th_macro_data.csv

WORKDIR /app/back-end

EXPOSE 7860

CMD ["python", "run.py"]
