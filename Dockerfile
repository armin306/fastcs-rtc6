# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION} AS developer

# Add any system dependencies for the developer/build environment here
RUN apt-get update && apt-get install -y --no-install-recommends \
    graphviz \
    build-essential \
    iputils-ping \
    cmake \
    python3-dev \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up a virtual environment and put it in PATH
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH

# The build stage installs the context into the venv
FROM developer AS build
COPY . /context
WORKDIR /context
RUN touch dev-requirements.txt && pip install -c dev-requirements.txt .
RUN pip install dodal

# The runtime stage copies the built venv into a slim runtime container
FROM python:${PYTHON_VERSION}-slim AS runtime
# Add apt-get system dependecies for runtime here if needed
COPY --from=build /venv/ /venv/
ENV PATH=/venv/bin:$PATH
RUN bash "$(python -c 'import fastcs_rtc6, os; print(os.path.join(os.path.dirname(fastcs_rtc6.__file__), "install_library.sh"))')"

# change this entrypoint if it is not the same as the repo
ENTRYPOINT ["fastcs-rtc6"]
# fastcs.yaml isn't baked into this image - the real deployment (k8s) is
# expected to mount it and override this with `run <path-to-config>`,
# matching fastcs-carbide's Dockerfile.
CMD ["--version"]
