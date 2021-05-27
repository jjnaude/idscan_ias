# ID-Scan Image analysis server

This repository houses the ID-Scan Image analysis server. This server is intended to present a REST API exposing a webservice that allows the user to enroll and look up individual cattle by matching their muzzle prints in the supplied images.

This release is just a stub that does no actual matching, but presents the same interfaces and has (most of) the same dependencies that the final version is expected to have. The stub is intended to be used by SilverBridge to integrate against until such time as the final server is available. 

## Installation

To get the server up and running requires that the following pre-requisites are in place:

- A recent version of Docker (tested against version 20.10.6, build 370c289)
- A recent version of docker-compose (tested against version 1.29.2, build 5becea4c)
- An NVIDIA GPU with a recent driver (tested against GeForce GTX 1080 running driver 465.19.01)
- A recent version of nvidia-container-runtime (tested against commit 12644e614e25b05da6fd08a38ffa0cfe1903fdec)

Once these dependencies are in place, installation should be very straightforward.

```bash
https://github.com/jjnaude/idscan_ias.git
cd idscan_ias
docker-compose up
```

If all is well, the system should present the REST API at http://localhost:8080 ,the swagger-ui documentation will be available at http://localhost:8080/ui and the API definition itself in OpenAPI Specification format can be downloaded from 
http://localhost:8080/openapi.json. This allows the use of a wide range of [tooling](https://github.com/OAI/OpenAPI-Specification/blob/main/IMPLEMENTATIONS.md#implementations) that implements this standard. These may be used to generate documentation, test-harnesses, clients etc. 

Once it has been verified that a GPU can succesfully be made available to the GPU-worker service, it no longer makes sense to tie up a resource like this if the API is only being used to integrate against and does not actually require the GPU. In this case the API can be started without checking for CUDA availability by defining the environment variable IAS_SKIP_GPU_CHECK, allowing the API to be run from a machine that does not have an NVIDIA GPU present.

```bash
IAS_SKIP_GPU_CHECK=1 docker-compose up ias 
```
