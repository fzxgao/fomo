#!/usr/bin/env bash
export LD_LIBRARY_PATH=/net/nfs1/public/EM/CUDA/cuda-11.8/lib64:/lmb/home/fgao/micromamba/envs/cryocare_11/lib/python3.8/site-packages/nvidia/cublas/lib:/public/EM/imod/IMOD/lib:/public/EM/OpenMPI/openmpi-4.0.1/build/lib:/lmb/home/fgao/scripts/dynamo/MCRLinux/runtime/glnxa64:/lmb/home/fgao/scripts/dynamo/MCRLinux/bin/glnxa64:/lmb/home/fgao/micromamba/envs/dynamo/lib:/lmb/home/fgao/micromamba/pkgs/libstdcxx-ng-13.1.0-hfd8a6a1_0/lib/
source /lmb/home/fgao/scripts/dynamo/dynamo_activate_linux.sh
exec dynamo "$@"