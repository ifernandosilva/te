FROM nvidia/cuda:11.8.0-devel-ubuntu22.04 as builder

RUN apt-get update && \
    apt-get install --no-install-recommends -y git build-essential python3-dev python3-pip && \
    rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/qwopqwop200/GPTQ-for-LLaMa /build

WORKDIR /build

ARG GPTQ_VERSION
RUN git checkout ${GPTQ_VERSION}

RUN python3 -m venv /build/venv
RUN . /build/venv/bin/activate && \
    pip3 install torch torchvision torchaudio && \
    pip3 install -r requirements.txt

# https://developer.nvidia.com/cuda-gpus
# for a rtx 2060: ARG TORCH_CUDA_ARCH_LIST="7.5"
ARG TORCH_CUDA_ARCH_LIST="3.5;5.0;6.0;6.1;7.0;7.5;8.0;8.6+PTX"
RUN . /build/venv/bin/activate && \
    python3 setup_cuda.py bdist_wheel -d .

FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

LABEL maintainer="Your Name <your.email@example.com>"
LABEL description="Docker image for GPTQ-for-LLaMa and Text Generation WebUI"

RUN apt-get update && \
    apt-get install --no-install-recommends -y git python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip pip3 install virtualenv

COPY . /app/

WORKDIR /app

ARG WEBUI_VERSION
RUN test -n "${WEBUI_VERSION}" && git reset --hard ${WEBUI_VERSION} || echo "Using provided webui source"

RUN virtualenv /app/venv
RUN . /app/venv/bin/activate && \
    pip3 install torch torchvision torchaudio && \
    pip3 install -r requirements.txt

COPY --from=builder /build /app/repositories/GPTQ-for-LLaMa
RUN . /app/venv/bin/activate && \
    pip3 install /app/repositories/GPTQ-for-LLaMa/*.whl

ENV CLI_ARGS=""

RUN --mount=type=cache,target=/root/.cache/pip . /app/venv/bin/activate cd extensions/api && pip3 install -r requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip . /app/venv/bin/activate cd extensions/elevenlabs_tts && pip3 install -r requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip . /app/venv/bin/activate cd extensions/google_translate && pip3 install -r requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip . /app/venv/bin/activate cd extensions/silero_tts && pip3 install -r requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip . /app/venv/bin/activate cd extensions/whisper_stt && pip3 install -r requirements.txt

CMD . /app/venv/bin/activate && python3 server.py ${CLI_ARGS}
