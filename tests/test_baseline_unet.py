import pytest
torch = pytest.importorskip("torch")


def test_unet_forward_shape():
    from models.baseline_unet import BaselineUNet
    m = BaselineUNet(in_ch=36, n_leads=9)
    x = torch.zeros(2, 36, 110, 160)
    y = m(x)
    assert y.shape == (2, 9, 110, 160)
    assert int(m.count_params()) > 100_000
