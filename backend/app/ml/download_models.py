"""Run at `docker build`: fetch model weights into the image so the service works offline.

- PekingU/rtdetr_r18vd_coco_o365   RT-DETR detector, Apache-2.0 (code and weights)
- IDEA-Research/grounding-dino-tiny open-vocabulary detector for key frames, Apache-2.0
See docs/LICENSES.md. Revisions are pinned for reproducible builds.
"""
import os
import sys

from huggingface_hub import snapshot_download

TARGET = os.environ.get("MODELS_DIR", "/srv/models")
MODELS = [
    (os.environ.get("DETECTOR_MODEL", "PekingU/rtdetr_r18vd_coco_o365"),
     os.environ.get("DETECTOR_REVISION", "386c43855d01bcd966e548f3296fbd2cd2a2a40b")),
    (os.environ.get("OV_MODEL", "IDEA-Research/grounding-dino-tiny"),
     os.environ.get("OV_REVISION", "a2bb814dd30d776dcf7e30523b00659f4f141c71")),
]

def download_models():
    for model_id, revision in MODELS:
        path = snapshot_download(model_id, revision=revision, local_dir=os.path.join(TARGET, model_id.split("/")[-1]),
                                 allow_patterns=["*.json", "*.safetensors", "*.txt", "LICENSE*", "README*"])
        print("downloaded", model_id, revision[:8], "->", path, file=sys.stderr)


# Swagger UI for /docs (Apache-2.0): served locally because the service runs offline and its CSP forbids CDNs
SWAGGER_VERSION = "5.17.14"
SWAGGER_DIR = os.environ.get("DOCS_STATIC_DIR", "/srv/docs-static")


def download_swagger():
    import io
    import tarfile
    import urllib.request

    url = f"https://registry.npmjs.org/swagger-ui-dist/-/swagger-ui-dist-{SWAGGER_VERSION}.tgz"
    data = urllib.request.urlopen(url, timeout=120).read()
    os.makedirs(SWAGGER_DIR, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for name in ("swagger-ui-bundle.js", "swagger-ui.css", "LICENSE"):
            member = tar.getmember(f"package/{name}")
            with open(os.path.join(SWAGGER_DIR, name), "wb") as f:
                f.write(tar.extractfile(member).read())
    print("downloaded swagger-ui-dist", SWAGGER_VERSION, "->", SWAGGER_DIR, file=sys.stderr)


if __name__ == "__main__":
    download_models()
    download_swagger()
