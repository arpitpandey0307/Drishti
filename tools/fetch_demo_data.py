"""Fetch demo datasets from HF Hub so a fresh clone can run the viewer.

Downloads into outputs/datasets/ (gitignored):
  v0 viewer set: kiet_flood_test.h5 (17MB) + kiet_networks_test.json
  v1 demo set:   v1/kiet_flood_test.h5 (67MB) + v1/kiet_networks_v1.json + v1/normalization_train.json
Source: Aman34243/drishti-demo-data (public, free).
"""
import os

REPO = "Aman34243/drishti-demo-data"

FILES = [
    ("v0/kiet_flood_test.h5", "outputs/datasets/kiet_flood_test.h5"),
    ("v0/kiet_networks_test.json", "outputs/datasets/kiet_networks_test.json"),
    ("v1/kiet_flood_test.h5", "outputs/datasets/v1/kiet_flood_test.h5"),
    ("v1/kiet_networks_v1.json", "outputs/datasets/v1/kiet_networks_v1.json"),
    ("v1/normalization_train.json", "outputs/datasets/v1/normalization_train.json"),
]


def main():
    from huggingface_hub import hf_hub_download
    for src, dst in FILES:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            print("exists, skip:", dst)
            continue
        p = hf_hub_download(REPO, src)
        import shutil
        shutil.copy(p, dst)
        print("fetched:", dst)


if __name__ == "__main__":
    main()
