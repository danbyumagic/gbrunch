#!/bin/bash
set -euo pipefail
project=$(cd "$(dirname "$0")/../.." && pwd)
scratch=${GBRUNCH_TOOLBOX_SCRATCH:-$project/build/toolbox-scratch}
output=${GBRUNCH_TOOLBOX_OUTPUT:-$project/build/toolbox-output}
assets=${GBRUNCH_TOOLBOX_ASSETS:-$project/assets}
runtime=${GBRUNCH_TOOLBOX_RUNTIME:-$project/toolkit/runtime}
mkdir -p "$scratch" "$output"
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock run --rm --privileged --name gbrunch-toolbox-builder \
 --mount "type=bind,src=$project,dst=/src,readonly" \
 --mount "type=bind,src=$scratch,dst=/scratch" \
 --mount "type=bind,src=$output,dst=/out" \
 --mount "type=bind,src=$assets,dst=/assets,readonly" \
 --mount "type=bind,src=$runtime,dst=/runtime,readonly" \
 --mount 'type=bind,src=/etc/ssl/certs/ca-certificates.crt,dst=/run/build-ca-bundle.pem,readonly' \
 debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f /bin/bash /src/toolkit/build/build-in-container.sh
