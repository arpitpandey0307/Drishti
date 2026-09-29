# space/ — source of the HF static demo (https://aman34243-drishti-flood-nowcast.static.hf.space/)

Tracked: `index.html` (demo page) + `windows/meta.json` (window index).
Git-ignored binaries (identical copies hosted on the Space):
`drishti.onnx` + `drishti.onnx.data` (model) and `windows/w*.bin` (demo inputs).

## Fetch binaries (to run the demo locally or rebuild the Space)

```bash
python3 -c "
from api.route_nowcast import _get
base = 'https://aman34243-drishti-flood-nowcast.static.hf.space'
for p in ['drishti.onnx', 'drishti.onnx.data', 'windows/meta.json',
          'windows/w0.bin', 'windows/w1.bin', 'windows/w2.bin',
          'windows/w3.bin', 'windows/w4.bin', 'windows/w5.bin']:
    _get(base, p, 'space')
"
python3 -m http.server 8123   # open /space/index.html
```

## Rebuild / re-export

- Model: `models/baseline_unet.py` + weights `Aman34243/drishti-flood-nowcaster`
  → single-file ONNX (`drishti.onnx`, weights inlined — ORT-web cannot load the
  external-data sidecar over HTTP).
- Windows: `dataset/ml_dataset.py:FloodWindows` + `models/train_baseline.py:build_sample`
  → float32 LE `w*.bin` (36×110×160) + `meta.json` (see `windows/meta.json` schema).
- Publish: `hf upload Aman34243/drishti-flood-nowcast space --type space`
