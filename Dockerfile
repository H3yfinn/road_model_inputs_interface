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
# Defaults to the latest leap_road_model main branch. Set LEAP_ROAD_MODEL_REF to
# a commit SHA or another branch/tag only when a reproducible deployment is needed.
ARG LEAP_ROAD_MODEL_REF=a7f0dbe1e6e6d654331c8f48f2831111bea49c24

RUN if [ "${LEAP_ROAD_MODEL_REF}" = "main" ]; then \
        git clone --depth 1 --branch main ${LEAP_ROAD_MODEL_REPO} /app/leap_road_model; \
    else \
        git clone ${LEAP_ROAD_MODEL_REPO} /app/leap_road_model \
        && cd /app/leap_road_model \
        && git checkout ${LEAP_ROAD_MODEL_REF}; \
    fi

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
