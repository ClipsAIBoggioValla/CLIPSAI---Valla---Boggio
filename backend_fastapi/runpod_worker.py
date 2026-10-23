import runpod
from backend.handler import handler

runpod.serverless.start({"handler": handler})
