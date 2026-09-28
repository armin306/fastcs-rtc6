#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$SCRIPT_DIR/src/fastcs_rtc6/bindings"
rm -rf build
mkdir -p build
cd build
cmake ..
make
cd "$SCRIPT_DIR"

# Copy the newly built .so file if it was output to the wrong location
if [ -f "/workspace/src/fastcs_rtc6/bindings/rtc6_bindings.cpython-311-x86_64-linux-gnu.so" ]; then
    cp /workspace/src/fastcs_rtc6/bindings/rtc6_bindings.cpython-311-x86_64-linux-gnu.so \
       "$SCRIPT_DIR/src/fastcs_rtc6/bindings/rtc6_bindings.cpython-311-x86_64-linux-gnu.so"
fi

pip install -e .
pybind11-stubgen fastcs_rtc6.bindings.rtc6_bindings -o src

# Copy the generated .pyi from build dir to the correct location
if [ -f "src/fastcs_rtc6/bindings/build/src/fastcs_rtc6/bindings/rtc6_bindings.pyi" ]; then
    cp src/fastcs_rtc6/bindings/build/src/fastcs_rtc6/bindings/rtc6_bindings.pyi \
       src/fastcs_rtc6/bindings/rtc6_bindings.pyi
fi

ruff format .
